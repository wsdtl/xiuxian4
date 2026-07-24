"""普通、精英与个人首领的正式敌人内容。"""

from game.core.gameplay import (
    COMBAT_ATTACK,
    COMBAT_DEFENSE,
    COMBAT_SPEED,
    HEALTH_MAXIMUM,
    SPIRIT_MAXIMUM,
    BattleAiRule,
    AttributeGrant,
    ContributionSpec,
    ENEMY_RANK_BOSS_ID,
    ENEMY_RANK_ELITE_ID,
    ENEMY_RANK_NORMAL_ID,
    EnemyDefinition,
    EnemyLevelProfileDefinition,
    EnemyRankDefinition,
    EnemyRewardProfileDefinition,
    ModifierLayer,
    TagSet,
)

from ..combat.definitions import BASIC_ATTACK_ABILITY_ID
from ..combat.stats import COMBAT_CONTROL_RESISTANCE, COMBAT_TENACITY
from .blueprints import PERSONAL_BOSS_BLUEPRINTS, REGULAR_ENEMY_BLUEPRINTS
from .loot import (
    BOSS_ENEMY_LOOT_TABLE_ID,
    ELITE_ENEMY_LOOT_TABLE_ID,
    NORMAL_ENEMY_LOOT_TABLE_ID,
)


STANDARD_ENEMY_LEVEL_PROFILE_ID = "enemy.level.standard"
NORMAL_ENEMY_REWARD_PROFILE_ID = "enemy.reward.normal"
ELITE_ENEMY_REWARD_PROFILE_ID = "enemy.reward.elite"
BOSS_ENEMY_REWARD_PROFILE_ID = "enemy.reward.boss"


def _levels(formula) -> tuple[float, ...]:
    return tuple(round(float(formula(level)), 2) for level in range(1, 101))


STANDARD_ENEMY_LEVEL_PROFILE = EnemyLevelProfileDefinition(
    STANDARD_ENEMY_LEVEL_PROFILE_ID,
    {
        HEALTH_MAXIMUM: _levels(lambda level: 70 + 9 * (level - 1) + 0.03 * (level - 1) ** 2),
        SPIRIT_MAXIMUM: _levels(lambda level: 100 + 2 * (level - 1)),
        COMBAT_ATTACK: _levels(lambda level: 7 + 0.9 * (level - 1)),
        COMBAT_DEFENSE: _levels(lambda level: 0.5 * (level - 1)),
        COMBAT_SPEED: _levels(lambda _level: 100),
        COMBAT_CONTROL_RESISTANCE: _levels(lambda _level: 0),
        COMBAT_TENACITY: _levels(lambda _level: 0),
    },
)


ENEMY_REWARD_PROFILES = (
    EnemyRewardProfileDefinition(
        NORMAL_ENEMY_REWARD_PROFILE_ID,
        7.0,
        2.0,
        NORMAL_ENEMY_LOOT_TABLE_ID,
        1,
    ),
    EnemyRewardProfileDefinition(
        ELITE_ENEMY_REWARD_PROFILE_ID,
        11.0,
        4.0,
        ELITE_ENEMY_LOOT_TABLE_ID,
        1,
    ),
    EnemyRewardProfileDefinition(
        BOSS_ENEMY_REWARD_PROFILE_ID,
        28.0,
        9.0,
        BOSS_ENEMY_LOOT_TABLE_ID,
        1,
    ),
)


