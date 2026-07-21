"""世界行纪的纯计分和一次性阶段判定。"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from game.content.catalog.world_progress import WorldProgressDefinition

from .models import WorldProgressAdvance, WorldProgressState


def advance_world_progress(
    state: WorldProgressState,
    encounter_kind: str,
    *,
    definition: WorldProgressDefinition,
    logical_time: datetime,
) -> WorldProgressAdvance:
    if logical_time.tzinfo is None or logical_time.utcoffset() is None:
        raise ValueError("行纪推进时间必须包含时区")
    if state.points >= definition.maximum_points:
        return WorldProgressAdvance(state, 0)
    added = min(
        definition.points_for(encounter_kind),
        definition.maximum_points - state.points,
    )
    points = state.points + added
    reached = tuple(
        milestone.percent
        for milestone in definition.milestones
        if milestone.percent not in state.claimed_milestones
        and state.points < definition.threshold(milestone) <= points
    )
    current = replace(
        state,
        points=points,
        victories=state.victories + 1,
        claimed_milestones=(*state.claimed_milestones, *reached),
        started_at=state.started_at or logical_time,
        reached_at=logical_time,
        completed_at=(
            logical_time
            if points == definition.maximum_points and state.completed_at is None
            else state.completed_at
        ),
        revision=state.revision + 1,
    )
    return WorldProgressAdvance(current, added, reached)


__all__ = ["advance_world_progress"]
