"""官方世界志目录组装。"""

from .magic import MAGIC_LORE
from .models import WorldLoreCatalog
from .stellar_ring import STELLAR_RING_LORE
from .taixuan import TAIXUAN_LORE


WORLD_LORE_CATALOG = WorldLoreCatalog(
    (
        TAIXUAN_LORE,
        MAGIC_LORE,
        STELLAR_RING_LORE,
    )
)


__all__ = ["WORLD_LORE_CATALOG"]
