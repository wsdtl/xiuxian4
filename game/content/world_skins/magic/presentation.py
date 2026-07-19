"""魔法世界的武器装备名称与评分格式。"""

from ...presentation import EnemyPresentationStyle, GearPresentationStyle
from .enemies import MAGIC_ENEMY_BEHAVIOR_NAMES, MAGIC_ENEMY_PREFIXES
from .skin import MAGIC_SKIN_ID, MAGIC_SKIN_VERSION


MAGIC_GEAR_PRESENTATION = GearPresentationStyle(
    MAGIC_SKIN_ID,
    MAGIC_SKIN_VERSION,
    "{quality}·{name}",
    "魔能评分",
)

MAGIC_ENEMY_PRESENTATION = EnemyPresentationStyle(
    MAGIC_SKIN_ID,
    MAGIC_SKIN_VERSION,
    MAGIC_ENEMY_PREFIXES,
    MAGIC_ENEMY_BEHAVIOR_NAMES,
)


__all__ = ["MAGIC_ENEMY_PRESENTATION", "MAGIC_GEAR_PRESENTATION"]
