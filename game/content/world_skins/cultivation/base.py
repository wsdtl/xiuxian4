"""基础修仙界的公共展示名称。"""

from game.core.gameplay import (
    COMBAT_ATTACK,
    COMBAT_DEFENSE,
    COMBAT_SPEED,
    HEALTH_CURRENT,
    HEALTH_MAXIMUM,
    SPIRIT_CURRENT,
    SPIRIT_MAXIMUM,
    SkinEntry,
)

from ...catalog import (
    COMMON_QUALITY_ID,
    EPIC_QUALITY_ID,
    FINE_QUALITY_ID,
    LEGENDARY_QUALITY_ID,
    PRIMARY_CURRENCY_ID,
    RARE_QUALITY_ID,
)
from ...catalog.combat.stats import (
    COMBAT_ACCURACY,
    COMBAT_BLOCK_CHANCE,
    COMBAT_BLOCK_REDUCTION,
    COMBAT_CONTROL_CHANCE,
    COMBAT_CONTROL_RESISTANCE,
    COMBAT_CRITICAL_CHANCE,
    COMBAT_CRITICAL_DAMAGE,
    COMBAT_EVASION,
    COMBAT_FLAT_PENETRATION,
    COMBAT_HEALING_RATE,
    COMBAT_HEALING_RECEIVED,
    COMBAT_INCOMING_RATE,
    COMBAT_OUTGOING_RATE,
    COMBAT_RATE_PENETRATION,
    COMBAT_TENACITY,
    SHIELD_CURRENT,
)


CULTIVATION_BASE_ENTRIES = {
    PRIMARY_CURRENCY_ID: SkinEntry(name="灵石", icon="◆"),
    COMMON_QUALITY_ID: SkinEntry(name="黄"),
    FINE_QUALITY_ID: SkinEntry(name="玄"),
    RARE_QUALITY_ID: SkinEntry(name="地"),
    EPIC_QUALITY_ID: SkinEntry(name="天"),
    LEGENDARY_QUALITY_ID: SkinEntry(name="圣"),
    HEALTH_MAXIMUM: SkinEntry(name="气血上限"),
    SPIRIT_MAXIMUM: SkinEntry(name="灵力上限"),
    COMBAT_ATTACK: SkinEntry(name="攻击力"),
    COMBAT_DEFENSE: SkinEntry(name="基础防御"),
    COMBAT_SPEED: SkinEntry(name="行动速度"),
    COMBAT_ACCURACY: SkinEntry(name="命中率"),
    COMBAT_EVASION: SkinEntry(name="闪避率"),
    COMBAT_CRITICAL_CHANCE: SkinEntry(name="会心率"),
    COMBAT_CRITICAL_DAMAGE: SkinEntry(name="会心伤害"),
    COMBAT_BLOCK_CHANCE: SkinEntry(name="格挡率"),
    COMBAT_BLOCK_REDUCTION: SkinEntry(name="格挡减伤"),
    COMBAT_OUTGOING_RATE: SkinEntry(name="造成伤害"),
    COMBAT_INCOMING_RATE: SkinEntry(name="承受伤害"),
    COMBAT_FLAT_PENETRATION: SkinEntry(name="固定穿透"),
    COMBAT_RATE_PENETRATION: SkinEntry(name="比例穿透"),
    COMBAT_HEALING_RATE: SkinEntry(name="治疗效果"),
    COMBAT_HEALING_RECEIVED: SkinEntry(name="受疗效果"),
    COMBAT_CONTROL_CHANCE: SkinEntry(name="控制命中"),
    COMBAT_CONTROL_RESISTANCE: SkinEntry(name="控制抵抗"),
    COMBAT_TENACITY: SkinEntry(name="控制韧性"),
    HEALTH_CURRENT: SkinEntry(name="当前气血"),
    SPIRIT_CURRENT: SkinEntry(name="当前灵力"),
    SHIELD_CURRENT: SkinEntry(name="当前护盾"),
}


__all__ = ["CULTIVATION_BASE_ENTRIES"]
