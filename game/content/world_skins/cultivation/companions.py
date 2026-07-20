"""太玄界伙伴系统公共称谓。"""

from game.core.gameplay import SkinEntry

from ...catalog.companion import (
    COMPANION_BIND_ACTION_ID,
    COMPANION_RELEASE_ACTION_ID,
    COMPANION_SANCTUARY_TERM_ID,
    COMPANION_TERM_ID,
)


CULTIVATION_COMPANION_ENTRIES = {
    COMPANION_TERM_ID: SkinEntry(name="灵宠", compact_name="灵宠", icon="✦"),
    COMPANION_SANCTUARY_TERM_ID: SkinEntry(
        name="万灵秘境",
        compact_name="秘境",
        icon="☯",
    ),
    COMPANION_BIND_ACTION_ID: SkinEntry(name="出战", compact_name="出战"),
    COMPANION_RELEASE_ACTION_ID: SkinEntry(name="放生", compact_name="放生"),
}


__all__ = ["CULTIVATION_COMPANION_ENTRIES"]
