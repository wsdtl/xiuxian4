"""世界行纪的稳定计分与阶段奖励参数。"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from ..item import DIMENSION_SHIFT_ITEM_ID, DRAW_TICKET_ITEM_ID


@dataclass(frozen=True)
class WorldProgressItemReward:
    definition_id: str
    quantity: int = 1

    def __post_init__(self) -> None:
        if not self.definition_id.strip():
            raise ValueError("行纪物品奖励缺少正式物品 ID")
        if self.quantity < 1:
            raise ValueError("行纪物品奖励数量必须大于 0")


@dataclass(frozen=True)
class WorldProgressMilestone:
    percent: int
    currency_amount: int
    item_rewards: tuple[WorldProgressItemReward, ...] = ()

    def __post_init__(self) -> None:
        if not 1 <= self.percent <= 100:
            raise ValueError("行纪阶段必须位于 1% 到 100%")
        if self.currency_amount < 1:
            raise ValueError("行纪阶段奖励必须大于 0")
        item_rewards = tuple(self.item_rewards)
        if len({value.definition_id for value in item_rewards}) != len(item_rewards):
            raise ValueError("同一行纪阶段不能重复声明物品奖励")
        object.__setattr__(self, "item_rewards", item_rewards)


@dataclass(frozen=True)
class WorldProgressDefinition:
    maximum_points: int
    victory_points: Mapping[str, int]
    milestones: tuple[WorldProgressMilestone, ...]
    world_completion_rewards: tuple[WorldProgressItemReward, ...] = ()

    def __post_init__(self) -> None:
        if self.maximum_points < 1:
            raise ValueError("行纪区域满进度必须大于 0")
        points = {str(key): int(value) for key, value in self.victory_points.items()}
        if set(points) != {"normal", "elite", "boss"} or any(
            value < 1 for value in points.values()
        ):
            raise ValueError("行纪必须完整定义普通、精英和首领胜利分值")
        milestones = tuple(self.milestones)
        percents = tuple(value.percent for value in milestones)
        if percents != tuple(sorted(set(percents))) or percents[-1] != 100:
            raise ValueError("行纪阶段必须递增、不重复并以 100% 收尾")
        world_rewards = tuple(self.world_completion_rewards)
        if len({value.definition_id for value in world_rewards}) != len(world_rewards):
            raise ValueError("行纪世界圆满不能重复声明物品奖励")
        object.__setattr__(self, "victory_points", MappingProxyType(points))
        object.__setattr__(self, "milestones", milestones)
        object.__setattr__(self, "world_completion_rewards", world_rewards)

    def points_for(self, encounter_kind: str) -> int:
        try:
            return self.victory_points[str(encounter_kind)]
        except KeyError as exc:
            raise ValueError(f"行纪不接受该遭遇类型：{encounter_kind}") from exc

    def threshold(self, milestone: WorldProgressMilestone) -> int:
        return self.maximum_points * milestone.percent // 100


# 常规区域在满胜率下约需 8.4 小时；首领偏向区域约需 5.6 小时。
WORLD_PROGRESS_DEFINITION = WorldProgressDefinition(
    maximum_points=100,
    victory_points={"normal": 1, "elite": 2, "boss": 5},
    milestones=(
        WorldProgressMilestone(25, 25),
        WorldProgressMilestone(50, 50),
        WorldProgressMilestone(75, 100),
        WorldProgressMilestone(
            100,
            200,
            (WorldProgressItemReward(DRAW_TICKET_ITEM_ID),),
        ),
    ),
    world_completion_rewards=(
        WorldProgressItemReward(DIMENSION_SHIFT_ITEM_ID),
    ),
)


__all__ = [
    "WORLD_PROGRESS_DEFINITION",
    "WorldProgressDefinition",
    "WorldProgressItemReward",
    "WorldProgressMilestone",
]
