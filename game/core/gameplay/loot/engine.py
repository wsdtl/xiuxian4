"""确定性掉落、空结果、批量抽取和保底推进。"""

from __future__ import annotations

from ..context import RuleContext
from ..errors import RuleOutcome, RuleViolation
from ..events import RuleEvent
from .models import (
    LOOT_CHANCE_SCALE,
    LOOT_MODIFIER_SCALE,
    LootAward,
    LootCatalog,
    LootDecision,
    LootEntry,
    LootExecution,
    LootGroup,
    LootGroupMode,
    LootRollCommand,
    LootRollReceipt,
    LootState,
    LootTableDefinition,
)


class LootEngine:
    def __init__(self, catalog: LootCatalog) -> None:
        if not catalog.finalized:
            catalog.finalize()
        self.catalog = catalog

    def roll(
        self,
        command: LootRollCommand,
        *,
        state: LootState,
        context: RuleContext,
    ) -> RuleOutcome[LootExecution]:
        checkpoint = context.random.checkpoint()
        try:
            if state.owner_id != command.actor_id:
                self._fail("loot.owner_mismatch", "掉落状态不属于当前行为人")
            if state.revision != command.expected_revision:
                self._fail(
                    "loot.revision_conflict",
                    "掉落状态版本与事务预期不一致",
                    {"expected": command.expected_revision, "actual": state.revision},
                )
            table = self.catalog.require(command.table_id)
            pity_before = int(state.pity_counters.get(table.id, 0))
            pity = pity_before
            awards: list[LootAward] = []
            decisions: list[LootDecision] = []
            empty_count = 0
            for roll_index in range(command.rolls):
                roll_awards: list[LootAward] = []
                for group in table.groups:
                    group_awards, group_decisions, group_empty = self._roll_group(
                        table,
                        group,
                        command,
                        pity,
                        roll_index,
                        context,
                    )
                    roll_awards.extend(group_awards)
                    decisions.extend(group_decisions)
                    empty_count += group_empty
                awards.extend(roll_awards)
                pity = self._next_pity(table, pity, roll_awards)
            counters = dict(state.pity_counters)
            if table.pity is not None:
                counters[table.id] = pity
            next_state = LootState(state.owner_id, counters, state.revision + 1)
            receipt = LootRollReceipt(
                command.id,
                command.actor_id,
                table.id,
                table.version,
                tuple(awards),
                tuple(decisions),
                empty_count,
                pity_before,
                pity,
                context.logical_time,
                context.trace_id,
            )
            event = RuleEvent.from_context(
                context,
                kind="loot.rolled",
                source_id=command.actor_id,
                target_id=command.actor_id,
                subject_id=table.id,
                values={
                    "command_id": command.id,
                    "table_version": table.version,
                    "rolls": command.rolls,
                    "award_count": len(awards),
                    "empty_count": empty_count,
                    "pity_before": pity_before,
                    "pity_after": pity,
                },
            )
            return RuleOutcome.success(LootExecution(next_state, receipt, (event,)))
        except RuleViolation as exc:
            context.random.restore(checkpoint)
            return RuleOutcome.failed(exc.failure)

    def _roll_group(
        self,
        table: LootTableDefinition,
        group: LootGroup,
        command: LootRollCommand,
        pity: int,
        roll_index: int,
        context: RuleContext,
    ) -> tuple[list[LootAward], list[LootDecision], int]:
        entries = [entry for entry in group.entries if entry.eligible(context.effective_tags)]
        if not entries:
            self._fail(
                "loot.no_eligible_entries",
                "掉落组没有符合条件的条目",
                {"group_id": group.id},
            )
        if group.mode is LootGroupMode.WEIGHTED_ONE:
            return self._weighted(table, group, entries, command, pity, roll_index, context)
        if group.mode is LootGroupMode.INDEPENDENT:
            return self._independent(group, entries, command, roll_index, context)
        return self._all(group, entries, roll_index, context)

    def _weighted(
        self,
        table: LootTableDefinition,
        group: LootGroup,
        entries: list[LootEntry],
        command: LootRollCommand,
        pity: int,
        roll_index: int,
        context: RuleContext,
    ) -> tuple[list[LootAward], list[LootDecision], int]:
        awards: list[LootAward] = []
        decisions: list[LootDecision] = []
        empty = 0
        remaining = list(entries)
        for draw_index in range(group.draws):
            forced = bool(
                table.pity
                and table.pity.group_id == group.id
                and pity >= table.pity.threshold - 1
                and draw_index == 0
            )
            candidates = remaining
            if forced:
                candidates = [
                    entry
                    for entry in remaining
                    if entry.id in table.pity.guaranteed_entry_ids
                ]
            weighted = [
                (entry, self._modified(entry.weight, command, entry.id))
                for entry in candidates
            ]
            weighted = [(entry, weight) for entry, weight in weighted if weight > 0]
            if not weighted:
                self._fail(
                    "loot.no_positive_weight",
                    "掉落组没有正权重候选",
                    {"group_id": group.id, "forced": forced},
                )
            total = sum(weight for _, weight in weighted)
            sampled = context.random.randint(1, total)
            selected = weighted[-1][0]
            cursor = 0
            for entry, weight in weighted:
                cursor += weight
                if sampled <= cursor:
                    selected = entry
                    break
            decisions.append(
                LootDecision(
                    roll_index,
                    draw_index,
                    group.id,
                    selected.id,
                    sampled,
                    total,
                    True,
                    forced,
                )
            )
            award = self._award(selected, group.id, roll_index, draw_index, context)
            if award is None:
                empty += 1
            else:
                awards.append(award)
            if group.unique:
                remaining.remove(selected)
        return awards, decisions, empty

    def _independent(
        self,
        group: LootGroup,
        entries: list[LootEntry],
        command: LootRollCommand,
        roll_index: int,
        context: RuleContext,
    ) -> tuple[list[LootAward], list[LootDecision], int]:
        awards: list[LootAward] = []
        decisions: list[LootDecision] = []
        empty = 0
        for draw_index in range(group.draws):
            any_hit = False
            for entry in entries:
                chance = min(
                    LOOT_CHANCE_SCALE,
                    self._modified(entry.chance, command, entry.id),
                )
                sampled = context.random.randint(1, LOOT_CHANCE_SCALE)
                hit = sampled <= chance
                decisions.append(
                    LootDecision(
                        roll_index,
                        draw_index,
                        group.id,
                        entry.id,
                        sampled,
                        LOOT_CHANCE_SCALE,
                        hit,
                    )
                )
                if not hit:
                    continue
                any_hit = True
                award = self._award(entry, group.id, roll_index, draw_index, context)
                if award is not None:
                    awards.append(award)
            if not any_hit:
                empty += 1
        return awards, decisions, empty

    def _all(
        self,
        group: LootGroup,
        entries: list[LootEntry],
        roll_index: int,
        context: RuleContext,
    ) -> tuple[list[LootAward], list[LootDecision], int]:
        awards: list[LootAward] = []
        decisions: list[LootDecision] = []
        empty = 0
        for draw_index in range(group.draws):
            draw_has_award = False
            for entry in entries:
                decisions.append(
                    LootDecision(roll_index, draw_index, group.id, entry.id, 1, 1, True)
                )
                award = self._award(entry, group.id, roll_index, draw_index, context)
                if award is not None:
                    awards.append(award)
                    draw_has_award = True
            if not draw_has_award:
                empty += 1
        return awards, decisions, empty

    @staticmethod
    def _award(
        entry: LootEntry,
        group_id: str,
        roll_index: int,
        draw_index: int,
        context: RuleContext,
    ) -> LootAward | None:
        if entry.award_id is None:
            return None
        quantity = context.random.randint(entry.minimum_quantity, entry.maximum_quantity)
        return LootAward(
            roll_index,
            draw_index,
            group_id,
            entry.id,
            entry.award_id,
            quantity,
        )

    @staticmethod
    def _modified(value: int, command: LootRollCommand, entry_id: str) -> int:
        basis_points = command.modifier_basis_points.get(entry_id, LOOT_MODIFIER_SCALE)
        return value * basis_points // LOOT_MODIFIER_SCALE

    @staticmethod
    def _next_pity(
        table: LootTableDefinition,
        current: int,
        awards: list[LootAward],
    ) -> int:
        if table.pity is None:
            return current
        if any(award.entry_id in table.pity.qualifying_entry_ids for award in awards):
            return 0
        return min(current + 1, table.pity.threshold - 1)

    @staticmethod
    def _fail(code: str, message: str, details: dict[str, object] | None = None) -> None:
        raise RuleViolation(code, message, details or {})


__all__ = ["LootEngine"]
