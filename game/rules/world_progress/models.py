"""世界行纪的纯状态与阶段推进结果。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from game.core.gameplay import StableId, stable_id


WORLD_PROGRESS_AGGREGATE = "snapshot.world_progress"
WORLD_PROGRESS_RULESET_VERSION = "rules.world_progress.v1"


@dataclass(frozen=True)
class WorldProgressState:
    character_id: str
    character_name: str
    world_id: StableId
    region_id: StableId
    points: int = 0
    victories: int = 0
    claimed_milestones: tuple[int, ...] = ()
    started_at: datetime | None = None
    reached_at: datetime | None = None
    completed_at: datetime | None = None
    revision: int = 0

    def __post_init__(self) -> None:
        if not self.character_id.strip() or not self.character_name.strip():
            raise ValueError("行纪状态缺少角色身份")
        object.__setattr__(self, "world_id", stable_id(self.world_id, field="world id"))
        object.__setattr__(self, "region_id", stable_id(self.region_id, field="region id"))
        if self.points < 0 or self.victories < 0 or self.revision < 0:
            raise ValueError("行纪状态计数不能小于 0")
        milestones = tuple(int(value) for value in self.claimed_milestones)
        if milestones != tuple(sorted(set(milestones))):
            raise ValueError("行纪已领取阶段必须递增且不能重复")
        for field_name in ("started_at", "reached_at", "completed_at"):
            value = getattr(self, field_name)
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError(f"WorldProgressState.{field_name} 必须包含时区")
        if self.points == 0 and any(
            value is not None for value in (self.started_at, self.reached_at, self.completed_at)
        ):
            raise ValueError("零进度行纪不能已有推进时间")
        object.__setattr__(self, "claimed_milestones", milestones)


@dataclass(frozen=True)
class WorldProgressAdvance:
    state: WorldProgressState
    added_points: int
    reached_milestones: tuple[int, ...] = ()


def world_progress_state_id(character_id: str, world_id: str, region_id: str) -> str:
    values = tuple(str(value or "").strip() for value in (character_id, world_id, region_id))
    if any(not value for value in values):
        raise ValueError("行纪聚合身份不完整")
    return "|".join(values)


__all__ = [
    "WORLD_PROGRESS_AGGREGATE",
    "WORLD_PROGRESS_RULESET_VERSION",
    "WorldProgressAdvance",
    "WorldProgressState",
    "world_progress_state_id",
]
