"""角色规则的初始化数值入口；正式人物名录是唯一来源。"""

from game.content.catalog.character.definitions import (
    INITIAL_CORE_ATTRIBUTES,
    LEVEL_CORE_ATTRIBUTE_DELTAS,
    character_level_milestone,
    character_level_milestones,
)

__all__ = [
    "INITIAL_CORE_ATTRIBUTES",
    "LEVEL_CORE_ATTRIBUTE_DELTAS",
    "character_level_milestone",
    "character_level_milestones",
]
