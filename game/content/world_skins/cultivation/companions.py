"""太玄界伙伴系统公共称谓。"""

from game.core.gameplay import SkinEntry

from ...catalog.companion import (
    COMPANION_BIND_ACTION_ID,
    COMPANION_FAREWELL_ACTION_ID,
    COMPANION_SANCTUARY_TERM_ID,
    COMPANION_TERM_ID,
)


CULTIVATION_COMPANION_ENTRIES = {
    COMPANION_TERM_ID: SkinEntry(name="伙伴", compact_name="伙伴", icon="✦"),
    COMPANION_SANCTUARY_TERM_ID: SkinEntry(
        name="万灵秘境",
        compact_name="秘境",
        icon="☯",
    ),
    COMPANION_BIND_ACTION_ID: SkinEntry(name="出战", compact_name="出战"),
    COMPANION_FAREWELL_ACTION_ID: SkinEntry(name="告别", compact_name="告别"),
}


__all__ = ["CULTIVATION_COMPANION_ENTRIES"]
