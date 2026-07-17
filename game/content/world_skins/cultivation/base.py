"""基础修仙界的公共展示名称。"""

from game.core.gameplay import SkinEntry

from ...catalog import (
    COMMON_QUALITY_ID,
    EPIC_QUALITY_ID,
    FINE_QUALITY_ID,
    LEGENDARY_QUALITY_ID,
    PRIMARY_CURRENCY_ID,
    RARE_QUALITY_ID,
)


CULTIVATION_BASE_ENTRIES = {
    PRIMARY_CURRENCY_ID: SkinEntry(name="灵石", icon="◆"),
    COMMON_QUALITY_ID: SkinEntry(name="黄"),
    FINE_QUALITY_ID: SkinEntry(name="玄"),
    RARE_QUALITY_ID: SkinEntry(name="地"),
    EPIC_QUALITY_ID: SkinEntry(name="天"),
    LEGENDARY_QUALITY_ID: SkinEntry(name="圣"),
}


__all__ = ["CULTIVATION_BASE_ENTRIES"]
