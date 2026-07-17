"""基础修仙界世界皮肤的唯一组装入口。"""

from game.core.gameplay import SkinPack

from .base import CULTIVATION_BASE_ENTRIES
from .character import CULTIVATION_CHARACTER_ENTRIES
from .combat import CULTIVATION_COMBAT_ENTRIES
from .equipment import CULTIVATION_EQUIPMENT_ENTRIES
from .items import CULTIVATION_ITEM_ENTRIES
from .weapons import CULTIVATION_WEAPON_ENTRIES
from .world import CULTIVATION_WORLD_ENTRIES


CULTIVATION_SKIN_ID = "skin.cultivation"


CULTIVATION_SKIN = SkinPack(
    id=CULTIVATION_SKIN_ID,
    version=5,
    name="基础修仙界",
    icon="☯",
    entries={
        **CULTIVATION_BASE_ENTRIES,
        **CULTIVATION_CHARACTER_ENTRIES,
        **CULTIVATION_COMBAT_ENTRIES,
        **CULTIVATION_EQUIPMENT_ENTRIES,
        **CULTIVATION_ITEM_ENTRIES,
        **CULTIVATION_WEAPON_ENTRIES,
        **CULTIVATION_WORLD_ENTRIES,
    },
)


__all__ = ["CULTIVATION_SKIN", "CULTIVATION_SKIN_ID"]
