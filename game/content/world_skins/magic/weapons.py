"""魔法世界的武器展示。"""

from game.core.gameplay import SkinEntry

from ...catalog import STARTER_WEAPON_ID, STARTER_WEAPON_ITEM_ID


MAGIC_WEAPON_ENTRIES = {
    STARTER_WEAPON_ITEM_ID: SkinEntry(name="王都守备剑器", icon="⚔"),
    STARTER_WEAPON_ID: SkinEntry(
        name="王都守备剑",
        description="王都配发给新晋冒险者的普通制式剑。",
        icon="⚔",
    ),
}


__all__ = ["MAGIC_WEAPON_ENTRIES"]
