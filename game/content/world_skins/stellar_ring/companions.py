"""星环界伙伴系统公共称谓。"""

from game.core.gameplay import SkinEntry

from ...catalog.companion import (
    COMPANION_BIND_ACTION_ID,
    COMPANION_FAREWELL_ACTION_ID,
    COMPANION_SANCTUARY_TERM_ID,
    COMPANION_TERM_ID,
)


STELLAR_RING_COMPANION_ENTRIES = {
    COMPANION_TERM_ID: SkinEntry(name="伙伴", compact_name="伙伴", icon="◎"),
    COMPANION_SANCTUARY_TERM_ID: SkinEntry(
        name="回声育成舱",
        compact_name="育成舱",
        icon="◎",
    ),
    COMPANION_BIND_ACTION_ID: SkinEntry(name="协同", compact_name="协同"),
    COMPANION_FAREWELL_ACTION_ID: SkinEntry(name="告别", compact_name="告别"),
}


__all__ = ["STELLAR_RING_COMPANION_ENTRIES"]
