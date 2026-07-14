"""装配状态与库存位置共同提交的原子事务。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol

from ..context import RuleContext
from ..errors import RuleOutcome, RuleViolation
from ..events import RuleEvent
from ..ids import StableId, stable_id
from ..inventory import (
    InventoryEngine,
    InventoryState,
    InventoryTransaction,
    ItemCatalog,
    ItemInstance,
    MoveAsset,
    SwapAssetContainers,
)
from .models import (
    LOADOUT_ITEM_COMPONENT_ID,
    LoadoutItemComponent,
    LoadoutPreset,
    LoadoutSlotCatalog,
    LoadoutState,
)


class LoadoutOperation(Protocol):
    """装配事务接受的原子操作标记。"""


@dataclass(frozen=True)
class EquipAsset:
    slot_id: StableId
    asset_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "slot_id", stable_id(self.slot_id, field="loadout slot id"))
        if not self.asset_id.strip():
            raise ValueError("EquipAsset 缺少 asset_id")


@dataclass(frozen=True)
class UnequipSlot:
    slot_id: StableId

    def __post_init__(self) -> None:
        object.__setattr__(self, "slot_id", stable_id(self.slot_id, field="loadout slot id"))


@dataclass(frozen=True)
class SaveLoadoutPreset:
    preset_id: StableId

    def __post_init__(self) -> None:
        object.__setattr__(self, "preset_id", stable_id(self.preset_id, field="loadout preset id"))


@dataclass(frozen=True)
class DeleteLoadoutPreset:
    preset_id: StableId

    def __post_init__(self) -> None:
        object.__setattr__(self, "preset_id", stable_id(self.preset_id, field="loadout preset id"))


@dataclass(frozen=True)
class ActivateLoadoutPreset:
    preset_id: StableId

    def __post_init__(self) -> None:
        object.__setattr__(self, "preset_id", stable_id(self.preset_id, field="loadout preset id"))


@dataclass(frozen=True)
class LoadoutTransaction:
    id: str
    actor_id: str
    expected_revision: int
    inventory_container_id: str
    equipped_container_id: str
    operations: tuple[LoadoutOperation, ...]

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.actor_id.strip():
            raise ValueError("LoadoutTransaction 缺少 id 或 actor_id")
        if self.expected_revision < 0:
            raise ValueError("LoadoutTransaction.expected_revision 不能小于 0")
        if not self.inventory_container_id.strip() or not self.equipped_container_id.strip():
            raise ValueError("LoadoutTransaction 缺少库存或已装备容器 id")
        if self.inventory_container_id == self.equipped_container_id:
            raise ValueError("库存容器和已装备容器不能相同")
        if not self.operations:
            raise ValueError("LoadoutTransaction.operations 不能为空")


@dataclass(frozen=True)
class LoadoutExecution:
    transaction_id: str
    loadout: LoadoutState
    inventory: InventoryState
    events: tuple[RuleEvent, ...]


class LoadoutEngine:
    """统一处理武器与装备的装上、替换和卸下。"""

    def __init__(
        self,
        slots: LoadoutSlotCatalog,
        items: ItemCatalog,
        inventory: InventoryEngine,
    ) -> None:
        if not slots.finalized:
            slots.finalize()
        if not items.finalized:
            items.finalize()
        if inventory.catalog is not items:
            raise ValueError("装配引擎和库存引擎必须使用同一个物品目录")
        self.slots = slots
        self.items = items
        self.inventory = inventory
        known_slots = set(self.slots.definitions.ids())
        for item in self.items.definitions:
            component = item.components.get(LOADOUT_ITEM_COMPONENT_ID)
            if component is None:
                continue
            assert isinstance(component, LoadoutItemComponent)
            unknown = set(component.allowed_slot_ids) - known_slots
            if unknown:
                raise KeyError(
                    f"物品 {item.id} 引用了未知装配槽：{', '.join(sorted(unknown))}"
                )

    def execute(
        self,
        transaction: LoadoutTransaction,
        *,
        loadout: LoadoutState,
        inventory_state: InventoryState,
        context: RuleContext,
    ) -> RuleOutcome[LoadoutExecution]:
        checkpoint = context.random.checkpoint()
        try:
            if loadout.revision != transaction.expected_revision:
                self._fail(
                    "loadout.revision_conflict",
                    "装配状态版本与事务预期不一致",
                    {"expected": transaction.expected_revision, "actual": loadout.revision},
                )
            self._validate_containers(transaction, loadout, inventory_state)
            self._validate_loadout(loadout, inventory_state, transaction.equipped_container_id)
            slots = dict(loadout.slots)
            presets = dict(loadout.presets)
            active_preset_id = loadout.active_preset_id
            locations = {
                asset.id: asset.container_id
                for asset in (*inventory_state.stacks.values(), *inventory_state.instances.values())
            }
            inventory_operations: list[object] = []
            event_specs: list[tuple[str, StableId, Mapping[str, object]]] = []
            for operation in transaction.operations:
                if isinstance(operation, EquipAsset):
                    self._equip(
                        operation,
                        slots,
                        locations,
                        inventory_operations,
                        event_specs,
                        loadout,
                        inventory_state,
                        transaction,
                        presets,
                        active_preset_id,
                    )
                    if active_preset_id is not None:
                        presets[active_preset_id] = LoadoutPreset(active_preset_id, slots)
                elif isinstance(operation, UnequipSlot):
                    self._unequip(
                        operation,
                        slots,
                        locations,
                        inventory_operations,
                        event_specs,
                        inventory_state,
                        transaction,
                    )
                    if active_preset_id is not None:
                        presets[active_preset_id] = LoadoutPreset(active_preset_id, slots)
                elif isinstance(operation, SaveLoadoutPreset):
                    # 保存到另一套等同于转移这些实例的配装归属，原套对应槽位自动清空。
                    transferring = set(slots.values())
                    for preset_id, preset in tuple(presets.items()):
                        if preset_id == operation.preset_id:
                            continue
                        remaining = {
                            slot_id: asset_id
                            for slot_id, asset_id in preset.slots.items()
                            if asset_id not in transferring
                        }
                        if len(remaining) != len(preset.slots):
                            presets[preset_id] = LoadoutPreset(preset_id, remaining)
                    presets[operation.preset_id] = LoadoutPreset(operation.preset_id, slots)
                    active_preset_id = operation.preset_id
                    event_specs.append(
                        (
                            "loadout.preset.saved",
                            operation.preset_id,
                            {"preset_id": operation.preset_id, "asset_count": len(slots)},
                        )
                    )
                elif isinstance(operation, DeleteLoadoutPreset):
                    if operation.preset_id not in presets:
                        self._fail("loadout.preset_unknown", "找不到指定配装")
                    del presets[operation.preset_id]
                    if active_preset_id == operation.preset_id:
                        active_preset_id = None
                    event_specs.append(
                        (
                            "loadout.preset.deleted",
                            operation.preset_id,
                            {"preset_id": operation.preset_id},
                        )
                    )
                elif isinstance(operation, ActivateLoadoutPreset):
                    try:
                        preset = presets[operation.preset_id]
                    except KeyError:
                        self._fail("loadout.preset_unknown", "找不到指定配装")
                    self._activate_preset(
                        preset,
                        slots,
                        locations,
                        inventory_operations,
                        loadout,
                        inventory_state,
                        transaction,
                    )
                    slots = dict(preset.slots)
                    active_preset_id = operation.preset_id
                    event_specs.append(
                        (
                            "loadout.preset.activated",
                            operation.preset_id,
                            {"preset_id": operation.preset_id, "asset_count": len(slots)},
                        )
                    )
                else:
                    raise TypeError(f"未知装配操作：{type(operation).__name__}")
            if inventory_operations:
                inventory_outcome = self.inventory.execute(
                    InventoryTransaction(
                        f"{transaction.id}:inventory",
                        transaction.actor_id,
                        "inventory.loadout_change",
                        tuple(inventory_operations),
                    ),
                    state=inventory_state,
                    context=context,
                )
                if inventory_outcome.failure:
                    raise RuleViolation(
                        inventory_outcome.failure.code,
                        inventory_outcome.failure.message,
                        inventory_outcome.failure.details,
                    )
                assert inventory_outcome.value is not None
                next_inventory = inventory_outcome.value.state
                inventory_events = inventory_outcome.value.events
            else:
                next_inventory = inventory_state
                inventory_events = ()
            next_loadout = LoadoutState(
                loadout.character_id,
                slots,
                loadout.revision + 1,
                presets,
                active_preset_id,
            )
            events = tuple(
                RuleEvent.from_context(
                    context,
                    kind=kind,
                    source_id=transaction.actor_id,
                    target_id=loadout.character_id,
                    subject_id=subject_id,
                    values={"transaction_id": transaction.id, **values},
                )
                for kind, subject_id, values in event_specs
            )
            return RuleOutcome.success(
                LoadoutExecution(
                    transaction.id,
                    next_loadout,
                    next_inventory,
                    (*inventory_events, *events),
                )
            )
        except RuleViolation as exc:
            context.random.restore(checkpoint)
            return RuleOutcome.failed(exc.failure)

    def _activate_preset(
        self,
        preset: LoadoutPreset,
        current_slots: dict[StableId, str],
        locations: dict[str, str],
        inventory_operations: list[object],
        loadout: LoadoutState,
        inventory_state: InventoryState,
        transaction: LoadoutTransaction,
    ) -> None:
        current_assets = set(current_slots.values())
        target_assets = set(preset.slots.values())
        for slot_id, asset_id in preset.slots.items():
            slot = self.slots.require(slot_id)
            instance = self._require_instance(asset_id, inventory_state)
            if inventory_state.owner_of(asset_id) != loadout.character_id:
                self._fail("loadout.owner_mismatch", "配装引用了不属于当前角色的物品")
            component = self._component(instance)
            definition = self.items.require(instance.definition_id)
            if slot.id not in component.allowed_slot_ids or not definition.tags.allows(
                required=slot.required_item_tags,
                blocked=slot.blocked_item_tags,
            ):
                self._fail("loadout.slot_rejected", "配装中的物品不符合槽位约束")
            expected_container = (
                transaction.equipped_container_id
                if asset_id in current_assets
                else transaction.inventory_container_id
            )
            if locations.get(asset_id) != expected_container:
                self._fail("loadout.preset_asset_unavailable", "配装中的物品不在可切换位置")
        outgoing = sorted(current_assets - target_assets)
        incoming = sorted(target_assets - current_assets)
        paired = min(len(outgoing), len(incoming))
        for index in range(paired):
            inventory_operations.append(
                SwapAssetContainers(incoming[index], outgoing[index])
            )
            locations[outgoing[index]] = transaction.inventory_container_id
            locations[incoming[index]] = transaction.equipped_container_id
        for asset_id in outgoing[paired:]:
            inventory_operations.append(MoveAsset(asset_id, transaction.inventory_container_id))
            locations[asset_id] = transaction.inventory_container_id
        for asset_id in incoming[paired:]:
            inventory_operations.append(MoveAsset(asset_id, transaction.equipped_container_id))
            locations[asset_id] = transaction.equipped_container_id

    def _equip(
        self,
        operation: EquipAsset,
        slots: dict[StableId, str],
        locations: dict[str, str],
        inventory_operations: list[object],
        event_specs: list[tuple[str, StableId, Mapping[str, object]]],
        loadout: LoadoutState,
        inventory_state: InventoryState,
        transaction: LoadoutTransaction,
        presets: Mapping[StableId, LoadoutPreset],
        active_preset_id: StableId | None,
    ) -> None:
        slot = self.slots.require(operation.slot_id)
        instance = self._require_instance(operation.asset_id, inventory_state)
        if inventory_state.owner_of(instance.id) != loadout.character_id:
            self._fail("loadout.owner_mismatch", "角色不是待装备物品的当前所有者")
        for preset_id, preset in presets.items():
            if preset_id != active_preset_id and instance.id in preset.slots.values():
                self._fail(
                    "loadout.asset_bound_to_other_preset",
                    "物品已经属于另一套配装",
                    {"asset_id": instance.id, "preset_id": preset_id},
                )
        component = self._component(instance)
        definition = self.items.require(instance.definition_id)
        if slot.id not in component.allowed_slot_ids or not definition.tags.allows(
            required=slot.required_item_tags,
            blocked=slot.blocked_item_tags,
        ):
            self._fail(
                "loadout.slot_rejected",
                "物品不能进入指定装配槽",
                {"asset_id": instance.id, "slot_id": slot.id},
            )
        occupied_slot = next(
            (key for key, asset_id in slots.items() if asset_id == instance.id),
            None,
        )
        if occupied_slot is not None:
            self._fail(
                "loadout.asset_already_equipped",
                "物品已经处于装配状态",
                {"asset_id": instance.id, "slot_id": occupied_slot},
            )
        if locations.get(instance.id) != transaction.inventory_container_id:
            self._fail(
                "loadout.asset_not_in_inventory",
                "待装备物品不在本次指定的库存容器中",
                {"asset_id": instance.id},
            )
        previous = slots.get(slot.id)
        if previous is None:
            inventory_operations.append(MoveAsset(instance.id, transaction.equipped_container_id))
            locations[instance.id] = transaction.equipped_container_id
            event_kind = "loadout.asset.equipped"
        else:
            inventory_operations.append(SwapAssetContainers(instance.id, previous))
            locations[instance.id] = transaction.equipped_container_id
            locations[previous] = transaction.inventory_container_id
            event_kind = "loadout.asset.replaced"
        slots[slot.id] = instance.id
        event_specs.append(
            (
                event_kind,
                slot.id,
                {
                    "slot_id": slot.id,
                    "asset_id": instance.id,
                    "item_id": instance.definition_id,
                    "previous_asset_id": previous,
                },
            )
        )

    def _unequip(
        self,
        operation: UnequipSlot,
        slots: dict[StableId, str],
        locations: dict[str, str],
        inventory_operations: list[object],
        event_specs: list[tuple[str, StableId, Mapping[str, object]]],
        inventory_state: InventoryState,
        transaction: LoadoutTransaction,
    ) -> None:
        slot = self.slots.require(operation.slot_id)
        try:
            asset_id = slots.pop(slot.id)
        except KeyError:
            self._fail(
                "loadout.slot_empty",
                "指定装配槽当前没有物品",
                {"slot_id": slot.id},
            )
        instance = self._require_instance(asset_id, inventory_state)
        if locations.get(asset_id) != transaction.equipped_container_id:
            self._fail("loadout.location_mismatch", "已装备物品的位置与装配状态不一致")
        inventory_operations.append(MoveAsset(asset_id, transaction.inventory_container_id))
        locations[asset_id] = transaction.inventory_container_id
        event_specs.append(
            (
                "loadout.asset.unequipped",
                slot.id,
                {
                    "slot_id": slot.id,
                    "asset_id": asset_id,
                    "item_id": instance.definition_id,
                },
            )
        )

    def _validate_containers(
        self,
        transaction: LoadoutTransaction,
        loadout: LoadoutState,
        inventory_state: InventoryState,
    ) -> None:
        try:
            inventory_container = inventory_state.containers[transaction.inventory_container_id]
            equipped_container = inventory_state.containers[transaction.equipped_container_id]
        except KeyError as exc:
            self._fail(
                "loadout.container_unknown",
                "找不到装配事务需要的容器",
                {"container_id": exc.args[0]},
            )
        if inventory_container.owner_id != loadout.character_id:
            self._fail("loadout.owner_mismatch", "库存容器不属于当前角色")
        if equipped_container.owner_id != loadout.character_id:
            self._fail("loadout.owner_mismatch", "已装备容器不属于当前角色")
        if (
            equipped_container.maximum_assets is not None
            and equipped_container.maximum_assets < len(self.slots.definitions.ids())
        ):
            self._fail(
                "loadout.container_invalid",
                "已装备容器容量小于标准装配槽数量",
                {
                    "container_id": equipped_container.id,
                    "capacity": equipped_container.maximum_assets,
                    "required": len(self.slots.definitions.ids()),
                },
            )

    def _validate_loadout(
        self,
        loadout: LoadoutState,
        inventory_state: InventoryState,
        equipped_container_id: str,
    ) -> None:
        for slot_id, asset_id in loadout.slots.items():
            slot = self.slots.require(slot_id)
            instance = self._require_instance(asset_id, inventory_state)
            component = self._component(instance)
            definition = self.items.require(instance.definition_id)
            if instance.container_id != equipped_container_id:
                self._fail("loadout.location_mismatch", "装配状态引用的物品不在已装备容器")
            if slot.id not in component.allowed_slot_ids or not definition.tags.allows(
                required=slot.required_item_tags,
                blocked=slot.blocked_item_tags,
            ):
                self._fail("loadout.slot_rejected", "现有装配状态不符合槽位约束")

    def _component(self, instance: ItemInstance) -> LoadoutItemComponent:
        definition = self.items.require(instance.definition_id)
        try:
            return definition.component(LOADOUT_ITEM_COMPONENT_ID, LoadoutItemComponent)
        except KeyError:
            self._fail(
                "loadout.item_not_equipable",
                "物品没有装配组件",
                {"item_id": definition.id},
            )

    @staticmethod
    def _require_instance(asset_id: str, inventory_state: InventoryState) -> ItemInstance:
        try:
            return inventory_state.instances[asset_id]
        except KeyError:
            LoadoutEngine._fail(
                "loadout.instance_unknown",
                "装配系统只接受独立物品实例",
                {"asset_id": asset_id},
            )

    @staticmethod
    def _fail(
        code: StableId,
        message: str,
        details: Mapping[str, object] | None = None,
    ) -> None:
        raise RuleViolation(code, message, details or {})


__all__ = [
    "ActivateLoadoutPreset",
    "DeleteLoadoutPreset",
    "EquipAsset",
    "LoadoutEngine",
    "LoadoutExecution",
    "LoadoutOperation",
    "LoadoutTransaction",
    "SaveLoadoutPreset",
    "UnequipSlot",
]
