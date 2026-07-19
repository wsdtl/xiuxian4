"""把抽取、扣签和堆叠物奖励组合为一次全有或全无的规则执行。"""

from __future__ import annotations

from ..context import RuleContext
from ..errors import RuleOutcome, RuleViolation
from ..inventory import (
    AppendStack,
    ConsumeStack,
    GrantStack,
    InventoryEngine,
    InventoryState,
    InventoryTransaction,
    ItemAssetKind,
    SourceReceipt,
)
from ..loot import LootState
from .engine import DrawEngine
from .models import (
    DrawInventoryCommand,
    DrawInventoryExecution,
    DrawInventoryReceipt,
    DrawItemAward,
)


class DrawInventoryEngine:
    """组合抽取与库存引擎，但不拥有两边的状态。"""

    def __init__(self, draw: DrawEngine, inventory: InventoryEngine) -> None:
        self.draw = draw
        self.inventory = inventory
        for pool_id in draw.pools.ids():
            pool = draw.pools.require(pool_id)
            ticket = inventory.catalog.require(pool.ticket_item_id)
            if ticket.asset_kind is not ItemAssetKind.STACK:
                raise ValueError(f"抽取池 {pool.id} 的抽取签必须是可堆叠物品")
            for award_id in pool.award_ids:
                award = inventory.catalog.require(award_id)
                if award.asset_kind is not ItemAssetKind.STACK:
                    raise ValueError(f"抽取池 {pool.id} 的物品奖励必须可以堆叠：{award_id}")

    def execute(
        self,
        command: DrawInventoryCommand,
        *,
        inventory_state: InventoryState,
        loot_state: LootState,
        context: RuleContext,
    ) -> RuleOutcome[DrawInventoryExecution]:
        checkpoint = context.random.checkpoint()
        try:
            self._validate(command, inventory_state)
            draw_outcome = self.draw.draw(
                command.draw,
                state=loot_state,
                context=context,
            )
            if draw_outcome.failure or draw_outcome.value is None:
                context.random.restore(checkpoint)
                return RuleOutcome.failed(draw_outcome.failure)
            draw_execution = draw_outcome.value
            award_counts: dict[str, int] = {}
            for award in draw_execution.receipt.awards:
                award_counts[award.award_id] = (
                    award_counts.get(award.award_id, 0) + award.quantity
                )
            operations: list[object] = [
                ConsumeStack(command.ticket_asset_id, command.draw.rolls)
            ]
            item_awards: list[DrawItemAward] = []
            for index, (definition_id, quantity) in enumerate(
                sorted(award_counts.items()),
                start=1,
            ):
                definition = self.inventory.catalog.require(definition_id)
                if definition.asset_kind is not ItemAssetKind.STACK:
                    self._fail(
                        "draw.non_stack_award",
                        "当前抽取结算只接受可堆叠物品奖励",
                        {"definition_id": definition_id},
                    )
                receipt = SourceReceipt(
                    f"receipt:{command.draw.id}:award:{index}",
                    "source.draw",
                    command.draw.pool_id,
                    context.logical_time,
                    {
                        "draw_command_id": command.draw.id,
                        "pool_version": draw_execution.receipt.pool_version,
                    },
                )
                existing = next(
                    (
                        stack
                        for stack in inventory_state.stacks.values()
                        if stack.definition_id == definition_id
                        and stack.container_id == command.destination_container_id
                    ),
                    None,
                )
                if existing is not None:
                    operations.append(AppendStack(existing.id, quantity, receipt))
                else:
                    operations.append(
                        GrantStack(
                            self._new_asset_id(
                                command,
                                definition_id,
                                index,
                                inventory_state,
                            ),
                            definition_id,
                            command.destination_container_id,
                            quantity,
                            receipt,
                        )
                    )
                item_awards.append(DrawItemAward(definition_id, quantity))
            transaction_id = f"{command.draw.id}:inventory"
            inventory_outcome = self.inventory.execute(
                InventoryTransaction(
                    transaction_id,
                    command.draw.actor_id,
                    "draw.settlement",
                    tuple(operations),
                ),
                state=inventory_state,
                context=context,
            )
            if inventory_outcome.failure or inventory_outcome.value is None:
                context.random.restore(checkpoint)
                return RuleOutcome.failed(inventory_outcome.failure)
            receipt = DrawInventoryReceipt(
                draw_execution.receipt,
                transaction_id,
                command.ticket_asset_id,
                command.draw.rolls,
                tuple(item_awards),
            )
            return RuleOutcome.success(
                DrawInventoryExecution(
                    inventory_outcome.value.state,
                    draw_execution.loot_state,
                    receipt,
                    (*draw_execution.events, *inventory_outcome.value.events),
                )
            )
        except RuleViolation as exc:
            context.random.restore(checkpoint)
            return RuleOutcome.failed(exc.failure)

    def _validate(self, command: DrawInventoryCommand, state: InventoryState) -> None:
        if state.revision != command.expected_inventory_revision:
            self._fail(
                "draw.inventory_revision_conflict",
                "库存版本与抽取预期不一致",
                {"expected": command.expected_inventory_revision, "actual": state.revision},
            )
        try:
            ticket = state.stacks[command.ticket_asset_id]
            destination = state.containers[command.destination_container_id]
        except KeyError as exc:
            self._fail("draw.inventory_target_missing", "抽取签或奖励容器不存在")
            raise AssertionError from exc
        pool = self.draw.pools.require(command.draw.pool_id)
        if ticket.definition_id != pool.ticket_item_id:
            self._fail("draw.ticket_mismatch", "当前物品不是此奖池使用的抽取签")
        if ticket.quantity < command.draw.rolls:
            self._fail(
                "draw.ticket_insufficient",
                "抽取签数量不足",
                {"required": command.draw.rolls, "actual": ticket.quantity},
            )
        ticket_owner = state.containers[ticket.container_id].owner_id
        if ticket_owner != command.draw.actor_id or destination.owner_id != command.draw.actor_id:
            self._fail("draw.inventory_owner_mismatch", "抽取签或奖励容器不属于当前行为人")

    @staticmethod
    def _new_asset_id(
        command: DrawInventoryCommand,
        definition_id: str,
        index: int,
        state: InventoryState,
    ) -> str:
        preferred = f"stack:{command.draw.actor_id}:{definition_id}"
        if preferred not in state.stacks and preferred not in state.instances:
            return preferred
        return f"{command.draw.id}:award:{index}"

    @staticmethod
    def _fail(code: str, message: str, details: dict[str, object] | None = None) -> None:
        raise RuleViolation(code, message, details or {})


__all__ = ["DrawInventoryEngine"]
