"""魔法世界的武器装备名称与评分格式。"""

from ...presentation import EnemyPresentationStyle, GearPresentationStyle
from .enemies import MAGIC_ENEMY_BEHAVIOR_NAMES, MAGIC_ENEMY_PREFIXES
from .skin import MAGIC_SKIN_ID


MAGIC_GEAR_PRESENTATION = GearPresentationStyle(
    MAGIC_SKIN_ID,
    9,
    "{quality}·{name}",
    "魔能评分",
)

MAGIC_ENEMY_PRESENTATION = EnemyPresentationStyle(
    MAGIC_SKIN_ID,
    9,
    MAGIC_ENEMY_PREFIXES,
    MAGIC_ENEMY_BEHAVIOR_NAMES,
)


__all__ = ["MAGIC_ENEMY_PRESENTATION", "MAGIC_GEAR_PRESENTATION"]
