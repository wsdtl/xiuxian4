"""基础修仙界的消耗品展示。"""

from game.core.gameplay import SkinEntry

from ...catalog import (
    SMALL_HEALTH_MEDICINE_ABILITY_ID,
    SMALL_HEALTH_MEDICINE_ITEM_ID,
    SMALL_SPIRIT_MEDICINE_ABILITY_ID,
    SMALL_SPIRIT_MEDICINE_ITEM_ID,
)


CULTIVATION_ITEM_ENTRIES = {
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
}


__all__ = ["CULTIVATION_ITEM_ENTRIES"]
