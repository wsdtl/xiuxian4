"""正式游戏命令共享的紧凑展示规则。"""

from __future__ import annotations

from datetime import datetime

from game.content import CHARACTER_LEVEL_PROGRESSION_ID, character_realm_for_level
from game.core.gameplay import CharacterState, SkinProjector
from game.rules.character import CharacterSettingsState


MOOD_HEADER_COLORS = (
    "#FF8C00",
    "#9ACD32",
    "#1ABC9C",
    "#2980B9",
    "#8E44AD",
    "#9B59B6",
    "#FF69B4",
)


def character_level(character: CharacterState) -> int:
    """读取人物主等级，不依赖成长轨道遍历顺序。"""

    return character.progressions[CHARACTER_LEVEL_PROGRESSION_ID].level


def character_header_parts(
    character: CharacterState,
    projector: SkinProjector,
) -> tuple[str, str, str]:
    """构造不主动换行的“境界短名 + 名字 + 等级”人物头。"""

    level = character_level(character)
    realm = character_realm_for_level(level)
    return (
        projector.compact_name(realm.id),
        f" {character.name}",
        f" Lv{level}",
    )


def character_realm_name(
    character: CharacterState,
    projector: SkinProjector,
) -> str:
    """读取角色详情使用的完整境界名。"""

    return projector.name(character_realm_for_level(character_level(character)).id)


def character_header_color(
    settings: CharacterSettingsState,
    logical_time: datetime,
) -> str:
    """按角色开关和星期返回已验证的人物头颜色。"""

    if not settings.mood_header_enabled:
        return ""
    return MOOD_HEADER_COLORS[logical_time.weekday()]


__all__ = [
    "MOOD_HEADER_COLORS",
    "character_header_color",
    "character_header_parts",
    "character_level",
    "character_realm_name",
]
