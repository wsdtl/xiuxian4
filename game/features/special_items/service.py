"""背包扩容与装备套装保证物品的原子使用服务。"""

from dataclasses import replace
from hashlib import sha256

from game.core.gameplay import (
    EQUIPMENT_SET_GUARANTEE_ITEM_COMPONENT_ID,
    ITEM_CONTAINER_CAPACITY_COMPONENT_ID,
    ConsumeStack,
    ContainerCapacityItemComponent,
    EquipmentSetGuaranteeItemComponent,
    IncreaseContainerSpace,
    InventoryEngine,
    InventoryState,
    InventoryTransaction,
    ItemCatalog,
    ItemStack,
    RuleEvent,
    RuleOutcome,
    RuleViolation,
)
from game.rules.equipment import (
    EQUIPMENT_SET_GUARANTEE_AGGREGATE,
    EquipmentSetGuaranteeState,
    activate_equipment_set_guarantee,
)

from .models import (
    SpecialItemUseCommand,
    SpecialItemUseReceipt,
    special_item_use_fingerprint,
)


BACKPACK_CAPACITY_EFFECT_KIND = "special_item.backpack_capacity"
EQUIPMENT_SET_GUARANTEE_EFFECT_KIND = "special_item.equipment_set_guarantee"


class SpecialItemUseService:
    """在一个工作单元中提交道具扣除及其长期效果。"""

    def __init__(
        self,
        database,
        items: ItemCatalog,
        inventory_engine: InventoryEngine,
        snapshots,
        inventory_aggregate: str,
    ) -> None:
        self.database = database
        self.items = items
        self.inventory_engine = inventory_engine
        self.snapshots = snapshots
        self.inventory_aggregate = inventory_aggregate

    def use(
        self,
        command: SpecialItemUseCommand,
        *,
        inventory_id: str,
        context,
    ) -> RuleOutcome[SpecialItemUseReceipt]:
        if not inventory_id.strip():
            raise ValueError("inventory_id 不能为空")
        checkpoint = context.random.checkpoint()
        try:
            with self.database.unit_of_work() as uow:
                fingerprint = _persistence_fingerprint(command, inventory_id)
                committed = uow.load_transaction(command.id)
                if committed is not None:
                    if committed.fingerprint != fingerprint or committed.scope_id != command.actor_id:
                        raise ValueError(
                            f"同一特殊物品事务 ID 对应不同内容：{command.id}"
                        )
                    receipt = self.snapshots.codec.loads(
                        committed.receipt_payload,
                        SpecialItemUseReceipt,
                    )
                    if (
                        receipt.transaction_id != command.id
                        or receipt.actor_id != command.actor_id
                        or receipt.item_asset_id != command.item_asset_id
                    ):
                        raise RuntimeError("特殊物品事务表、请求与回执身份不一致")
                    return RuleOutcome.success(replace(receipt, replayed=True))

                inventory = self.snapshots.require(
                    uow,
                    self.inventory_aggregate,
                    inventory_id,
                    InventoryState,
                )
                try:
                    next_inventory, previous_guarantee, next_guarantee, receipt, events = (
                        self._execute(command, inventory, uow, context)
                    )
                except RuleViolation as exc:
                    context.random.restore(checkpoint)
                    return RuleOutcome.failed(exc.failure)

                self.snapshots.update(
                    uow,
                    self.inventory_aggregate,
                    inventory_id,
                    inventory,
                    next_inventory,
                    context.logical_time,
                )
                if next_guarantee is not None:
                    if previous_guarantee is None:
                        self.snapshots.insert(
                            uow,
                            EQUIPMENT_SET_GUARANTEE_AGGREGATE,
                            command.actor_id,
                            next_guarantee,
                            context.logical_time,
                        )
                    else:
                        self.snapshots.update(
                            uow,
                            EQUIPMENT_SET_GUARANTEE_AGGREGATE,
                            command.actor_id,
                            previous_guarantee,
                            next_guarantee,
                            context.logical_time,
                        )
                timestamp = context.logical_time.isoformat()
                uow.insert_transaction(
                    command.id,
                    fingerprint,
                    command.actor_id,
                    self.snapshots.codec.dumps(receipt),
                    timestamp,
                )
                for sequence, event in enumerate(events):
                    uow.append_outbox(
                        command.id,
                        sequence,
                        event.kind,
                        self.snapshots.codec.dumps(event),
                        timestamp,
                    )
                uow.commit()
                return RuleOutcome.success(receipt)
        except Exception:
            context.random.restore(checkpoint)
            raise

    def _execute(self, command, inventory, uow, context):
        try:
            item_asset = inventory.asset(command.item_asset_id)
        except KeyError as exc:
            raise RuleViolation("special_item.item_unknown", "找不到要使用的特殊物品") from exc
        if not isinstance(item_asset, ItemStack):
            self._fail("special_item.item_not_stack", "特殊物品必须是可堆叠物品")
        if inventory.owner_of(item_asset.id) != command.actor_id:
            self._fail("special_item.item_owner_mismatch", "特殊物品不属于当前角色")
        if inventory.available_quantity(item_asset.id) < 1:
            self._fail("special_item.item_unavailable", "特殊物品当前被其他流程占用")
        definition = self.items.require(item_asset.definition_id)
        capacity = definition.components.get(ITEM_CONTAINER_CAPACITY_COMPONENT_ID)
        guarantee = definition.components.get(EQUIPMENT_SET_GUARANTEE_ITEM_COMPONENT_ID)
        previous_guarantee = None
        next_guarantee = None

        if isinstance(capacity, ContainerCapacityItemComponent):
            try:
                container = next(
                    value
                    for value in inventory.containers.values()
                    if value.kind == capacity.container_kind
                )
            except StopIteration as exc:
                raise RuleViolation("special_item.container_unknown", "找不到要扩容的背包") from exc
            if container.maximum_space is None:
                self._fail("special_item.container_unlimited", "该背包不需要扩容")
            value_before = container.maximum_space
            operations = (
                ConsumeStack(item_asset.id, 1),
                IncreaseContainerSpace(
                    container.id,
                    capacity.amount,
                    capacity.maximum_space,
                ),
            )
            effect_kind = BACKPACK_CAPACITY_EFFECT_KIND
            value_after = min(value_before + capacity.amount, capacity.maximum_space)
            extra_events = ()
        elif isinstance(guarantee, EquipmentSetGuaranteeItemComponent):
            previous_guarantee = self.snapshots.load(
                uow,
                EQUIPMENT_SET_GUARANTEE_AGGREGATE,
                command.actor_id,
                EquipmentSetGuaranteeState,
            )
            current_guarantee = previous_guarantee or EquipmentSetGuaranteeState(
                command.actor_id
            )
            try:
                next_guarantee = activate_equipment_set_guarantee(
                    current_guarantee,
                    guarantee,
                )
            except ValueError as exc:
                raise RuleViolation("special_item.guarantee_already_active", str(exc)) from exc
            value_before = current_guarantee.charges
            value_after = next_guarantee.charges
            operations = (ConsumeStack(item_asset.id, 1),)
            effect_kind = EQUIPMENT_SET_GUARANTEE_EFFECT_KIND
            extra_events = (
                RuleEvent.from_context(
                    context,
                    kind="equipment.set_guarantee.activated",
                    source_id=item_asset.id,
                    target_id=command.actor_id,
                    subject_id=definition.id,
                    values={
                        "charges_before": value_before,
                        "charges_after": value_after,
                    },
                ),
            )
        else:
            self._fail("special_item.component_missing", "物品不是可由该服务使用的特殊物品")

        inventory_outcome = self.inventory_engine.execute(
            InventoryTransaction(
                f"{command.id}:inventory",
                command.actor_id,
                "special_item.use",
                operations,
            ),
            state=inventory,
            context=context,
        )
        if inventory_outcome.failure:
            raise RuleViolation(
                inventory_outcome.failure.code,
                inventory_outcome.failure.message,
                inventory_outcome.failure.details,
            )
        assert inventory_outcome.value is not None
        receipt = SpecialItemUseReceipt(
            command.id,
            command.actor_id,
            item_asset.id,
            definition.id,
            effect_kind,
            value_before,
            value_after,
        )
        return (
            inventory_outcome.value.state,
            previous_guarantee,
            next_guarantee,
            receipt,
            (*inventory_outcome.value.events, *extra_events),
        )

    @staticmethod
    def _fail(code: str, message: str) -> None:
        raise RuleViolation(code, message)


def _persistence_fingerprint(command: SpecialItemUseCommand, inventory_id: str) -> str:
    payload = f"{special_item_use_fingerprint(command)}|{inventory_id}"
    return sha256(payload.encode("utf-8")).hexdigest()


__all__ = [
    "BACKPACK_CAPACITY_EFFECT_KIND",
    "EQUIPMENT_SET_GUARANTEE_EFFECT_KIND",
    "SpecialItemUseService",
]
