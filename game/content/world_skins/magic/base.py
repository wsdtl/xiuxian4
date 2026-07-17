"""魔法世界的公共展示名称。"""

from game.core.gameplay import SkinEntry

from ...catalog import (
    COMMON_QUALITY_ID,
    EPIC_QUALITY_ID,
    FINE_QUALITY_ID,
    LEGENDARY_QUALITY_ID,
    PRIMARY_CURRENCY_ID,
    RARE_QUALITY_ID,
)


MAGIC_BASE_ENTRIES = {
    PRIMARY_CURRENCY_ID: SkinEntry(name="魔晶", icon="◆"),
    COMMON_QUALITY_ID: SkinEntry(name="普通"),
    FINE_QUALITY_ID: SkinEntry(name="精良"),
    RARE_QUALITY_ID: SkinEntry(name="稀有"),
    EPIC_QUALITY_ID: SkinEntry(name="史诗"),
    LEGENDARY_QUALITY_ID: SkinEntry(name="传说"),
}


__all__ = ["MAGIC_BASE_ENTRIES"]
