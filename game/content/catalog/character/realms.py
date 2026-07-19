"""人物等级对应的稳定境界段。"""

from __future__ import annotations

from dataclasses import dataclass

from game.core.gameplay import ContentDefinition, StableId, stable_id

from .definitions import CHARACTER_MAXIMUM_LEVEL


@dataclass(frozen=True)
class CharacterRealmDefinition:
    """境界只投影等级区间，不保存到角色快照。"""

    id: StableId
    minimum_level: int
    maximum_level: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="realm id"))
        if self.minimum_level < 1 or self.maximum_level < self.minimum_level:
            raise ValueError("人物境界等级区间无效")

    def contains(self, level: int) -> bool:
        return self.minimum_level <= level <= self.maximum_level


CHARACTER_REALMS = tuple(
    CharacterRealmDefinition(
        f"realm.character.r{index:02d}",
        1 + (index - 1) * 10,
        index * 10,
    )
    for index in range(1, 10)
) + tuple(
    CharacterRealmDefinition(
        f"realm.character.r{index:02d}",
        81 + index,
        81 + index,
    )
    for index in range(10, 20)
)

CHARACTER_REALM_DISPLAY_IDS = frozenset(realm.id for realm in CHARACTER_REALMS)
CHARACTER_REALM_CONTENT_DEFINITIONS = tuple(
    ContentDefinition(realm.id, "content.character_realm")
    for realm in CHARACTER_REALMS
)


def character_realm_for_level(level: int) -> CharacterRealmDefinition:
    """返回正式人物等级对应的境界。"""

    normalized_level = int(level)
    if not 1 <= normalized_level <= CHARACTER_MAXIMUM_LEVEL:
        raise ValueError(f"人物等级不在境界范围内: {normalized_level}")
    index = (
        (normalized_level - 1) // 10
        if normalized_level <= 90
        else normalized_level - 82
    )
    return CHARACTER_REALMS[index]


__all__ = [
    "CHARACTER_REALMS",
    "CHARACTER_REALM_CONTENT_DEFINITIONS",
    "CHARACTER_REALM_DISPLAY_IDS",
    "CharacterRealmDefinition",
    "character_realm_for_level",
]
