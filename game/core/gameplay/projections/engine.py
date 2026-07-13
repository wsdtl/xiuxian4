"""稳定并列规则的不可变排名快照构造。"""

from __future__ import annotations

from datetime import datetime

from .models import (
    RankingCandidate,
    RankingDirection,
    RankingEntry,
    RankingSnapshot,
)


class RankingEngine:
    def freeze(
        self,
        *,
        board_id: str,
        scope_id: str,
        period_id: str,
        version: int,
        direction: RankingDirection,
        candidates: tuple[RankingCandidate, ...],
        frozen_at: datetime,
        through_fact_offset: int,
        limit: int | None = None,
    ) -> RankingSnapshot:
        if limit is not None and limit < 1:
            raise ValueError("排名限制必须大于 0")
        if len({candidate.subject_id for candidate in candidates}) != len(candidates):
            raise ValueError("排名候选主体不能重复")
        direction = RankingDirection(direction)
        if direction is RankingDirection.DESCENDING:
            ordered = sorted(
                candidates,
                key=lambda value: (-value.score, value.tie_value, value.subject_id),
            )
        else:
            ordered = sorted(
                candidates,
                key=lambda value: (value.score, value.tie_value, value.subject_id),
            )
        if limit is not None:
            ordered = ordered[:limit]
        entries = tuple(
            RankingEntry(index, value.subject_id, value.score, value.tie_value)
            for index, value in enumerate(ordered, 1)
        )
        return RankingSnapshot(
            board_id,
            scope_id,
            period_id,
            version,
            direction,
            entries,
            frozen_at,
            through_fact_offset,
        )


__all__ = ["RankingEngine"]
