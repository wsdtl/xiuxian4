"""抽取池规则：复用掉落引擎，不负责背包扣签和奖励入账。"""

from __future__ import annotations

from ..context import RuleContext
from ..errors import RuleOutcome, RuleViolation
from ..loot import LootEngine, LootRollCommand, LootState
from .models import DrawCommand, DrawExecution, DrawPoolCatalog, DrawReceipt


class DrawEngine:
    """把可信抽取池翻译为掉落抽取结果。"""

    def __init__(self, pools: DrawPoolCatalog, loot: LootEngine) -> None:
        if not pools.finalized:
            raise RuntimeError("抽取池名录必须先完成校验")
        self.pools = pools
        self.loot = loot

    def draw(
        self,
        command: DrawCommand,
        *,
        state: LootState,
        context: RuleContext,
    ) -> RuleOutcome[DrawExecution]:
        checkpoint = context.random.checkpoint()
        try:
            if state.owner_id != command.actor_id:
                self._fail("draw.owner_mismatch", "抽取状态不属于当前行为人")
            if state.revision != command.expected_loot_revision:
                self._fail(
                    "draw.revision_conflict",
                    "抽取状态版本与事务预期不一致",
                    {"expected": command.expected_loot_revision, "actual": state.revision},
                )
            pool = self.pools.require(command.pool_id)
            loot_command = LootRollCommand(
                command.id,
                command.actor_id,
                pool.loot_table_id,
                command.expected_loot_revision,
                command.rolls,
            )
            outcome = self.loot.roll(loot_command, state=state, context=context)
            if outcome.failure or outcome.value is None:
                return RuleOutcome.failed(outcome.failure)
            execution = outcome.value
            if execution.receipt.empty_count:
                self._fail(
                    "draw.empty_award",
                    "抽取池不能产生空奖",
                    {"pool_id": pool.id, "empty_count": execution.receipt.empty_count},
                )
            invalid = sorted(
                {
                    award.award_id
                    for award in execution.receipt.awards
                    if award.award_id not in pool.award_ids
                }
            )
            if invalid:
                self._fail(
                    "draw.award_outside_pool",
                    "抽取结果不在抽取池可信名录中",
                    {"award_id": invalid[0]},
                )
            receipt = DrawReceipt(
                command.id,
                command.actor_id,
                pool.id,
                pool.version,
                pool.ticket_item_id,
                command.rolls,
                execution.receipt.awards,
                execution.receipt,
            )
            return RuleOutcome.success(
                DrawExecution(execution.state, receipt, execution.events)
            )
        except RuleViolation as exc:
            context.random.restore(checkpoint)
            return RuleOutcome.failed(exc.failure)

    @staticmethod
    def _fail(code: str, message: str, details: dict[str, object] | None = None) -> None:
        raise RuleViolation(code, message, details or {})


__all__ = ["DrawEngine"]
