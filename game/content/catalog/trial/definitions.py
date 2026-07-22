"""构筑试炼的固定模式、目标数值和无掉落占位身份。"""

from game.core.gameplay import (
    COMBAT_ATTACK,
    COMBAT_DEFENSE,
    COMBAT_SPEED,
    HEALTH_MAXIMUM,
    SPIRIT_MAXIMUM,
    BattleAiRule,
    ContributionSpec,
    EnemyDefinition,
    EnemyLevelProfileDefinition,
    EnemyRankDefinition,
    EnemyRewardProfileDefinition,
    TagSet,
)

from ..combat.definitions import BASIC_ATTACK_ABILITY_ID
from ..combat.stats import COMBAT_CONTROL_RESISTANCE, COMBAT_TENACITY
from .models import BuildTrialCatalog, BuildTrialModeDefinition


BUILD_TRIAL_SINGLE_ID = "trial.mode.single"
BUILD_TRIAL_GROUP_ID = "trial.mode.group"
BUILD_TRIAL_ENDURANCE_ID = "trial.mode.endurance"

BUILD_TRIAL_RANK_ID = "enemy.rank.build_trial"
BUILD_TRIAL_REWARD_PROFILE_ID = "enemy.reward.build_trial"

BUILD_TRIAL_SINGLE_TARGET_ID = "enemy.build_trial.single"
BUILD_TRIAL_GROUP_TARGET_ID = "enemy.build_trial.group"
BUILD_TRIAL_ENDURANCE_TARGET_ID = "enemy.build_trial.endurance"


def _levels(formula) -> tuple[float, ...]:
    return tuple(round(float(formula(level)), 2) for level in range(1, 101))


BUILD_TRIAL_LEVEL_PROFILES = (
    EnemyLevelProfileDefinition(
        "enemy.level.build_trial.single",
        {
            HEALTH_MAXIMUM: _levels(lambda level: 320 + 32 * (level - 1)),
            SPIRIT_MAXIMUM: _levels(lambda _level: 100),
            COMBAT_ATTACK: _levels(lambda level: 3 + 0.25 * (level - 1)),
            COMBAT_DEFENSE: _levels(lambda level: 0.25 * (level - 1)),
            COMBAT_SPEED: _levels(lambda _level: 100),
            COMBAT_CONTROL_RESISTANCE: _levels(lambda _level: 0.10),
            COMBAT_TENACITY: _levels(lambda _level: 0.05),
        },
    ),
    EnemyLevelProfileDefinition(
        "enemy.level.build_trial.group",
        {
            HEALTH_MAXIMUM: _levels(lambda level: 80 + 8 * (level - 1)),
            SPIRIT_MAXIMUM: _levels(lambda _level: 100),
            COMBAT_ATTACK: _levels(lambda level: 2 + 0.18 * (level - 1)),
            COMBAT_DEFENSE: _levels(lambda level: 0.10 * (level - 1)),
            COMBAT_SPEED: _levels(lambda _level: 100),
            COMBAT_CONTROL_RESISTANCE: _levels(lambda _level: 0),
            COMBAT_TENACITY: _levels(lambda _level: 0),
        },
    ),
    EnemyLevelProfileDefinition(
        "enemy.level.build_trial.endurance",
        {
            HEALTH_MAXIMUM: _levels(lambda _level: 1_000_000),
            SPIRIT_MAXIMUM: _levels(lambda _level: 100),
            COMBAT_ATTACK: _levels(lambda level: 5 + 0.55 * (level - 1)),
            COMBAT_DEFENSE: _levels(lambda level: 0.20 * (level - 1)),
            COMBAT_SPEED: _levels(lambda _level: 100),
            COMBAT_CONTROL_RESISTANCE: _levels(lambda _level: 0.25),
            COMBAT_TENACITY: _levels(lambda _level: 0.20),
        },
    ),
)


