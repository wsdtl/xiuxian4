"""世界行纪业务查询、排名与存储边界模型。"""

from __future__ import annotations

from dataclasses import dataclass

from game.core.gameplay import StableId
from game.rules.world_progress import WorldProgressState


@dataclass(frozen=True)
class WorldProgressStorageKinds:
    progress: str
    ledger: str
    reward_claim: str


@dataclass(frozen=True)
class WorldProgressRegionView:
    region_id: StableId
    points: int
    maximum_points: int
    victories: int
    claimed_milestones: tuple[int, ...]

    @property
    def percent(self) -> int:
        return self.points * 100 // self.maximum_points

    @property
    def completed(self) -> bool:
        return self.points >= self.maximum_points


@dataclass(frozen=True)
class WorldProgressView:
    character_id: str
    world_id: StableId
    regions: tuple[WorldProgressRegionView, ...]

    @property
    def points(self) -> int:
        return sum(value.points for value in self.regions)

    @property
    def maximum_points(self) -> int:
        return sum(value.maximum_points for value in self.regions)

    @property
    def completed_regions(self) -> int:
        return sum(value.completed for value in self.regions)

    @property
    def percent(self) -> int:
        return self.points * 100 // self.maximum_points if self.maximum_points else 0

    def require_region(self, region_id: str) -> WorldProgressRegionView:
        try:
            return next(value for value in self.regions if value.region_id == region_id)
        except StopIteration as exc:
            raise KeyError(f"当前世界没有这处行纪区域：{region_id}") from exc


@dataclass(frozen=True)
class WorldProgressAdvanceResult:
    status: str
    state: WorldProgressState
    added_points: int = 0
    reached_milestones: tuple[int, ...] = ()
    reward_amount: int = 0


@dataclass(frozen=True)
class WorldProgressRankEntry:
    rank: int
    character_id: str
    character_name: str
    points: int
    completed_regions: int


@dataclass(frozen=True)
class WorldProgressRankingView:
    scope_world_id: StableId | None
    entries: tuple[WorldProgressRankEntry, ...]
    own_entry: WorldProgressRankEntry | None = None


__all__ = [
    "WorldProgressAdvanceResult",
    "WorldProgressRankEntry",
    "WorldProgressRankingView",
    "WorldProgressRegionView",
    "WorldProgressStorageKinds",
    "WorldProgressView",
]
