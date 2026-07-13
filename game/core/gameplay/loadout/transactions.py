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
                    )
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
                else:
                    raise TypeError(f"未知装配操作：{type(operation).__name__}")
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
            next_loadout = LoadoutState(
                loadout.character_id,
                slots,
                loadout.revision + 1,
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
                    inventory_outcome.value.state,
                    (*inventory_outcome.value.events, *events),
                )
            )
        except RuleViolation as exc:
            context.random.restore(checkpoint)
            return RuleOutcome.failed(exc.failure)

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
    ) -> None:
        slot = self.slots.require(operation.slot_id)
        instance = self._require_instance(operation.asset_id, inventory_state)
        if inventory_state.owner_of(instance.id) != loadout.character_id:
            self._fail("loadout.owner_mismatch", "角色不是待装备物品的当前所有者")
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
    "EquipAsset",
    "LoadoutEngine",
    "LoadoutExecution",
    "LoadoutOperation",
    "LoadoutTransaction",
    "UnequipSlot",
]
