"""首批探险区域、敌人生态与掉落倾向。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from game.core.gameplay import StableId, stable_id

from ..character import CHARACTER_MAXIMUM_LEVEL
from ..enemy.definitions import BOSS_ENEMIES, REGULAR_ENEMIES
from ..enemy.loot import (
    BOSS_ENEMY_LOOT_TABLE_ID,
    ELITE_ENEMY_LOOT_TABLE_ID,
    NORMAL_ENEMY_LOOT_TABLE_ID,
)
from ..item.trophies import REGION_TROPHY_ITEM_IDS, REGION_TROPHY_WEIGHTS
from ..world import (
    BLACK_WIND_RAVINE_ID,
    BROKEN_PILLAR_RELIC_ID,
    GREEN_CLOUD_PLAIN_ID,
    HEAVENLY_CRAFT_RELIC_ID,
    KUNLUN_SKY_RUINS_ID,
    MIRROR_LAKE_MARSH_ID,
    MYRIAD_SWORD_TOMB_ID,
    NORTHERN_ABYSS_SNOWFIELD_ID,
    RETURNING_RUIN_ABYSS_ID,
    SCARLET_FLAME_VALLEY_ID,
    SUNSET_RIDGE_ID,
    THUNDER_MARSH_STEPPE_ID,
    VERDANT_WILDERNESS_ID,
)


EXPLORATION_CONTENT_VERSION = "exploration.content.v1"
EXPLORATION_BATCH_SECONDS = 10 * 60


class ExplorationRegionKind(str, Enum):
    REGULAR = "regular"
    WEAPON_FOCUS = "weapon_focus"
    EQUIPMENT_FOCUS = "equipment_focus"
    BOSS_FOCUS = "boss_focus"


@dataclass(frozen=True)
class ExplorationEncounterWeights:
    normal: int
    elite: int
    boss: int
    empty: int = 0

    def __post_init__(self) -> None:
        values = (self.normal, self.elite, self.boss, self.empty)
        if any(value < 0 for value in values) or sum(values) < 1:
            raise ValueError("探险遭遇权重必须包含至少一个正权重")


@dataclass(frozen=True)
class ExplorationRegionDefinition:
    id: StableId
    location_id: StableId
    kind: ExplorationRegionKind
    minimum_enemy_level: int
    maximum_enemy_level: int
    regular_enemy_ids: frozenset[StableId]
    boss_enemy_ids: frozenset[StableId]
    encounter_weights: ExplorationEncounterWeights
    trophy_item_ids: tuple[StableId, ...]
    trophy_weights: tuple[int, ...] = REGION_TROPHY_WEIGHTS
    loot_modifiers: Mapping[StableId, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="exploration region id"))
        object.__setattr__(self, "location_id", stable_id(self.location_id, field="location id"))
        object.__setattr__(self, "kind", ExplorationRegionKind(self.kind))
        if not (
            1
            <= self.minimum_enemy_level
            <= self.maximum_enemy_level
            <= CHARACTER_MAXIMUM_LEVEL
        ):
            raise ValueError(
                f"探险区域敌人等级必须位于 1 到 {CHARACTER_MAXIMUM_LEVEL}"
            )
        regular = frozenset(stable_id(value, field="enemy id") for value in self.regular_enemy_ids)
        bosses = frozenset(stable_id(value, field="boss enemy id") for value in self.boss_enemy_ids)
        if not regular or not bosses:
            raise ValueError("探险区域必须同时拥有常规敌人和首领池")
        trophies = tuple(
            stable_id(value, field="trophy item id")
            for value in self.trophy_item_ids
        )
        weights = tuple(int(value) for value in self.trophy_weights)
        if not trophies or len(trophies) != len(weights) or any(value < 1 for value in weights):
            raise ValueError("探险区域战利品与权重必须一一对应且全部大于 0")
        modifiers = {
            stable_id(key, field="loot entry id"): int(value)
            for key, value in self.loot_modifiers.items()
        }
        if any(not 0 <= value <= 100_000 for value in modifiers.values()):
            raise ValueError("探险掉落修正必须位于 0 到 100000 基点")
        object.__setattr__(self, "regular_enemy_ids", regular)
        object.__setattr__(self, "boss_enemy_ids", bosses)
        object.__setattr__(self, "trophy_item_ids", trophies)
        object.__setattr__(self, "trophy_weights", weights)
        object.__setattr__(self, "loot_modifiers", MappingProxyType(modifiers))

    def enemy_level(self, character_level: int) -> int:
        return min(self.maximum_enemy_level, max(self.minimum_enemy_level, int(character_level)))

    def loot_table_id(self, encounter_kind: str) -> StableId:
        return {
            "normal": NORMAL_ENEMY_LOOT_TABLE_ID,
            "elite": ELITE_ENEMY_LOOT_TABLE_ID,
            "boss": BOSS_ENEMY_LOOT_TABLE_ID,
        }[encounter_kind]


class ExplorationRegionCatalog:
    def __init__(self, definitions: tuple[ExplorationRegionDefinition, ...]) -> None:
        values = {definition.id: definition for definition in definitions}
        if len(values) != len(definitions):
            raise ValueError("探险区域稳定 ID 不能重复")
        locations = [definition.location_id for definition in definitions]
        if len(locations) != len(set(locations)):
            raise ValueError("同一个地点不能登记多个探险区域")
        self._definitions = MappingProxyType(values)
        self._by_location = MappingProxyType(
            {definition.location_id: definition for definition in definitions}
        )

    def require(self, region_id: StableId) -> ExplorationRegionDefinition:
        key = stable_id(region_id, field="exploration region id")
        try:
            return self._definitions[key]
        except KeyError as exc:
            raise KeyError(f"未知探险区域：{key}") from exc

    def for_location(self, location_id: StableId) -> ExplorationRegionDefinition:
        key = stable_id(location_id, field="location id")
        try:
            return self._by_location[key]
        except KeyError as exc:
            raise KeyError(f"地点不是探险区域：{key}") from exc

    def definitions(self) -> tuple[ExplorationRegionDefinition, ...]:
        return tuple(self._definitions.values())

    def validate(self, content) -> None:
        known_locations = set(content.world.locations.ids())
        known_enemies = set(content.enemies.definitions.ids())
        known_items = set(content.items.definitions.ids())
        for definition in self._definitions.values():
            if definition.location_id not in known_locations:
                raise KeyError(f"探险区域引用未知地点：{definition.location_id}")
            unknown = (definition.regular_enemy_ids | definition.boss_enemy_ids) - known_enemies
            if unknown:
                raise KeyError(f"探险区域引用未知敌人：{', '.join(sorted(unknown))}")
            unknown_trophies = set(definition.trophy_item_ids) - known_items
            if unknown_trophies:
                raise KeyError(
                    f"探险区域引用未知战利品：{', '.join(sorted(unknown_trophies))}"
                )


_REGULAR_IDS = tuple(value.id for value in REGULAR_ENEMIES)
_BOSS_IDS = tuple(value.id for value in BOSS_ENEMIES)


def _regular_region(index: int, location_id: str, low: int, high: int):
    offset = index * 6
    boss_offset = index * 3
    return ExplorationRegionDefinition(
        f"exploration.region.r{index + 1}",
        location_id,
        ExplorationRegionKind.REGULAR,
        low,
        high,
        frozenset(_REGULAR_IDS[offset : offset + 6]),
        frozenset(_BOSS_IDS[boss_offset : boss_offset + 3]),
        ExplorationEncounterWeights(68, 24, 3, 5),
        REGION_TROPHY_ITEM_IDS[location_id],
    )


REGULAR_EXPLORATION_REGIONS = tuple(
    _regular_region(index, *values)
    for index, values in enumerate(
        (
            (GREEN_CLOUD_PLAIN_ID, 1, 12),
            (SUNSET_RIDGE_ID, 8, 22),
            (BLACK_WIND_RAVINE_ID, 18, 32),
            (MIRROR_LAKE_MARSH_ID, 28, 42),
            (SCARLET_FLAME_VALLEY_ID, 38, 52),
            (VERDANT_WILDERNESS_ID, 48, 62),
            (THUNDER_MARSH_STEPPE_ID, 58, 72),
            (NORTHERN_ABYSS_SNOWFIELD_ID, 68, 82),
            (BROKEN_PILLAR_RELIC_ID, 78, 92),
            (KUNLUN_SKY_RUINS_ID, 88, 100),
        )
    )
)

SPECIAL_EXPLORATION_REGIONS = (
    ExplorationRegionDefinition(
        "exploration.region.weapon_focus",
        MYRIAD_SWORD_TOMB_ID,
        ExplorationRegionKind.WEAPON_FOCUS,
        30,
        100,
        frozenset(_REGULAR_IDS[index] for index in (0, 1, 8, 12, 15, 16, 20, 21, 22, 23, 26, 37, 38, 40, 50, 51, 57)),
        frozenset(_BOSS_IDS[:30]),
        ExplorationEncounterWeights(45, 45, 5, 5),
        REGION_TROPHY_ITEM_IDS[MYRIAD_SWORD_TOMB_ID],
        loot_modifiers={
            "loot_entry.enemy.elite.equipment": 7_000,
            "loot_entry.enemy.elite.weapon": 30_000,
            "loot_entry.enemy.boss.equipment": 7_000,
            "loot_entry.enemy.boss.weapon": 30_000,
        },
    ),
    ExplorationRegionDefinition(
        "exploration.region.equipment_focus",
        HEAVENLY_CRAFT_RELIC_ID,
        ExplorationRegionKind.EQUIPMENT_FOCUS,
        50,
        100,
        frozenset(_REGULAR_IDS[index] for index in (5, 11, 17, 24, 31, 36, 39, 43, 44, 53, 59)),
        frozenset(_BOSS_IDS[:30]),
        ExplorationEncounterWeights(45, 45, 5, 5),
        REGION_TROPHY_ITEM_IDS[HEAVENLY_CRAFT_RELIC_ID],
        loot_modifiers={
            "loot_entry.enemy.normal.equipment": 20_000,
            "loot_entry.enemy.elite.equipment": 20_000,
            "loot_entry.enemy.elite.weapon": 5_000,
            "loot_entry.enemy.boss.equipment": 20_000,
            "loot_entry.enemy.boss.weapon": 5_000,
        },
    ),
    ExplorationRegionDefinition(
        "exploration.region.boss_focus",
        RETURNING_RUIN_ABYSS_ID,
        ExplorationRegionKind.BOSS_FOCUS,
        80,
        100,
        frozenset(_REGULAR_IDS[-12:]),
        frozenset(_BOSS_IDS[:30]),
        ExplorationEncounterWeights(10, 45, 40, 5),
        REGION_TROPHY_ITEM_IDS[RETURNING_RUIN_ABYSS_ID],
    ),
)

EXPLORATION_REGIONS = (*REGULAR_EXPLORATION_REGIONS, *SPECIAL_EXPLORATION_REGIONS)
EXPLORATION_REGION_CATALOG = ExplorationRegionCatalog(EXPLORATION_REGIONS)


__all__ = [
    "EXPLORATION_BATCH_SECONDS",
    "EXPLORATION_CONTENT_VERSION",
    "EXPLORATION_REGION_CATALOG",
    "EXPLORATION_REGIONS",
    "ExplorationEncounterWeights",
    "ExplorationRegionCatalog",
    "ExplorationRegionDefinition",
    "ExplorationRegionKind",
    "REGULAR_EXPLORATION_REGIONS",
    "SPECIAL_EXPLORATION_REGIONS",
]
