"""敌人、行为与遭遇公共底座。"""

from .catalog import EnemyCatalog
from .models import (
    ENCOUNTER_SCOPE_GLOBAL_ID,
    ENCOUNTER_SCOPE_PARTY_ID,
    ENCOUNTER_SCOPE_PERSONAL_ID,
    ENEMY_RANK_BOSS_ID,
    ENEMY_RANK_ELITE_ID,
    ENEMY_RANK_NORMAL_ID,
    EncounterScopeDefinition,
    EnemyBehaviorDefinition,
    EnemyDefinition,
    EnemyEncounterDefinition,
    EnemyEncounterInstance,
    EnemyInstance,
    EnemyLevelProfileDefinition,
    EnemyPhaseDefinition,
    EnemyRankDefinition,
    EnemyRewardProfileDefinition,
    EnemySpawnDefinition,
)
from .runtime import (
    EnemyCombatProjection,
    EnemyCombatProjector,
    EnemyRewardQuote,
    EnemyThreatEvaluator,
    EnemyThreatReport,
)


ENEMY_FOUNDATION_VERSION = "enemy.foundation.v1"


__all__ = [
    "ENCOUNTER_SCOPE_GLOBAL_ID",
    "ENCOUNTER_SCOPE_PARTY_ID",
    "ENCOUNTER_SCOPE_PERSONAL_ID",
    "ENEMY_FOUNDATION_VERSION",
    "ENEMY_RANK_BOSS_ID",
    "ENEMY_RANK_ELITE_ID",
    "ENEMY_RANK_NORMAL_ID",
    "EncounterScopeDefinition",
    "EnemyBehaviorDefinition",
    "EnemyCatalog",
    "EnemyCombatProjection",
    "EnemyCombatProjector",
    "EnemyDefinition",
    "EnemyEncounterDefinition",
    "EnemyEncounterInstance",
    "EnemyInstance",
    "EnemyLevelProfileDefinition",
    "EnemyPhaseDefinition",
    "EnemyRankDefinition",
    "EnemyRewardProfileDefinition",
    "EnemyRewardQuote",
    "EnemySpawnDefinition",
    "EnemyThreatEvaluator",
    "EnemyThreatReport",
]
