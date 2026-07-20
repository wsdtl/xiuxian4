"""抽取池规则：复用掉落引擎，不负责背包扣签和奖励入账。"""

from __future__ import annotations

from ..context import RuleContext
from ..errors import RuleOutcome, RuleViolation
from dataclasses import replace

from ..events import RuleEvent
from ..loot import LootAward, LootEngine, LootRollCommand, LootState
from .models import (
    DrawCommand,
    DrawExecution,
    DrawGuaranteeDecision,
    DrawGuaranteeSlotDefinition,
    DrawPoolCatalog,
    DrawReceipt,
)


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
            guaranteed_awards, guarantee_decisions, guaranteed_state, guarantee_events = (
                self._apply_guarantee_slots(
                    pool.guarantee_slots,
                    command,
                    execution.state,
                    execution.receipt.awards,
                    context,
                )
            )
            awards = tuple(
                sorted(
                    (*execution.receipt.awards, *guaranteed_awards),
                    key=lambda value: (value.roll_index, value.draw_index, value.group_id),
                )
            )
            receipt = DrawReceipt(
                command.id,
                command.actor_id,
                pool.id,
                pool.version,
                pool.ticket_item_id,
                command.rolls,
                awards,
                execution.receipt,
                guarantee_decisions,
            )
            return RuleOutcome.success(
                DrawExecution(
                    guaranteed_state,
                    receipt,
                    (*execution.events, *guarantee_events),
                )
            )
        except RuleViolation as exc:
            context.random.restore(checkpoint)
            return RuleOutcome.failed(exc.failure)

    @staticmethod
    def _apply_guarantee_slots(
        slots: tuple[DrawGuaranteeSlotDefinition, ...],
        command: DrawCommand,
        state: LootState,
        normal_awards: tuple[LootAward, ...],
        context: RuleContext,
    ) -> tuple[
        tuple[LootAward, ...],
        tuple[DrawGuaranteeDecision, ...],
        LootState,
        tuple[RuleEvent, ...],
    ]:
        if not slots:
            return (), (), state, ()
        counters = dict(state.pity_counters)
        bonus_awards: list[LootAward] = []
        decisions: list[DrawGuaranteeDecision] = []
        events: list[RuleEvent] = []
        awards_by_roll = {
            roll_index: tuple(
                value for value in normal_awards if value.roll_index == roll_index
            )
            for roll_index in range(command.rolls)
        }
        for roll_index in range(command.rolls):
            for slot_index, slot in enumerate(slots):
                before = int(counters.get(slot.id, 0))
                naturally_satisfied = any(
                    value.award_id in slot.qualifying_award_ids
                    for value in awards_by_roll[roll_index]
                )
                if naturally_satisfied:
                    counters[slot.id] = 0
                    decisions.append(
                        DrawGuaranteeDecision(
                            slot.id,
                            roll_index,
                            before,
                            0,
                            naturally_satisfied=True,
                        )
                    )
                    continue
                progressed = before + 1
                if progressed < slot.threshold:
                    counters[slot.id] = progressed
                    decisions.append(
                        DrawGuaranteeDecision(
                            slot.id,
                            roll_index,
                            before,
                            progressed,
                        )
                    )
                    continue
                total = sum(value.weight for value in slot.entries)
                sampled = context.random.randint(1, total)
                selected = slot.entries[-1]
                cursor = 0
                for entry in slot.entries:
                    cursor += entry.weight
                    if sampled <= cursor:
                        selected = entry
                        break
                award = LootAward(
                    roll_index,
                    1_000 + slot_index,
                    slot.id,
                    selected.id,
                    selected.award_id,
                    selected.quantity,
                )
                bonus_awards.append(award)
                counters[slot.id] = 0
                decisions.append(
                    DrawGuaranteeDecision(
                        slot.id,
                        roll_index,
                        before,
                        0,
                        forced=True,
                        entry_id=selected.id,
                        award_id=selected.award_id,
                        sampled=sampled,
                        scale=total,
                    )
                )
                events.append(
                    RuleEvent.from_context(
                        context,
                        kind="draw.guarantee_triggered",
                        source_id=command.actor_id,
                        target_id=command.actor_id,
                        subject_id=slot.id,
                        values={
                            "roll_index": roll_index,
                            "threshold": slot.threshold,
                            "award_id": selected.award_id,
                            "quantity": selected.quantity,
                        },
                    )
                )
        return (
            tuple(bonus_awards),
            tuple(decisions),
            replace(state, pity_counters=counters),
            tuple(events),
        )

    @staticmethod
    def _fail(code: str, message: str, details: dict[str, object] | None = None) -> None:
        raise RuleViolation(code, message, details or {})


__all__ = ["DrawEngine"]
