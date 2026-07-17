"""普通、精英、首领和世界首领的基础遭遇样板。"""

from game.core.gameplay import (
    ENCOUNTER_SCOPE_GLOBAL_ID,
    ENCOUNTER_SCOPE_PARTY_ID,
    ENCOUNTER_SCOPE_PERSONAL_ID,
    ENEMY_RANK_BOSS_ID,
    ENEMY_RANK_ELITE_ID,
    ENEMY_RANK_NORMAL_ID,
    EncounterScopeDefinition,
    EnemyEncounterDefinition,
    EnemySpawnDefinition,
    TagSet,
)

from .definitions import BOSS_ENEMIES, REGULAR_ENEMIES


PERSONAL_NORMAL_ENCOUNTER_ID = "encounter.enemy.personal.normal"
PERSONAL_ELITE_ENCOUNTER_ID = "encounter.enemy.personal.elite"
PERSONAL_BOSS_ENCOUNTER_ID = "encounter.enemy.personal.boss"
PARTY_BOSS_ENCOUNTER_ID = "encounter.enemy.party.boss"
GLOBAL_BOSS_ENCOUNTER_ID = "encounter.enemy.global.boss"


ENCOUNTER_SCOPES = (
    EncounterScopeDefinition(ENCOUNTER_SCOPE_PERSONAL_ID, 1, False),
    EncounterScopeDefinition(ENCOUNTER_SCOPE_PARTY_ID, 6, False),
    EncounterScopeDefinition(ENCOUNTER_SCOPE_GLOBAL_ID, None, True),
)

_REGULAR_IDS = frozenset(value.id for value in REGULAR_ENEMIES)
_BOSS_IDS = tuple(value.id for value in BOSS_ENEMIES)


ENEMY_ENCOUNTERS = (
    EnemyEncounterDefinition(
        PERSONAL_NORMAL_ENCOUNTER_ID,
        ENCOUNTER_SCOPE_PERSONAL_ID,
        1,
        100,
        (EnemySpawnDefinition(_REGULAR_IDS, ENEMY_RANK_NORMAL_ID, 1, 3, 1),),
        TagSet.of("encounter.enemy.normal"),
    ),
    EnemyEncounterDefinition(
        PERSONAL_ELITE_ENCOUNTER_ID,
        ENCOUNTER_SCOPE_PERSONAL_ID,
        1,
        100,
        (EnemySpawnDefinition(_REGULAR_IDS, ENEMY_RANK_ELITE_ID, 1, 1, 2),),
        TagSet.of("encounter.enemy.elite"),
    ),
    EnemyEncounterDefinition(
        PERSONAL_BOSS_ENCOUNTER_ID,
        ENCOUNTER_SCOPE_PERSONAL_ID,
        1,
        100,
        (EnemySpawnDefinition(frozenset(_BOSS_IDS[:30]), ENEMY_RANK_BOSS_ID, 1, 1, 3),),
        TagSet.of("encounter.enemy.boss"),
    ),
    EnemyEncounterDefinition(
        PARTY_BOSS_ENCOUNTER_ID,
        ENCOUNTER_SCOPE_PARTY_ID,
        1,
        100,
        (EnemySpawnDefinition(frozenset(_BOSS_IDS[20:50]), ENEMY_RANK_BOSS_ID, 1, 1, 4),),
        TagSet.of("encounter.enemy.boss", "encounter.party"),
    ),
    EnemyEncounterDefinition(
        GLOBAL_BOSS_ENCOUNTER_ID,
        ENCOUNTER_SCOPE_GLOBAL_ID,
        1,
        100,
        (EnemySpawnDefinition(frozenset(_BOSS_IDS[50:]), ENEMY_RANK_BOSS_ID, 1, 1, 5),),
        TagSet.of("encounter.enemy.boss", "encounter.global"),
    ),
)


ENCOUNTER_DISPLAY_IDS = frozenset(
    {*(value.id for value in ENCOUNTER_SCOPES), *(value.id for value in ENEMY_ENCOUNTERS)}
)


__all__ = [
    "ENCOUNTER_DISPLAY_IDS",
    "ENCOUNTER_SCOPES",
    "ENEMY_ENCOUNTERS",
    "GLOBAL_BOSS_ENCOUNTER_ID",
    "PARTY_BOSS_ENCOUNTER_ID",
    "PERSONAL_BOSS_ENCOUNTER_ID",
    "PERSONAL_ELITE_ENCOUNTER_ID",
    "PERSONAL_NORMAL_ENCOUNTER_ID",
]
