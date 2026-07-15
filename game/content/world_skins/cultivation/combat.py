"""基础修仙界的战斗展示。"""

from game.core.gameplay import SkinEntry

from ...catalog import (
    BASIC_ATTACK_ABILITY_ID,
    BASIC_COMBAT_FEATURE_ID,
    BREAKING_STRIKE_ABILITY_ID,
    PHYSICAL_DAMAGE_ID,
)


CULTIVATION_COMBAT_ENTRIES = {
    BASIC_COMBAT_FEATURE_ID: SkinEntry(name="基础斗法"),
    PHYSICAL_DAMAGE_ID: SkinEntry(name="物理伤害"),
    BASIC_ATTACK_ABILITY_ID: SkinEntry(name="基础攻击"),
    BREAKING_STRIKE_ABILITY_ID: SkinEntry(
        name="破势",
        description="造成 150% 攻击伤害，消耗 20% 最大灵力，冷却 2 次自身行动。",
    ),
}


__all__ = ["CULTIVATION_COMBAT_ENTRIES"]
