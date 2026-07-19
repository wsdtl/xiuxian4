"""库存原子事务与标准资产操作。"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Mapping, Protocol

from ..context import RuleContext
from ..errors import RuleOutcome, RuleViolation
from ..events import RuleEvent
from ..ids import StableId, stable_id
from ..phases import ExecutionPhase
from .definitions import ItemCatalog, ItemDefinition
from .components import ITEM_STORAGE_COMPONENT_ID, ItemStorageComponent
from .models import (
    AssetReservation,
    InventoryState,
    ItemAssetKind,
    ItemContainer,
    ItemInstance,
    ItemStack,
    ProvenanceLot,
    ReservationMode,
    SourceReceipt,
)


class InventoryOperation(Protocol):
    """库存事务接受的原子操作标记。"""


@dataclass(frozen=True)
class GrantStack:
    asset_id: str
    definition_id: StableId
    container_id: str
    quantity: int
    receipt: SourceReceipt


@dataclass(frozen=True)
class AppendStack:
    """向既有堆叠追加一个可追溯来源批次。"""

    asset_id: str
    quantity: int
    receipt: SourceReceipt


@dataclass(frozen=True)
class GrantInstance:
    asset_id: str
    definition_id: StableId
    container_id: str
    receipt: SourceReceipt
    data: Mapping[str, object] = field(default_factory=dict)
    revision: int = 0


@dataclass(frozen=True)
class ConsumeStack:
    asset_id: str
    quantity: int
    reservation_id: str | None = None


@dataclass(frozen=True)
class ConsumeInstance:
    asset_id: str
    reservation_id: str | None = None


@dataclass(frozen=True)
class DestroyAsset:
    asset_id: str
    reservation_id: str | None = None


@dataclass(frozen=True)
class MoveAsset:
    asset_id: str
    destination_container_id: str
    reservation_id: str | None = None


@dataclass(frozen=True)
class UpdateInstance:
    """以完整类型化实例更新其数据，资产身份和位置不得改变。"""

    instance: ItemInstance
    expected_revision: int

    def __post_init__(self) -> None:
        if self.expected_revision < 0:
            raise ValueError("UpdateInstance.expected_revision 不能小于 0")


@dataclass(frozen=True)
class IncreaseContainerSpace:
    container_id: str
    amount: int
    maximum_space: int

    def __post_init__(self) -> None:
        if not self.container_id.strip():
            raise ValueError("IncreaseContainerSpace.container_id 不能为空")
        for field_name in ("amount", "maximum_space"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"IncreaseContainerSpace.{field_name} 必须是整数")
        if self.amount < 1 or self.maximum_space < self.amount:
            raise ValueError("容器扩容量和绝对上限无效")


@dataclass(frozen=True)
class SwapAssetContainers:
    first_asset_id: str
    second_asset_id: str


@dataclass(frozen=True)
class SplitStack:
    source_asset_id: str
    new_asset_id: str
    quantity: int


@dataclass(frozen=True)
class MergeStacks:
    source_asset_id: str
    target_asset_id: str


@dataclass(frozen=True)
class ReserveAsset:
    reservation_id: str
    asset_id: str
    mode: ReservationMode
    business_kind: StableId
    business_id: str
    quantity: int = 1
    expires_at: datetime | None = None


@dataclass(frozen=True)
class ReleaseReservation:
    reservation_id: str


@dataclass(frozen=True)
class InventoryTransaction:
    """调用方给出的唯一事务身份和有序操作。"""

    id: str
    actor_id: str
    reason: StableId
    operations: tuple[InventoryOperation, ...]

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("InventoryTransaction 缺少 id")
        if not self.actor_id.strip():
            raise ValueError("InventoryTransaction 缺少 actor_id")
        object.__setattr__(self, "reason", stable_id(self.reason, field="transaction reason"))
        if not self.operations:
            raise ValueError("InventoryTransaction.operations 不能为空")


@dataclass(frozen=True)
class InventoryExecution:
    transaction_id: str
    state: InventoryState
    events: tuple[RuleEvent, ...]


@dataclass
class _Draft:
    containers: dict[str, ItemContainer]
    stacks: dict[str, ItemStack]
    instances: dict[str, ItemInstance]
    reservations: dict[str, AssetReservation]
    asset_references: dict[str, int]
    next_reference_number: int
    events: list[RuleEvent]


class InventoryEngine:
    """在不可变快照上执行全有或全无的资产变更。"""

    def __init__(self, catalog: ItemCatalog) -> None:
        if not catalog.finalized:
            catalog.finalize()
        self.catalog = catalog

    def execute(
        self,
        transaction: InventoryTransaction,
        *,
        state: InventoryState,
        context: RuleContext,
    ) -> RuleOutcome[InventoryExecution]:
        checkpoint = context.random.checkpoint()
        draft = _Draft(
            containers=dict(state.containers),
            stacks=dict(state.stacks),
            instances=dict(state.instances),
            reservations=dict(state.reservations),
            asset_references=dict(state.asset_references),
            next_reference_number=state.next_reference_number,
            events=[],
        )
        try:
            self._release_expired(draft, transaction, context)
            for operation in transaction.operations:
                self._apply(operation, draft, transaction, context)
            result = InventoryState(
                containers=draft.containers,
                stacks=draft.stacks,
                instances=draft.instances,
                reservations=draft.reservations,
                revision=state.revision + 1,
                asset_references=draft.asset_references,
                next_reference_number=draft.next_reference_number,
            )
            self._validate_state(result)
            return RuleOutcome.success(
                InventoryExecution(transaction.id, result, tuple(draft.events))
            )
        except RuleViolation as exc:
            context.random.restore(checkpoint)
            return RuleOutcome.failed(exc.failure)

    def _apply(
        self,
        operation: InventoryOperation,
        draft: _Draft,
        transaction: InventoryTransaction,
        context: RuleContext,
    ) -> None:
        handlers = {
            GrantStack: self._grant_stack,
            AppendStack: self._append_stack,
            GrantInstance: self._grant_instance,
            ConsumeStack: self._consume_stack,
            ConsumeInstance: self._consume_instance,
            DestroyAsset: self._destroy_asset,
            MoveAsset: self._move_asset,
            UpdateInstance: self._update_instance,
            IncreaseContainerSpace: self._increase_container_space,
            SwapAssetContainers: self._swap_asset_containers,
            SplitStack: self._split_stack,
            MergeStacks: self._merge_stacks,
            ReserveAsset: self._reserve_asset,
            ReleaseReservation: self._release_reservation,
        }
        try:
            handler = handlers[type(operation)]
        except KeyError as exc:
            raise TypeError(f"未知库存操作：{type(operation).__name__}") from exc
        handler(operation, draft, transaction, context)

    def _grant_stack(
        self,
        operation: GrantStack,
        draft: _Draft,
        transaction: InventoryTransaction,
        context: RuleContext,
    ) -> None:
        self._require_new_asset_id(operation.asset_id, draft)
        definition = self._require_kind(operation.definition_id, ItemAssetKind.STACK)
        if operation.quantity < 1:
            self._fail("inventory.invalid_quantity", "发放数量必须大于 0")
        self._check_stack_limit(definition, operation.quantity)
        container = self._require_container(operation.container_id, draft)
        self._check_container(container, definition, ItemAssetKind.STACK, draft, adding=True)
        stack = ItemStack(
            operation.asset_id,
            definition.id,
            container.id,
            (ProvenanceLot(operation.receipt, operation.quantity),),
        )
        draft.stacks[stack.id] = stack
        reference_number = self._allocate_reference(stack.id, draft)
        self._event(
            draft,
            transaction,
            context,
            "inventory.item.granted",
            definition.id,
            container.owner_id,
            {
                "asset_id": stack.id,
                "quantity": stack.quantity,
                "container_id": container.id,
                "receipt_id": operation.receipt.id,
                "reference_number": reference_number,
            },
        )

    def _append_stack(
        self,
        operation: AppendStack,
        draft: _Draft,
        transaction: InventoryTransaction,
        context: RuleContext,
    ) -> None:
        if operation.quantity < 1:
            self._fail("inventory.invalid_quantity", "追加数量必须大于 0")
        stack = self._require_stack(operation.asset_id, draft)
        definition = self._require_kind(stack.definition_id, ItemAssetKind.STACK)
        self._check_stack_limit(definition, stack.quantity + operation.quantity)
        container = self._require_container(stack.container_id, draft)
        draft.stacks[stack.id] = replace(
            stack,
            lots=(*stack.lots, ProvenanceLot(operation.receipt, operation.quantity)),
            revision=stack.revision + 1,
        )
        self._event(
            draft,
            transaction,
            context,
            "inventory.item.granted",
            definition.id,
            container.owner_id,
            {
                "asset_id": stack.id,
                "quantity": operation.quantity,
                "container_id": container.id,
                "receipt_id": operation.receipt.id,
                "reference_number": draft.asset_references[stack.id],
            },
        )

    def _grant_instance(
        self,
        operation: GrantInstance,
        draft: _Draft,
        transaction: InventoryTransaction,
        context: RuleContext,
    ) -> None:
        self._require_new_asset_id(operation.asset_id, draft)
        definition = self._require_kind(operation.definition_id, ItemAssetKind.INSTANCE)
        container = self._require_container(operation.container_id, draft)
        self._check_container(container, definition, ItemAssetKind.INSTANCE, draft, adding=True)
        instance = ItemInstance(
            operation.asset_id,
            definition.id,
            container.id,
            operation.receipt,
            operation.data,
            operation.revision,
        )
        draft.instances[instance.id] = instance
        reference_number = self._allocate_reference(instance.id, draft)
        self._event(
            draft,
            transaction,
            context,
            "inventory.item.granted",
            definition.id,
            container.owner_id,
            {
                "asset_id": instance.id,
                "quantity": 1,
                "container_id": container.id,
                "receipt_id": operation.receipt.id,
                "reference_number": reference_number,
            },
        )

    def _consume_stack(
        self,
        operation: ConsumeStack,
        draft: _Draft,
        transaction: InventoryTransaction,
        context: RuleContext,
    ) -> None:
        if operation.quantity < 1:
            self._fail("inventory.invalid_quantity", "消耗数量必须大于 0")
        stack = self._require_stack(operation.asset_id, draft)
        self._authorize_quantity(
            stack.id,
            operation.quantity,
            operation.reservation_id,
            draft,
        )
        remaining, consumed = _take_lots(stack.lots, operation.quantity)
        owner_id = draft.containers[stack.container_id].owner_id
        if remaining:
            draft.stacks[stack.id] = replace(
                stack,
                lots=remaining,
                revision=stack.revision + 1,
            )
        else:
            del draft.stacks[stack.id]
            self._drop_reference(stack.id, draft)
            self._remove_asset_reservations(stack.id, draft)
        self._consume_reservation(
            operation.reservation_id,
            operation.quantity,
            draft,
        )
        self._event(
            draft,
            transaction,
            context,
            "inventory.item.consumed",
            stack.definition_id,
            owner_id,
            {
                "asset_id": stack.id,
                "quantity": operation.quantity,
                "remaining": stack.quantity - operation.quantity,
                "receipt_ids": tuple(lot.receipt.id for lot in consumed),
            },
            phase=ExecutionPhase.PAY_COST,
        )

    def _destroy_asset(
        self,
        operation: DestroyAsset,
        draft: _Draft,
        transaction: InventoryTransaction,
        context: RuleContext,
    ) -> None:
        asset = self._require_asset(operation.asset_id, draft)
        quantity = asset.quantity if isinstance(asset, ItemStack) else 1
        self._authorize_quantity(asset.id, quantity, operation.reservation_id, draft)
        owner_id = draft.containers[asset.container_id].owner_id
        if isinstance(asset, ItemStack):
            del draft.stacks[asset.id]
        else:
            del draft.instances[asset.id]
        self._drop_reference(asset.id, draft)
        self._remove_asset_reservations(asset.id, draft)
        self._event(
            draft,
            transaction,
            context,
            "inventory.item.destroyed",
            asset.definition_id,
            owner_id,
            {"asset_id": asset.id, "quantity": quantity},
        )

    def _consume_instance(
        self,
        operation: ConsumeInstance,
        draft: _Draft,
        transaction: InventoryTransaction,
        context: RuleContext,
    ) -> None:
        try:
            instance = draft.instances[operation.asset_id]
        except KeyError:
            self._fail(
                "inventory.instance_unknown",
                "找不到独立实例物品",
                {"asset_id": operation.asset_id},
            )
        self._authorize_quantity(instance.id, 1, operation.reservation_id, draft)
        owner_id = draft.containers[instance.container_id].owner_id
        del draft.instances[instance.id]
        self._drop_reference(instance.id, draft)
        self._remove_asset_reservations(instance.id, draft)
        self._event(
            draft,
            transaction,
            context,
            "inventory.item.consumed",
            instance.definition_id,
            owner_id,
            {
                "asset_id": instance.id,
                "quantity": 1,
                "remaining": 0,
                "receipt_ids": (instance.receipt.id,),
            },
            phase=ExecutionPhase.PAY_COST,
        )

    def _move_asset(
        self,
        operation: MoveAsset,
        draft: _Draft,
        transaction: InventoryTransaction,
        context: RuleContext,
    ) -> None:
        asset = self._require_asset(operation.asset_id, draft)
        destination = self._require_container(operation.destination_container_id, draft)
        source = draft.containers[asset.container_id]
        if source.id == destination.id:
            self._fail("inventory.same_container", "物品已经位于目标容器")
        quantity = asset.quantity if isinstance(asset, ItemStack) else 1
        self._authorize_quantity(asset.id, quantity, operation.reservation_id, draft)
        definition = self.catalog.require(asset.definition_id)
        kind = ItemAssetKind.STACK if isinstance(asset, ItemStack) else ItemAssetKind.INSTANCE
        self._check_container(destination, definition, kind, draft, adding=True)
        updated = replace(asset, container_id=destination.id, revision=asset.revision + 1)
        if isinstance(updated, ItemStack):
            draft.stacks[asset.id] = updated
        else:
            draft.instances[asset.id] = updated
        event_kind = (
            "inventory.item.transferred"
            if source.owner_id != destination.owner_id
            else "inventory.item.moved"
        )
        self._event(
            draft,
            transaction,
            context,
            event_kind,
            asset.definition_id,
            destination.owner_id,
            {
                "asset_id": asset.id,
                "quantity": quantity,
                "from_container_id": source.id,
                "to_container_id": destination.id,
                "from_owner_id": source.owner_id,
                "to_owner_id": destination.owner_id,
            },
            source_id=source.owner_id,
        )

    def _update_instance(
        self,
        operation: UpdateInstance,
        draft: _Draft,
        transaction: InventoryTransaction,
        context: RuleContext,
    ) -> None:
        try:
            instance = draft.instances[operation.instance.id]
        except KeyError:
            self._fail(
                "inventory.instance_unknown",
                "找不到要更新的独立实例物品",
                {"asset_id": operation.instance.id},
            )
        if instance.revision != operation.expected_revision:
            self._fail(
                "inventory.instance_revision_conflict",
                "物品实例版本与更新预期不一致",
                {
                    "asset_id": instance.id,
                    "expected": operation.expected_revision,
                    "actual": instance.revision,
                },
            )
        replacement = operation.instance
        if (
            replacement.id != instance.id
            or replacement.definition_id != instance.definition_id
            or replacement.container_id != instance.container_id
            or replacement.receipt != instance.receipt
        ):
            self._fail("inventory.instance_identity_changed", "实例数据更新不能改变物品身份或位置")
        draft.instances[instance.id] = replace(replacement, revision=instance.revision + 1)
        container = draft.containers[instance.container_id]
        self._event(
            draft,
            transaction,
            context,
            "inventory.item.data_updated",
            instance.definition_id,
            container.owner_id,
            {
                "asset_id": instance.id,
                "revision": instance.revision + 1,
            },
        )

    def _increase_container_space(
        self,
        operation: IncreaseContainerSpace,
        draft: _Draft,
        transaction: InventoryTransaction,
        context: RuleContext,
    ) -> None:
        container = self._require_container(operation.container_id, draft)
        if container.maximum_space is None:
            self._fail("inventory.container_space_unlimited", "无限容量容器不能使用扩容道具")
        if container.maximum_space >= operation.maximum_space:
            self._fail(
                "inventory.container_space_maximum_reached",
                "背包空间已经达到扩容上限",
                {"maximum_space": operation.maximum_space},
            )
        next_space = min(
            container.maximum_space + operation.amount,
            operation.maximum_space,
        )
        draft.containers[container.id] = replace(container, maximum_space=next_space)
        self._event(
            draft,
            transaction,
            context,
            "inventory.container.space_increased",
            container.kind,
            container.owner_id,
            {
                "container_id": container.id,
                "space_before": container.maximum_space,
                "space_after": next_space,
                "space_maximum": operation.maximum_space,
            },
        )
    def _split_stack(
        self,
        operation: SplitStack,
        draft: _Draft,
        transaction: InventoryTransaction,
        context: RuleContext,
    ) -> None:
        if operation.quantity < 1:
            self._fail("inventory.invalid_quantity", "拆分数量必须大于 0")
        self._require_new_asset_id(operation.new_asset_id, draft)
        source = self._require_stack(operation.source_asset_id, draft)
        available = source.quantity - self._reserved_quantity(source.id, draft)
        if operation.quantity > available or operation.quantity >= source.quantity:
            self._fail(
                "inventory.insufficient_quantity",
                "可拆分数量不足",
                {"asset_id": source.id, "requested": operation.quantity, "available": available},
            )
        definition = self.catalog.require(source.definition_id)
        container = draft.containers[source.container_id]
        self._check_container(container, definition, ItemAssetKind.STACK, draft, adding=True)
        remaining, moved = _take_lots(source.lots, operation.quantity)
        draft.stacks[source.id] = replace(
            source,
            lots=remaining,
            revision=source.revision + 1,
        )
        draft.stacks[operation.new_asset_id] = ItemStack(
            operation.new_asset_id,
            source.definition_id,
            source.container_id,
            moved,
        )
        reference_number = self._allocate_reference(operation.new_asset_id, draft)
        owner_id = draft.containers[source.container_id].owner_id
        self._event(
            draft,
            transaction,
            context,
            "inventory.item.split",
            source.definition_id,
            owner_id,
            {
                "source_asset_id": source.id,
                "new_asset_id": operation.new_asset_id,
                "quantity": operation.quantity,
                "reference_number": reference_number,
            },
        )

    def _swap_asset_containers(
        self,
        operation: SwapAssetContainers,
        draft: _Draft,
        transaction: InventoryTransaction,
        context: RuleContext,
    ) -> None:
        if operation.first_asset_id == operation.second_asset_id:
            self._fail("inventory.same_asset", "不能交换同一个物品资产")
        first = self._require_asset(operation.first_asset_id, draft)
        second = self._require_asset(operation.second_asset_id, draft)
        if first.container_id == second.container_id:
            self._fail("inventory.same_container", "两个物品已经位于同一容器")
        if self._reserved_quantity(first.id, draft) or self._reserved_quantity(second.id, draft):
            self._fail("inventory.asset_reserved", "存在预约的物品不能交换容器")
        first_source = draft.containers[first.container_id]
        second_source = draft.containers[second.container_id]
        first_definition = self.catalog.require(first.definition_id)
        second_definition = self.catalog.require(second.definition_id)
        first_kind = ItemAssetKind.STACK if isinstance(first, ItemStack) else ItemAssetKind.INSTANCE
        second_kind = ItemAssetKind.STACK if isinstance(second, ItemStack) else ItemAssetKind.INSTANCE
        # 两边资产数量不变，只校验目标容器的形态和标签，不检查临时容量。
        self._check_container(second_source, first_definition, first_kind, draft, adding=False)
        self._check_container(first_source, second_definition, second_kind, draft, adding=False)
        first_updated = replace(
            first,
            container_id=second_source.id,
            revision=first.revision + 1,
        )
        second_updated = replace(
            second,
            container_id=first_source.id,
            revision=second.revision + 1,
        )
        self._replace_asset(first_updated, draft)
        self._replace_asset(second_updated, draft)
        self._event(
            draft,
            transaction,
            context,
            "inventory.item.swapped",
            first.definition_id,
            second_source.owner_id,
            {
                "asset_id": first.id,
                "other_asset_id": second.id,
                "from_container_id": first_source.id,
                "to_container_id": second_source.id,
                "from_owner_id": first_source.owner_id,
                "to_owner_id": second_source.owner_id,
            },
            source_id=first_source.owner_id,
        )
        self._event(
            draft,
            transaction,
            context,
            "inventory.item.swapped",
            second.definition_id,
            first_source.owner_id,
            {
                "asset_id": second.id,
                "other_asset_id": first.id,
                "from_container_id": second_source.id,
                "to_container_id": first_source.id,
                "from_owner_id": second_source.owner_id,
                "to_owner_id": first_source.owner_id,
            },
            source_id=second_source.owner_id,
        )
    def _merge_stacks(
        self,
        operation: MergeStacks,
        draft: _Draft,
        transaction: InventoryTransaction,
        context: RuleContext,
    ) -> None:
        if operation.source_asset_id == operation.target_asset_id:
            self._fail("inventory.same_asset", "不能合并同一个物资堆")
        source = self._require_stack(operation.source_asset_id, draft)
        target = self._require_stack(operation.target_asset_id, draft)
        if source.definition_id != target.definition_id:
            self._fail("inventory.item_mismatch", "不同物品定义不能合并")
        if source.container_id != target.container_id:
            self._fail("inventory.container_mismatch", "不同容器中的物资不能直接合并")
        if self._reserved_quantity(source.id, draft) or self._reserved_quantity(target.id, draft):
            self._fail("inventory.asset_reserved", "存在预约的物资不能合并")
        definition = self.catalog.require(source.definition_id)
        self._check_stack_limit(definition, source.quantity + target.quantity)
        draft.stacks[target.id] = replace(
            target,
            lots=_coalesce_lots((*target.lots, *source.lots)),
            revision=target.revision + 1,
        )
        del draft.stacks[source.id]
        self._drop_reference(source.id, draft)
        owner_id = draft.containers[target.container_id].owner_id
        self._event(
            draft,
            transaction,
            context,
            "inventory.item.merged",
            target.definition_id,
            owner_id,
            {
                "source_asset_id": source.id,
                "target_asset_id": target.id,
                "quantity": source.quantity,
                "total": source.quantity + target.quantity,
            },
        )

    def _reserve_asset(
        self,
        operation: ReserveAsset,
        draft: _Draft,
        transaction: InventoryTransaction,
        context: RuleContext,
    ) -> None:
        if operation.reservation_id in draft.reservations:
            self._fail("inventory.reservation_exists", "预约 id 已经存在")
        asset = self._require_asset(operation.asset_id, draft)
        available = (
            asset.quantity if isinstance(asset, ItemStack) else 1
        ) - self._reserved_quantity(asset.id, draft)
        if operation.quantity < 1 or operation.quantity > available:
            self._fail(
                "inventory.insufficient_quantity",
                "可预约数量不足",
                {"asset_id": asset.id, "requested": operation.quantity, "available": available},
            )
        reservation = AssetReservation(
            operation.reservation_id,
            asset.id,
            operation.mode,
            operation.business_kind,
            operation.business_id,
            operation.quantity,
            context.logical_time,
            operation.expires_at,
        )
        draft.reservations[reservation.id] = reservation
        owner_id = draft.containers[asset.container_id].owner_id
        self._event(
            draft,
            transaction,
            context,
            "inventory.item.reserved",
            asset.definition_id,
            owner_id,
            {
                "asset_id": asset.id,
                "reservation_id": reservation.id,
                "mode": reservation.mode.value,
                "quantity": reservation.quantity,
                "business_kind": reservation.business_kind,
                "business_id": reservation.business_id,
                "expires_at": reservation.expires_at.isoformat() if reservation.expires_at else None,
            },
        )

    def _release_reservation(
        self,
        operation: ReleaseReservation,
        draft: _Draft,
        transaction: InventoryTransaction,
        context: RuleContext,
    ) -> None:
        try:
            reservation = draft.reservations.pop(operation.reservation_id)
        except KeyError:
            self._fail("inventory.reservation_unknown", "找不到要释放的预约")
        asset = self._require_asset(reservation.asset_id, draft)
        owner_id = draft.containers[asset.container_id].owner_id
        self._event(
            draft,
            transaction,
            context,
            "inventory.item.released",
            asset.definition_id,
            owner_id,
            {
                "asset_id": asset.id,
                "reservation_id": reservation.id,
                "mode": reservation.mode.value,
                "quantity": reservation.quantity,
                    "release_cause": "explicit",
            },
        )

    def _release_expired(
        self,
        draft: _Draft,
        transaction: InventoryTransaction,
        context: RuleContext,
    ) -> None:
        expired = tuple(
            value
            for value in draft.reservations.values()
            if value.expired_at(context.logical_time)
        )
        for reservation in expired:
            del draft.reservations[reservation.id]
            asset = self._require_asset(reservation.asset_id, draft)
            owner_id = draft.containers[asset.container_id].owner_id
            self._event(
                draft,
                transaction,
                context,
                "inventory.item.released",
                asset.definition_id,
                owner_id,
                {
                    "asset_id": asset.id,
                    "reservation_id": reservation.id,
                    "mode": reservation.mode.value,
                    "quantity": reservation.quantity,
                    "release_cause": "expired",
                },
            )

    def _validate_state(self, state: InventoryState) -> None:
        counts: dict[str, int] = {}
        occupied_space: dict[str, int] = {}
        for asset in (*state.stacks.values(), *state.instances.values()):
            definition = self.catalog.require(asset.definition_id)
            kind = ItemAssetKind.STACK if isinstance(asset, ItemStack) else ItemAssetKind.INSTANCE
            expected = definition.asset_kind
            if kind is not expected:
                self._fail("inventory.kind_mismatch", "库存资产形态与物品定义不一致")
            container = state.containers[asset.container_id]
            self._check_container(container, definition, kind, _Draft(
                dict(state.containers), dict(state.stacks), dict(state.instances),
                dict(state.reservations), dict(state.asset_references),
                state.next_reference_number, []
            ), adding=False)
            counts[container.id] = counts.get(container.id, 0) + 1
            if container.maximum_space is not None:
                try:
                    storage = definition.component(
                        ITEM_STORAGE_COMPONENT_ID,
                        ItemStorageComponent,
                    )
                except KeyError:
                    self._fail(
                        "inventory.storage_space_undefined",
                        "空间受限容器中的物品缺少空间占用定义",
                        {"item_id": definition.id, "container_id": container.id},
                    )
                quantity = asset.quantity if isinstance(asset, ItemStack) else 1
                occupied_space[container.id] = (
                    occupied_space.get(container.id, 0)
                    + storage.unit_space * quantity
                )
            if isinstance(asset, ItemStack):
                self._check_stack_limit(definition, asset.quantity)
        for container_id, count in counts.items():
            maximum = state.containers[container_id].maximum_assets
            if maximum is not None and count > maximum:
                self._fail("inventory.container_full", "容器资产数量超过容量")
        for container_id, used in occupied_space.items():
            maximum = state.containers[container_id].maximum_space
            if maximum is not None and used > maximum:
                self._fail(
                    "inventory.container_space_full",
                    "容器空间占用超过上限",
                    {"container_id": container_id, "used": used, "maximum": maximum},
                )

    def _check_container(
        self,
        container: ItemContainer,
        definition: ItemDefinition,
        kind: ItemAssetKind,
        draft: _Draft,
        *,
        adding: bool,
    ) -> None:
        if kind not in container.accepted_kinds:
            self._fail("inventory.container_rejected", "容器不接受该资产形态")
        if not definition.tags.allows(
            required=container.required_item_tags,
            blocked=container.blocked_item_tags,
        ):
            self._fail("inventory.container_rejected", "物品标签不符合容器策略")
        if adding and container.maximum_assets is not None:
            count = sum(
                asset.container_id == container.id
                for asset in (*draft.stacks.values(), *draft.instances.values())
            )
            if count >= container.maximum_assets:
                self._fail("inventory.container_full", "目标容器已满")

    def _require_kind(self, definition_id: StableId, kind: ItemAssetKind) -> ItemDefinition:
        try:
            definition = self.catalog.require(definition_id)
        except KeyError:
            self._fail("inventory.item_unknown", "找不到物品定义", {"item_id": definition_id})
        if definition.asset_kind is not kind:
            self._fail("inventory.kind_mismatch", "操作与物品资产形态不一致")
        return definition

    @staticmethod
    def _require_new_asset_id(asset_id: str, draft: _Draft) -> None:
        if not asset_id.strip():
            raise ValueError("物品资产 id 不能为空")
        if asset_id in draft.stacks or asset_id in draft.instances:
            InventoryEngine._fail("inventory.asset_exists", "物品资产 id 已经存在")

    @staticmethod
    def _allocate_reference(asset_id: str, draft: _Draft) -> int:
        if asset_id in draft.asset_references:
            InventoryEngine._fail("inventory.reference_exists", "物品资产已经分配编号")
        number = draft.next_reference_number
        draft.asset_references[asset_id] = number
        draft.next_reference_number += 1
        return number

    @staticmethod
    def _drop_reference(asset_id: str, draft: _Draft) -> None:
        try:
            del draft.asset_references[asset_id]
        except KeyError:
            InventoryEngine._fail("inventory.reference_unknown", "物品资产缺少稳定编号")

    @staticmethod
    def _require_container(container_id: str, draft: _Draft) -> ItemContainer:
        try:
            return draft.containers[container_id]
        except KeyError:
            InventoryEngine._fail(
                "inventory.container_unknown",
                "找不到物品容器",
                {"container_id": container_id},
            )

    @staticmethod
    def _require_stack(asset_id: str, draft: _Draft) -> ItemStack:
        try:
            return draft.stacks[asset_id]
        except KeyError:
            InventoryEngine._fail(
                "inventory.stack_unknown",
                "找不到可堆叠物资",
                {"asset_id": asset_id},
            )

    @staticmethod
    def _require_asset(asset_id: str, draft: _Draft) -> ItemStack | ItemInstance:
        if asset_id in draft.stacks:
            return draft.stacks[asset_id]
        try:
            return draft.instances[asset_id]
        except KeyError:
            InventoryEngine._fail(
                "inventory.asset_unknown",
                "找不到物品资产",
                {"asset_id": asset_id},
            )

    @staticmethod
    def _check_stack_limit(definition: ItemDefinition, quantity: int) -> None:
        if definition.stack_limit is not None and quantity > definition.stack_limit:
            InventoryEngine._fail(
                "inventory.stack_limit_exceeded",
                "物资堆数量超过定义上限",
                {"item_id": definition.id, "quantity": quantity, "limit": definition.stack_limit},
            )

    @staticmethod
    def _reserved_quantity(asset_id: str, draft: _Draft) -> int:
        return sum(
            value.quantity
            for value in draft.reservations.values()
            if value.asset_id == asset_id
        )

    def _authorize_quantity(
        self,
        asset_id: str,
        quantity: int,
        reservation_id: str | None,
        draft: _Draft,
    ) -> None:
        asset = self._require_asset(asset_id, draft)
        total = asset.quantity if isinstance(asset, ItemStack) else 1
        if quantity > total:
            self._fail("inventory.insufficient_quantity", "资产数量不足")
        reservations = tuple(
            value for value in draft.reservations.values() if value.asset_id == asset_id
        )
        if reservation_id is None:
            available = total - sum(value.quantity for value in reservations)
            if quantity > available:
                self._fail(
                    "inventory.asset_reserved",
                    "可用数量已被其他业务占用",
                    {"asset_id": asset_id, "requested": quantity, "available": available},
                )
            return
        try:
            reservation = draft.reservations[reservation_id]
        except KeyError:
            self._fail("inventory.reservation_unknown", "找不到指定预约")
        if reservation.asset_id != asset_id:
            self._fail("inventory.reservation_mismatch", "预约不属于指定资产")
        if quantity > reservation.quantity:
            self._fail("inventory.insufficient_quantity", "预约数量不足")
        other_reserved = sum(
            value.quantity for value in reservations if value.id != reservation_id
        )
        if total - quantity < other_reserved:
            self._fail("inventory.reservation_conflict", "本次操作会侵占其他预约")

    @staticmethod
    def _consume_reservation(
        reservation_id: str | None,
        quantity: int,
        draft: _Draft,
    ) -> None:
        if reservation_id is None:
            return
        reservation = draft.reservations.get(reservation_id)
        if reservation is None:
            return
        remaining = reservation.quantity - quantity
        if remaining:
            draft.reservations[reservation_id] = replace(reservation, quantity=remaining)
        else:
            del draft.reservations[reservation_id]

    @staticmethod
    def _remove_asset_reservations(asset_id: str, draft: _Draft) -> None:
        for reservation_id in tuple(draft.reservations):
            if draft.reservations[reservation_id].asset_id == asset_id:
                del draft.reservations[reservation_id]

    @staticmethod
    def _replace_asset(asset: ItemStack | ItemInstance, draft: _Draft) -> None:
        if isinstance(asset, ItemStack):
            draft.stacks[asset.id] = asset
        else:
            draft.instances[asset.id] = asset

    @staticmethod
    def _event(
        draft: _Draft,
        transaction: InventoryTransaction,
        context: RuleContext,
        kind: StableId,
        subject_id: StableId,
        target_id: str,
        values: Mapping[str, object],
        *,
        source_id: str | None = None,
        phase: ExecutionPhase = ExecutionPhase.RESOLVE,
    ) -> None:
        draft.events.append(
            RuleEvent.from_context(
                context,
                kind=kind,
                source_id=source_id or transaction.actor_id,
                target_id=target_id,
                subject_id=subject_id,
                values={
                    "transaction_id": transaction.id,
                    "reason": transaction.reason,
                    **values,
                },
                phase=phase,
            )
        )

    @staticmethod
    def _fail(
        code: StableId,
        message: str,
        details: Mapping[str, object] | None = None,
    ) -> None:
        raise RuleViolation(code, message, details or {})


def _take_lots(
    lots: tuple[ProvenanceLot, ...],
    quantity: int,
) -> tuple[tuple[ProvenanceLot, ...], tuple[ProvenanceLot, ...]]:
    """按来源批次先进先出，返回剩余批次和取走批次。"""

    wanted = quantity
    remaining: list[ProvenanceLot] = []
    taken: list[ProvenanceLot] = []
    for lot in lots:
        amount = min(wanted, lot.quantity)
        if amount:
            taken.append(ProvenanceLot(lot.receipt, amount))
            wanted -= amount
        if lot.quantity > amount:
            remaining.append(ProvenanceLot(lot.receipt, lot.quantity - amount))
    if wanted:
        raise ValueError("来源批次数量不足，库存快照已经损坏")
    return tuple(remaining), tuple(taken)


def _coalesce_lots(lots: tuple[ProvenanceLot, ...]) -> tuple[ProvenanceLot, ...]:
    """只合并相邻且收据相同的批次，保持来源消费顺序。"""

    values: list[ProvenanceLot] = []
    for lot in lots:
        if values and values[-1].receipt.id == lot.receipt.id:
            values[-1] = ProvenanceLot(values[-1].receipt, values[-1].quantity + lot.quantity)
        else:
            values.append(lot)
    return tuple(values)


__all__ = [
    "AppendStack",
    "ConsumeInstance",
    "ConsumeStack",
    "DestroyAsset",
    "GrantInstance",
    "GrantStack",
    "InventoryEngine",
    "InventoryExecution",
    "InventoryOperation",
    "InventoryTransaction",
    "MergeStacks",
    "MoveAsset",
    "ReleaseReservation",
    "ReserveAsset",
    "SplitStack",
    "SwapAssetContainers",
]
