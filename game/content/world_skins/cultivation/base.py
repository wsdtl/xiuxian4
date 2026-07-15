"""基础修仙界的公共展示名称。"""

from game.core.gameplay import SkinEntry

from ...catalog import COMMON_QUALITY_ID, PRIMARY_CURRENCY_ID


CULTIVATION_BASE_ENTRIES = {
    PRIMARY_CURRENCY_ID: SkinEntry(name="灵石", icon="◆"),
    COMMON_QUALITY_ID: SkinEntry(name="凡品"),
}


__all__ = ["CULTIVATION_BASE_ENTRIES"]
