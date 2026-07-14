"""新角色立即可用的基础战斗定义。"""

from game.core.gameplay import (
    AbilityDefinition,
    AttributeMagnitude,
    ChangeResource,
    DamageTypeDefinition,
    DealDamage,
    EffectDefinition,
    EffectReference,
    EffectTarget,
    FixedMagnitude,
    ResourceCost,
)
from game.core.gameplay.character import (
    COMBAT_ATTACK,
    HEALTH_CURRENT,
    HEALTH_MAXIMUM,
    SPIRIT_CURRENT,
    SPIRIT_MAXIMUM,
)


PHYSICAL_DAMAGE_ID = "damage.physical"
BASIC_ATTACK_EFFECT_ID = "effect.basic_attack"
BREAKING_STRIKE_EFFECT_ID = "effect.breaking_strike"
SMALL_HEALTH_RECOVERY_EFFECT_ID = "effect.recover_small_health"
SMALL_SPIRIT_RECOVERY_EFFECT_ID = "effect.recover_small_spirit"
BASIC_ATTACK_ABILITY_ID = "ability.basic_attack"
BREAKING_STRIKE_ABILITY_ID = "ability.breaking_strike"
SMALL_HEALTH_MEDICINE_ABILITY_ID = "ability.use_small_health_medicine"
SMALL_SPIRIT_MEDICINE_ABILITY_ID = "ability.use_small_spirit_medicine"

BASE_DAMAGE_TYPES = (
    DamageTypeDefinition(PHYSICAL_DAMAGE_ID, defense_attribute="combat.defense.physical"),
)

BASE_EFFECTS = (
    EffectDefinition(
        BASIC_ATTACK_EFFECT_ID,
        operations=(
            DealDamage(
                "operation.basic_attack_damage",
                PHYSICAL_DAMAGE_ID,
                AttributeMagnitude(COMBAT_ATTACK, owner="source"),
            ),
        ),
    ),
    EffectDefinition(
        BREAKING_STRIKE_EFFECT_ID,
        operations=(
            DealDamage(
                "operation.breaking_strike_damage",
                PHYSICAL_DAMAGE_ID,
                AttributeMagnitude(COMBAT_ATTACK, owner="source", scale=1.5),
            ),
        ),
    ),
    EffectDefinition(
        SMALL_HEALTH_RECOVERY_EFFECT_ID,
        operations=(
            ChangeResource(
                "operation.recover_small_health",
                HEALTH_CURRENT,
                AttributeMagnitude(HEALTH_MAXIMUM, owner="target", scale=0.12),
            ),
        ),
    ),
    EffectDefinition(
        SMALL_SPIRIT_RECOVERY_EFFECT_ID,
        operations=(
            ChangeResource(
                "operation.recover_small_spirit",
                SPIRIT_CURRENT,
                AttributeMagnitude(SPIRIT_MAXIMUM, owner="target", scale=0.12),
            ),
        ),
    ),
)

BASE_ABILITIES = (
    AbilityDefinition(
        BASIC_ATTACK_ABILITY_ID,
        effects=(EffectReference(BASIC_ATTACK_EFFECT_ID),),
    ),
    AbilityDefinition(
        BREAKING_STRIKE_ABILITY_ID,
        costs=(ResourceCost(SPIRIT_CURRENT, FixedMagnitude(20)),),
        effects=(EffectReference(BREAKING_STRIKE_EFFECT_ID),),
        cooldown_turns=2,
    ),
    AbilityDefinition(
        SMALL_HEALTH_MEDICINE_ABILITY_ID,
        effects=(EffectReference(SMALL_HEALTH_RECOVERY_EFFECT_ID, EffectTarget.SELF),),
    ),
    AbilityDefinition(
        SMALL_SPIRIT_MEDICINE_ABILITY_ID,
        effects=(EffectReference(SMALL_SPIRIT_RECOVERY_EFFECT_ID, EffectTarget.SELF),),
    ),
)

COMBAT_DISPLAY_CONTENT_IDS = frozenset(
    {
        PHYSICAL_DAMAGE_ID,
        BASIC_ATTACK_ABILITY_ID,
        BREAKING_STRIKE_ABILITY_ID,
        SMALL_HEALTH_MEDICINE_ABILITY_ID,
        SMALL_SPIRIT_MEDICINE_ABILITY_ID,
    }
)


__all__ = [
    "BASE_ABILITIES",
    "BASE_DAMAGE_TYPES",
    "BASE_EFFECTS",
    "BASIC_ATTACK_ABILITY_ID",
    "BREAKING_STRIKE_ABILITY_ID",
    "COMBAT_DISPLAY_CONTENT_IDS",
    "PHYSICAL_DAMAGE_ID",
    "SMALL_HEALTH_MEDICINE_ABILITY_ID",
    "SMALL_SPIRIT_MEDICINE_ABILITY_ID",
]
