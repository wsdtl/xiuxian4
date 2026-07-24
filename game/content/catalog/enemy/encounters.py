"""个人探险与组队挑战互斥的正式遭遇样板。"""

from game.core.gameplay import (
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

from .definitions import PERSONAL_BOSS_ENEMIES, REGULAR_ENEMIES
from .party import PARTY_BOSS_ENEMIES


PERSONAL_NORMAL_ENCOUNTER_ID = "encounter.enemy.personal.normal"
PERSONAL_ELITE_ENCOUNTER_ID = "encounter.enemy.personal.elite"
PERSONAL_BOSS_ENCOUNTER_ID = "encounter.enemy.personal.boss"
PARTY_BOSS_ENCOUNTER_ID = "encounter.enemy.party.boss"


ENCOUNTER_SCOPES = (
    EncounterScopeDefinition(ENCOUNTER_SCOPE_PERSONAL_ID, 1, False),
    EncounterScopeDefinition(ENCOUNTER_SCOPE_PARTY_ID, 6, False),
)

_REGULAR_IDS = frozenset(value.id for value in REGULAR_ENEMIES)
_PERSONAL_BOSS_IDS = frozenset(value.id for value in PERSONAL_BOSS_ENEMIES)
_PARTY_BOSS_IDS = frozenset(value.id for value in PARTY_BOSS_ENEMIES)


ENEMY_ENCOUNTERS = (
    EnemyEncounterDefinition(
        PERSONAL_NORMAL_ENCOUNTER_ID,
        ENCOUNTER_SCOPE_PERSONAL_ID,
        1,
        100,
        (EnemySpawnDefinition(_REGULAR_IDS, ENEMY_RANK_NORMAL_ID, 1, 1, 1),),
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
        (
            EnemySpawnDefinition(
                _PERSONAL_BOSS_IDS,
                ENEMY_RANK_BOSS_ID,
                1,
                1,
                3,
                (0.65, 0.30),
            ),
        ),
        TagSet.of("encounter.enemy.boss"),
    ),
    EnemyEncounterDefinition(
        PARTY_BOSS_ENCOUNTER_ID,
        ENCOUNTER_SCOPE_PARTY_ID,
        1,
        100,
        (
            EnemySpawnDefinition(
                _PARTY_BOSS_IDS,
                ENEMY_RANK_BOSS_ID,
                1,
                1,
                4,
                (0.70, 0.35),
            ),
        ),
        TagSet.of("encounter.enemy.boss", "encounter.party"),
    ),
)


def _validate() -> None:
    overlap = _PERSONAL_BOSS_IDS & _PARTY_BOSS_IDS
    if overlap:
        raise ValueError(
            "个人首领与组队首领不能共享身份：" + ", ".join(sorted(overlap))
        )


_validate()


ENCOUNTER_DISPLAY_IDS = frozenset(
    {*(value.id for value in ENCOUNTER_SCOPES), *(value.id for value in ENEMY_ENCOUNTERS)}
)


__all__ = [
    "ENCOUNTER_DISPLAY_IDS",
    "ENCOUNTER_SCOPES",
    "ENEMY_ENCOUNTERS",
    "PARTY_BOSS_ENCOUNTER_ID",
    "PERSONAL_BOSS_ENCOUNTER_ID",
    "PERSONAL_ELITE_ENCOUNTER_ID",
    "PERSONAL_NORMAL_ENCOUNTER_ID",
]