ENEMY_RANKS = (
    EnemyRankDefinition(
        ENEMY_RANK_NORMAL_ID,
        {HEALTH_MAXIMUM: 1.0, COMBAT_ATTACK: 1.0, COMBAT_DEFENSE: 1.0, COMBAT_SPEED: 1.0},
        minimum_behaviors=1,
        maximum_behaviors=1,
        threat_multiplier=1.0,
        reward_profile_id=NORMAL_ENEMY_REWARD_PROFILE_ID,
    ),
    EnemyRankDefinition(
        ENEMY_RANK_ELITE_ID,
        {HEALTH_MAXIMUM: 1.8, COMBAT_ATTACK: 1.2, COMBAT_DEFENSE: 1.15, COMBAT_SPEED: 1.05},
        contribution=ContributionSpec(
            attributes=(
                AttributeGrant(COMBAT_CONTROL_RESISTANCE, ModifierLayer.GLOBAL_FLAT, 0.05),
            ),
        ),
        minimum_behaviors=2,
        maximum_behaviors=3,
        threat_multiplier=1.8,
        reward_profile_id=ELITE_ENEMY_REWARD_PROFILE_ID,
    ),
    EnemyRankDefinition(
        ENEMY_RANK_BOSS_ID,
        {
            HEALTH_MAXIMUM: 6.0,
            COMBAT_ATTACK: 1.35,
            COMBAT_DEFENSE: 1.3,
            COMBAT_SPEED: 1.08,
        },
        contribution=ContributionSpec(
            attributes=(
                AttributeGrant(COMBAT_CONTROL_RESISTANCE, ModifierLayer.GLOBAL_FLAT, 0.25),
                AttributeGrant(COMBAT_TENACITY, ModifierLayer.GLOBAL_FLAT, 0.20),
            ),
        ),
        minimum_behaviors=3,
        maximum_behaviors=5,
        threat_multiplier=4.0,
        reward_profile_id=None,
    ),
)


_BASIC_AI = (
    BattleAiRule(
        "ai.enemy.basic_attack",
        BASIC_ATTACK_ABILITY_ID,
        "target.enemy.first",
        priority=0,
        maximum_targets=1,
    ),
)


def _regular_enemy(blueprint) -> EnemyDefinition:
    return EnemyDefinition(
        f"enemy.{blueprint.key}",
        STANDARD_ENEMY_LEVEL_PROFILE_ID,
        NORMAL_ENEMY_REWARD_PROFILE_ID,
        frozenset({ENEMY_RANK_NORMAL_ID, ENEMY_RANK_ELITE_ID}),
        base_contribution=ContributionSpec(
            tags=TagSet.of("enemy.identity.regular"),
            abilities=frozenset({BASIC_ATTACK_ABILITY_ID}),
        ),
        base_ai_rules=_BASIC_AI,
        tags=TagSet.of("enemy.identity.regular"),
    )


def _personal_boss_enemy(blueprint) -> EnemyDefinition:
    return EnemyDefinition(
        f"enemy.boss.{blueprint.key}",
        STANDARD_ENEMY_LEVEL_PROFILE_ID,
        BOSS_ENEMY_REWARD_PROFILE_ID,
        frozenset({ENEMY_RANK_BOSS_ID}),
        base_contribution=ContributionSpec(
            tags=TagSet.of("enemy.identity.boss"),
            abilities=frozenset({BASIC_ATTACK_ABILITY_ID}),
        ),
        base_ai_rules=_BASIC_AI,
        tags=TagSet.of("enemy.identity.boss"),
    )


REGULAR_ENEMIES = tuple(_regular_enemy(value) for value in REGULAR_ENEMY_BLUEPRINTS)
PERSONAL_BOSS_ENEMIES = tuple(
    _personal_boss_enemy(value)
    for value in PERSONAL_BOSS_BLUEPRINTS
)
ENEMY_DEFINITIONS = (*REGULAR_ENEMIES, *PERSONAL_BOSS_ENEMIES)


ENEMY_DEFINITION_DISPLAY_IDS = frozenset(value.id for value in ENEMY_DEFINITIONS)
ENEMY_RANK_DISPLAY_IDS = frozenset(value.id for value in ENEMY_RANKS)


__all__ = [
    "BOSS_ENEMY_REWARD_PROFILE_ID",
    "ELITE_ENEMY_REWARD_PROFILE_ID",
    "ENEMY_DEFINITIONS",
    "ENEMY_DEFINITION_DISPLAY_IDS",
    "ENEMY_RANKS",
    "ENEMY_RANK_DISPLAY_IDS",
    "ENEMY_REWARD_PROFILES",
    "NORMAL_ENEMY_REWARD_PROFILE_ID",
    "PERSONAL_BOSS_ENEMIES",
    "REGULAR_ENEMIES",
    "STANDARD_ENEMY_LEVEL_PROFILE",
    "STANDARD_ENEMY_LEVEL_PROFILE_ID",
]
