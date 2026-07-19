"""太玄界的消耗品展示。"""

from game.core.gameplay import SkinEntry

from ...catalog import (
    INSCRIPTION_FEATHER_ITEM_ID,
    LARGE_HEALTH_MEDICINE_ABILITY_ID,
    LARGE_HEALTH_MEDICINE_ITEM_ID,
    LARGE_SPIRIT_MEDICINE_ABILITY_ID,
    LARGE_SPIRIT_MEDICINE_ITEM_ID,
    MEDIUM_HEALTH_MEDICINE_ABILITY_ID,
    MEDIUM_HEALTH_MEDICINE_ITEM_ID,
    MEDIUM_SPIRIT_MEDICINE_ABILITY_ID,
    MEDIUM_SPIRIT_MEDICINE_ITEM_ID,
    SMALL_HEALTH_MEDICINE_ABILITY_ID,
    SMALL_HEALTH_MEDICINE_ITEM_ID,
    SMALL_SPIRIT_MEDICINE_ABILITY_ID,
    SMALL_SPIRIT_MEDICINE_ITEM_ID,
)


CULTIVATION_ITEM_ENTRIES = {
    INSCRIPTION_FEATHER_ITEM_ID: SkinEntry(
        name="铭刻之羽",
        description="承载一段不可复刻的旧愿，可为武器、装备或武器能力留下私名。",
        icon="📜",
    ),
    SMALL_HEALTH_MEDICINE_ABILITY_ID: SkinEntry(name="服用小还丹"),
    MEDIUM_HEALTH_MEDICINE_ABILITY_ID: SkinEntry(name="服用中还丹"),
    LARGE_HEALTH_MEDICINE_ABILITY_ID: SkinEntry(name="服用大还丹"),
    SMALL_SPIRIT_MEDICINE_ABILITY_ID: SkinEntry(name="服用小回灵丹"),
    MEDIUM_SPIRIT_MEDICINE_ABILITY_ID: SkinEntry(name="服用中回灵丹"),
    LARGE_SPIRIT_MEDICINE_ABILITY_ID: SkinEntry(name="服用大回灵丹"),
    SMALL_HEALTH_MEDICINE_ITEM_ID: SkinEntry(
        name="小还丹",
        description="恢复最大血气的 12%。",
        icon="💊",
    ),
    MEDIUM_HEALTH_MEDICINE_ITEM_ID: SkinEntry(
        name="中还丹",
        description="恢复最大血气的 25%。",
        icon="💊",
    ),
    LARGE_HEALTH_MEDICINE_ITEM_ID: SkinEntry(
        name="大还丹",
        description="恢复最大血气的 50%。",
        icon="💊",
    ),
    SMALL_SPIRIT_MEDICINE_ITEM_ID: SkinEntry(
        name="小回灵丹",
        description="恢复最大灵力的 12%。",
        icon="💧",
    ),
    MEDIUM_SPIRIT_MEDICINE_ITEM_ID: SkinEntry(
        name="中回灵丹",
        description="恢复最大灵力的 25%。",
        icon="💧",
    ),
    LARGE_SPIRIT_MEDICINE_ITEM_ID: SkinEntry(
        name="大回灵丹",
        description="恢复最大灵力的 50%。",
        icon="💧",
    ),
}


__all__ = ["CULTIVATION_ITEM_ENTRIES"]
