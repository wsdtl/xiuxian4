"""次元灾厄名录的稳定入口。"""

from .catalog import DOCUMENTED_SOURCE_SOFT_RATIO, DimensionalDisasterCatalog
from .cultivation import CULTIVATION_DISASTERS, CULTIVATION_DISASTER_SOURCE_ID
from .magic import MAGIC_DISASTERS, MAGIC_DISASTER_SOURCE_ID
from .stellar_ring import STELLAR_RING_DISASTERS, STELLAR_RING_DISASTER_SOURCE_ID
from .models import (
    DISASTER_ORIGIN_DOCUMENTED,
    DISASTER_ORIGIN_KINDS,
    DISASTER_ORIGIN_ORIGINAL,
    DimensionalDisasterDefinition,
    DisasterContentAudit,
    DisasterSourceAudit,
)
from .policy import *


DIMENSIONAL_DISASTERS = (
    *CULTIVATION_DISASTERS,
    *MAGIC_DISASTERS,
    *STELLAR_RING_DISASTERS,
)


def build_dimensional_disaster_catalog() -> DimensionalDisasterCatalog:
    return DimensionalDisasterCatalog(DIMENSIONAL_DISASTERS)


__all__ = [name for name in globals() if not name.startswith("_")]
