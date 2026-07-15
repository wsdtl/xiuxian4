"""魔法世界的消耗品展示。"""

from game.core.gameplay import SkinEntry

from ...catalog import (
    SMALL_HEALTH_MEDICINE_ABILITY_ID,
    SMALL_HEALTH_MEDICINE_ITEM_ID,
    SMALL_SPIRIT_MEDICINE_ABILITY_ID,
    SMALL_SPIRIT_MEDICINE_ITEM_ID,
)


MAGIC_ITEM_ENTRIES = {
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
}


__all__ = ["MAGIC_ITEM_ENTRIES"]
