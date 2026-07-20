"""次元灾厄专属战斗定义，不复用个人或组队首领身份。"""

from __future__ import annotations

from game.core.gameplay import (
    COMBAT_ATTACK,
    COMBAT_DEFENSE,
    COMBAT_SPEED,
    HEALTH_MAXIMUM,
    SPIRIT_MAXIMUM,
    BattleAiRule,
    ContributionSpec,
    ENEMY_RANK_BOSS_ID,
    EnemyDefinition,
    EnemyLevelProfileDefinition,
    EnemyPhaseDefinition,
    EnemyRewardProfileDefinition,
    TagSet,
)

from ..combat.definitions import BASIC_ATTACK_ABILITY_ID
from ..combat.stats import COMBAT_CONTROL_RESISTANCE, COMBAT_TENACITY
from ..enemy.behaviors import ENEMY_BEHAVIOR_CONTENT
from .cultivation import CULTIVATION_DISASTERS
from .magic import MAGIC_DISASTERS


DISASTER_ENEMY_LEVEL_PROFILE_ID = "enemy.level.dimensional_disaster"
DISASTER_ENEMY_REWARD_PROFILE_ID = "enemy.reward.dimensional_disaster"


def _levels(formula) -> tuple[float, ...]:
    return tuple(round(float(formula(level)), 2) for level in range(1, 101))


DISASTER_ENEMY_LEVEL_PROFILE = EnemyLevelProfileDefinition(
    DISASTER_ENEMY_LEVEL_PROFILE_ID,
    {
        HEALTH_MAXIMUM: _levels(
            lambda level: 110 + 14 * (level - 1) + 0.05 * (level - 1) ** 2
        ),
        SPIRIT_MAXIMUM: _levels(lambda level: 150 + 3 * (level - 1)),
        COMBAT_ATTACK: _levels(lambda level: 8 + 1.0 * (level - 1)),
        COMBAT_DEFENSE: _levels(lambda level: 0.55 * (level - 1)),
        COMBAT_SPEED: _levels(lambda _level: 100),
        COMBAT_CONTROL_RESISTANCE: _levels(lambda _level: 0),
        COMBAT_TENACITY: _levels(lambda _level: 0),
    },
)


# 灾厄奖励由活动贡献结算，敌人报价不能再次产生经验或掉落。
DISASTER_ENEMY_REWARD_PROFILE = EnemyRewardProfileDefinition(
    DISASTER_ENEMY_REWARD_PROFILE_ID,
    0.0,
    0.0,
    None,
    0,
)


_BASIC_AI = (
    BattleAiRule(
        "ai.enemy.dimensional_disaster.basic_attack",
        BASIC_ATTACK_ABILITY_ID,
        "target.enemy.first",
        priority=0,
        maximum_targets=1,
    ),
)
_ALL_BEHAVIOR_IDS = frozenset(
    value.id for value in ENEMY_BEHAVIOR_CONTENT.behaviors
)
_BEHAVIOR_KEYS = tuple(
    value.id.removeprefix("enemy.behavior.")
    for value in ENEMY_BEHAVIOR_CONTENT.behaviors
)


def _enemy(definition, index: int) -> EnemyDefinition:
    defaults = frozenset(
        f"enemy.behavior.{value}" for value in definition.combat_behavior_keys
    )
    phase_keys = tuple(
        value
        for value in _BEHAVIOR_KEYS
        if f"enemy.behavior.{value}" not in defaults
    )
    source_key = definition.source_skin_id.removeprefix("skin.")
    disaster_key = definition.id.rsplit(".", 1)[-1]
    phases = (
        EnemyPhaseDefinition(
            f"enemy.phase.disaster.{source_key}.{disaster_key}.second",
            0.65,
            frozenset(
                {f"enemy.behavior.{phase_keys[index % len(phase_keys)]}"}
            ),
        ),
        EnemyPhaseDefinition(
            f"enemy.phase.disaster.{source_key}.{disaster_key}.final",
            0.30,
            frozenset(
                {
                    f"enemy.behavior."
                    f"{phase_keys[(index + 9) % len(phase_keys)]}"
                }
            ),
        ),
    )
    return EnemyDefinition(
        definition.enemy_definition_id,
        DISASTER_ENEMY_LEVEL_PROFILE_ID,
        DISASTER_ENEMY_REWARD_PROFILE_ID,
        frozenset({ENEMY_RANK_BOSS_ID}),
        defaults,
        _ALL_BEHAVIOR_IDS,
        ContributionSpec(
            tags=TagSet.of("enemy.identity.dimensional_disaster"),
            abilities=frozenset({BASIC_ATTACK_ABILITY_ID}),
        ),
        _BASIC_AI,
        phases,
        TagSet.of("enemy.identity.dimensional_disaster"),
    )


DISASTER_ENEMY_DEFINITIONS = tuple(
    _enemy(value, index)
    for index, value in enumerate((*CULTIVATION_DISASTERS, *MAGIC_DISASTERS))
)


__all__ = [name for name in globals() if not name.startswith("_")]
