"""官方真实世界身份与地点绑定内容包。"""

from game.core.gameplay import (
    ContentPackage,
    ContentPackageManifest,
    ContentVersion,
    PackageRequirement,
)

from ..catalog import CATALOG_PACKAGE_ID
from ..world_skins import WORLD_SKIN_PACKAGE_ID
from .magic import MAGIC_LOCATION_BINDINGS, MAGIC_WORLD
from .layouts import WORLD_MAP_ANCHORS
from .stellar_ring import STELLAR_RING_LOCATION_BINDINGS, STELLAR_RING_WORLD
from .taixuan import TAIXUAN_LOCATION_BINDINGS, TAIXUAN_WORLD


WORLD_PACKAGE_ID = "content.worlds.official"
PLAYABLE_WORLD_DEFINITIONS = (
    TAIXUAN_WORLD,
    MAGIC_WORLD,
    STELLAR_RING_WORLD,
)
WORLD_LOCATION_BINDINGS = (
    *TAIXUAN_LOCATION_BINDINGS,
    *MAGIC_LOCATION_BINDINGS,
    *STELLAR_RING_LOCATION_BINDINGS,
)

WORLD_PACKAGE = ContentPackage(
    manifest=ContentPackageManifest(
        id=WORLD_PACKAGE_ID,
        version=ContentVersion(1, 2, 0),
        dependencies=(
            PackageRequirement(
                package_id=CATALOG_PACKAGE_ID,
                minimum_version=ContentVersion(3, 22, 0),
                maximum_exclusive=ContentVersion(4, 0, 0),
            ),
            PackageRequirement(
                package_id=WORLD_SKIN_PACKAGE_ID,
                minimum_version=ContentVersion(3, 19, 0),
                maximum_exclusive=ContentVersion(4, 0, 0),
            ),
        ),
    ),
    world_definitions=PLAYABLE_WORLD_DEFINITIONS,
    map_anchors=WORLD_MAP_ANCHORS,
    world_location_bindings=WORLD_LOCATION_BINDINGS,
)


__all__ = [
    "PLAYABLE_WORLD_DEFINITIONS",
    "WORLD_LOCATION_BINDINGS",
    "WORLD_MAP_ANCHORS",
    "WORLD_PACKAGE",
    "WORLD_PACKAGE_ID",
]