BUILD_TRIAL_RANK = EnemyRankDefinition(
    BUILD_TRIAL_RANK_ID,
    {
        HEALTH_MAXIMUM: 1.0,
        COMBAT_ATTACK: 1.0,
        COMBAT_DEFENSE: 1.0,
        COMBAT_SPEED: 1.0,
    },
    minimum_behaviors=0,
    maximum_behaviors=0,
    threat_multiplier=1.0,
    reward_profile_id=None,
)


BUILD_TRIAL_REWARD_PROFILE = EnemyRewardProfileDefinition(
    BUILD_TRIAL_REWARD_PROFILE_ID,
    0,
    0,
    None,
    0,
)


_BASIC_AI = (
    BattleAiRule(
        "ai.build_trial.basic_attack",
        BASIC_ATTACK_ABILITY_ID,
        "target.enemy.first",
        priority=0,
        maximum_targets=1,
    ),
)


def _target(target_id: str, level_profile_id: str) -> EnemyDefinition:
    return EnemyDefinition(
        target_id,
        level_profile_id,
        BUILD_TRIAL_REWARD_PROFILE_ID,
        frozenset({BUILD_TRIAL_RANK_ID}),
        base_contribution=ContributionSpec(
            tags=TagSet.of("enemy.identity.build_trial"),
            abilities=frozenset({BASIC_ATTACK_ABILITY_ID}),
        ),
        base_ai_rules=_BASIC_AI,
        tags=TagSet.of("enemy.identity.build_trial"),
    )


BUILD_TRIAL_TARGETS = (
    _target(BUILD_TRIAL_SINGLE_TARGET_ID, "enemy.level.build_trial.single"),
    _target(BUILD_TRIAL_GROUP_TARGET_ID, "enemy.level.build_trial.group"),
    _target(BUILD_TRIAL_ENDURANCE_TARGET_ID, "enemy.level.build_trial.endurance"),
)


BUILD_TRIAL_MODES = (
    BuildTrialModeDefinition(
        BUILD_TRIAL_SINGLE_ID,
        "单体",
        "检验爆发、暴击、穿透与单体循环",
        BUILD_TRIAL_SINGLE_TARGET_ID,
        "单体校准体",
        1,
        40,
        240,
        "build-trial.v1.single",
    ),
    BuildTrialModeDefinition(
        BUILD_TRIAL_GROUP_ID,
        "群体",
        "检验溅射、连锁、击败触发与群体续航",
        BUILD_TRIAL_GROUP_TARGET_ID,
        "群体校准体",
        5,
        50,
        600,
        "build-trial.v1.group",
    ),
    BuildTrialModeDefinition(
        BUILD_TRIAL_ENDURANCE_ID,
        "持久",
        "检验治疗、护盾、控制与长期资源循环",
        BUILD_TRIAL_ENDURANCE_TARGET_ID,
        "持久校准体",
        1,
        30,
        240,
        "build-trial.v1.endurance",
    ),
)


BUILD_TRIAL_CATALOG = BuildTrialCatalog(
    BUILD_TRIAL_MODES,
    {
        "单体": BUILD_TRIAL_SINGLE_ID,
        "群体": BUILD_TRIAL_GROUP_ID,
        "持久": BUILD_TRIAL_ENDURANCE_ID,
        "single": BUILD_TRIAL_SINGLE_ID,
        "group": BUILD_TRIAL_GROUP_ID,
        "endurance": BUILD_TRIAL_ENDURANCE_ID,
    },
)


__all__ = [
    "BUILD_TRIAL_CATALOG",
    "BUILD_TRIAL_ENDURANCE_ID",
    "BUILD_TRIAL_GROUP_ID",
    "BUILD_TRIAL_LEVEL_PROFILES",
    "BUILD_TRIAL_MODES",
    "BUILD_TRIAL_RANK",
    "BUILD_TRIAL_RANK_ID",
    "BUILD_TRIAL_REWARD_PROFILE",
    "BUILD_TRIAL_SINGLE_ID",
    "BUILD_TRIAL_TARGETS",
]
