"""魔法世界世界皮肤。"""

from game.core.gameplay import SkinEntry, SkinPack

from ..catalog import (
    BASIC_ATTACK_ABILITY_ID,
    BASIC_COMBAT_FEATURE_ID,
    BREAKING_STRIKE_ABILITY_ID,
    CHARACTER_LEVEL_PROGRESSION_ID,
    DEFAULT_CHARACTER_TEMPLATE_ID,
    MORTAL_PHYSIQUE_FEATURE_ID,
    ORIGIN_HUMAN_FEATURE_ID,
    PHYSICAL_DAMAGE_ID,
    PRIMARY_WORLD_SPACE_ID,
    SMALL_HEALTH_MEDICINE_ABILITY_ID,
    SMALL_HEALTH_MEDICINE_ITEM_ID,
    SMALL_SPIRIT_MEDICINE_ABILITY_ID,
    SMALL_SPIRIT_MEDICINE_ITEM_ID,
    STARTER_WEAPON_ID,
    STARTER_WEAPON_ITEM_ID,
    STARTING_CITY_ID,
    COMMON_QUALITY_ID,
    PRIMARY_CURRENCY_ID,
)


MAGIC_SKIN_ID = "skin.magic"


MAGIC_SKIN = SkinPack(
    id=MAGIC_SKIN_ID,
    version=1,
    name="魔法世界",
    icon="✦",
    entries={
        PRIMARY_CURRENCY_ID: SkinEntry(
            name="魔晶",
            icon="◆",
        ),
        COMMON_QUALITY_ID: SkinEntry(name="普通"),
        ORIGIN_HUMAN_FEATURE_ID: SkinEntry(name="人类"),
        MORTAL_PHYSIQUE_FEATURE_ID: SkinEntry(name="常人体魄"),
        BASIC_COMBAT_FEATURE_ID: SkinEntry(name="基础战技"),
        CHARACTER_LEVEL_PROGRESSION_ID: SkinEntry(name="冒险等级"),
        DEFAULT_CHARACTER_TEMPLATE_ID: SkinEntry(name="人类冒险者"),
        PHYSICAL_DAMAGE_ID: SkinEntry(name="物理伤害"),
        BASIC_ATTACK_ABILITY_ID: SkinEntry(name="基础攻击"),
        BREAKING_STRIKE_ABILITY_ID: SkinEntry(
            name="破势斩",
            description="造成 150% 攻击伤害，消耗 20% 最大魔力，冷却 2 次自身行动。",
        ),
        SMALL_HEALTH_MEDICINE_ABILITY_ID: SkinEntry(name="饮用小型生命药剂"),
        SMALL_SPIRIT_MEDICINE_ABILITY_ID: SkinEntry(name="饮用小型魔力药剂"),
        SMALL_HEALTH_MEDICINE_ITEM_ID: SkinEntry(
            name="小型生命药剂",
            description="恢复最大生命的 12%。",
            icon="🧪",
        ),
        SMALL_SPIRIT_MEDICINE_ITEM_ID: SkinEntry(
            name="小型魔力药剂",
            description="恢复最大魔力的 12%。",
            icon="💧",
        ),
        STARTER_WEAPON_ITEM_ID: SkinEntry(name="王都守备剑器", icon="⚔"),
        STARTER_WEAPON_ID: SkinEntry(
            name="王都守备剑",
            description="王都配发给新晋冒险者的普通制式剑。",
            icon="⚔",
        ),
        PRIMARY_WORLD_SPACE_ID: SkinEntry(name="星辉大陆"),
        STARTING_CITY_ID: SkinEntry(
            name="星辉王城",
            description="坐落于世界原点的第一座王城。",
            icon="🏰",
        ),
    },
)


__all__ = ["MAGIC_SKIN", "MAGIC_SKIN_ID"]
