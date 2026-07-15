"""基础修仙界的武器展示。"""

from game.core.gameplay import SkinEntry

from ...catalog import STARTER_WEAPON_ID, STARTER_WEAPON_ITEM_ID


CULTIVATION_WEAPON_ENTRIES = {
    STARTER_WEAPON_ITEM_ID: SkinEntry(name="仙京制式剑器", icon="⚔"),
    STARTER_WEAPON_ID: SkinEntry(
        name="仙京制式剑",
        description="仙京发给初入道途者的凡品制式长剑。",
        icon="⚔",
    ),
}


__all__ = ["CULTIVATION_WEAPON_ENTRIES"]
