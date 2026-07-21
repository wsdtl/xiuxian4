"""汇总官方世界展示皮肤，不声明玩法世界。"""

from game.core.gameplay import (
    ContentPackage,
    ContentPackageManifest,
    ContentVersion,
    PackageRequirement,
)

from ..catalog import CATALOG_PACKAGE_ID
from .cultivation import CULTIVATION_SKIN, CULTIVATION_SKIN_ID
from .magic import MAGIC_SKIN, MAGIC_SKIN_ID
from .stellar_ring import STELLAR_RING_SKIN, STELLAR_RING_SKIN_ID


WORLD_SKIN_PACKAGE_ID = "content.world_skins.official"
OFFICIAL_SKIN_IDS = (CULTIVATION_SKIN_ID, MAGIC_SKIN_ID, STELLAR_RING_SKIN_ID)


WORLD_SKIN_PACKAGE = ContentPackage(
    manifest=ContentPackageManifest(
        id=WORLD_SKIN_PACKAGE_ID,
        version=ContentVersion(3, 20, 0),
        dependencies=(
            PackageRequirement(
                package_id=CATALOG_PACKAGE_ID,
                minimum_version=ContentVersion(3, 22, 0),
                maximum_exclusive=ContentVersion(4, 0, 0),
            ),
        ),
    ),
    skin_packs=(CULTIVATION_SKIN, MAGIC_SKIN, STELLAR_RING_SKIN),
)


__all__ = [
    "OFFICIAL_SKIN_IDS",
    "WORLD_SKIN_PACKAGE",
    "WORLD_SKIN_PACKAGE_ID",
]
