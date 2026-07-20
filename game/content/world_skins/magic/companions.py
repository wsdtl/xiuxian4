"""魔法世界伙伴系统公共称谓。"""

from game.core.gameplay import SkinEntry

from ...catalog.companion import (
    COMPANION_BIND_ACTION_ID,
    COMPANION_RELEASE_ACTION_ID,
    COMPANION_SANCTUARY_TERM_ID,
    COMPANION_TERM_ID,
)


MAGIC_COMPANION_ENTRIES = {
    COMPANION_TERM_ID: SkinEntry(name="使魔", compact_name="使魔", icon="✦"),
    COMPANION_SANCTUARY_TERM_ID: SkinEntry(
        name="幻兽庭",
        compact_name="幻兽庭",
        icon="✦",
    ),
    COMPANION_BIND_ACTION_ID: SkinEntry(name="召唤", compact_name="召唤"),
    COMPANION_RELEASE_ACTION_ID: SkinEntry(
        name="解除契约",
        compact_name="解契",
    ),
}


__all__ = ["MAGIC_COMPANION_ENTRIES"]
