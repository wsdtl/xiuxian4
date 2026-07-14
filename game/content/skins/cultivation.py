"""基础修仙界世界皮肤。"""

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


CULTIVATION_SKIN_ID = "skin.cultivation"


CULTIVATION_SKIN = SkinPack(
    id=CULTIVATION_SKIN_ID,
    version=1,
    name="基础修仙界",
    icon="☯",
    entries={
        PRIMARY_CURRENCY_ID: SkinEntry(
            name="灵石",
            icon="◆",
        ),
        COMMON_QUALITY_ID: SkinEntry(name="凡品"),
        ORIGIN_HUMAN_FEATURE_ID: SkinEntry(name="人族"),
        MORTAL_PHYSIQUE_FEATURE_ID: SkinEntry(name="凡体"),
        BASIC_COMBAT_FEATURE_ID: SkinEntry(name="基础斗法"),
        CHARACTER_LEVEL_PROGRESSION_ID: SkinEntry(name="修为等级"),
        DEFAULT_CHARACTER_TEMPLATE_ID: SkinEntry(name="凡尘修士"),
        PHYSICAL_DAMAGE_ID: SkinEntry(name="物理伤害"),
        BASIC_ATTACK_ABILITY_ID: SkinEntry(name="基础攻击"),
        BREAKING_STRIKE_ABILITY_ID: SkinEntry(
            name="破势",
            description="造成 150% 攻击伤害，消耗 20% 最大灵力，冷却 2 次自身行动。",
        ),
        SMALL_HEALTH_MEDICINE_ABILITY_ID: SkinEntry(name="服用小还丹"),
        SMALL_SPIRIT_MEDICINE_ABILITY_ID: SkinEntry(name="服用小回灵丹"),
        SMALL_HEALTH_MEDICINE_ITEM_ID: SkinEntry(
            name="小还丹",
            description="恢复最大血气的 12%。",
            icon="💊",
        ),
        SMALL_SPIRIT_MEDICINE_ITEM_ID: SkinEntry(
            name="小回灵丹",
            description="恢复最大灵力的 12%。",
            icon="💧",
        ),
        STARTER_WEAPON_ITEM_ID: SkinEntry(name="仙京制式剑器", icon="⚔"),
        STARTER_WEAPON_ID: SkinEntry(
            name="仙京制式剑",
            description="仙京发给初入道途者的凡品制式长剑。",
            icon="⚔",
        ),
        PRIMARY_WORLD_SPACE_ID: SkinEntry(name="太玄界"),
        STARTING_CITY_ID: SkinEntry(
            name="太玄仙城",
            description="坐落于世界原点的第一座仙城。",
            icon="🏯",
        ),
    },
)


__all__ = ["CULTIVATION_SKIN", "CULTIVATION_SKIN_ID"]
