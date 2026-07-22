"""伙伴成长在外层业务事务中的持久化协调。"""

from game.rules.companion import (
    CompanionExperienceResult,
    CompanionGrowthEngine,
    CompanionRosterState,
)


class CompanionGrowthSettlement:
    def __init__(self, snapshots, roster_aggregate: str, engine: CompanionGrowthEngine) -> None:
        self.snapshots = snapshots
        self.roster_aggregate = roster_aggregate
        self.engine = engine

    def grant_in_uow(
        self,
        uow,
        character_id: str,
        companion_id: str | None,
        amount: int,
        *,
        character_level: int,
        logical_time,
    ) -> CompanionExperienceResult | None:
        if companion_id is None or amount <= 0:
            return None
        roster = self.snapshots.load(
            uow,
            self.roster_aggregate,
            character_id,
            CompanionRosterState,
        )
        if roster is None or companion_id not in roster.instances:
            return None
        next_roster, result = self.engine.grant_experience(
            roster,
            companion_id,
            amount,
            character_level=character_level,
        )
        if next_roster != roster:
            self.snapshots.update(
                uow,
                self.roster_aggregate,
                character_id,
                roster,
                next_roster,
                logical_time,
            )
        return result


__all__ = ["CompanionGrowthSettlement"]
