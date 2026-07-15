"""魔法世界的公共展示名称。"""

from game.core.gameplay import SkinEntry

from ...catalog import COMMON_QUALITY_ID, PRIMARY_CURRENCY_ID


MAGIC_BASE_ENTRIES = {
    PRIMARY_CURRENCY_ID: SkinEntry(name="魔晶", icon="◆"),
    COMMON_QUALITY_ID: SkinEntry(name="普通"),
}


__all__ = ["MAGIC_BASE_ENTRIES"]
