"""汇总官方世界皮肤，不保存玩法规则。"""

from game.core.gameplay import (
    ContentPackage,
    ContentPackageManifest,
    ContentVersion,
    PackageRequirement,
)

from ..catalog import CATALOG_PACKAGE_ID
from .cultivation import CULTIVATION_SKIN
from .magic import MAGIC_SKIN


WORLD_SKIN_PACKAGE_ID = "content.world_skins.official"


WORLD_SKIN_PACKAGE = ContentPackage(
    manifest=ContentPackageManifest(
        id=WORLD_SKIN_PACKAGE_ID,
        version=ContentVersion(3, 1, 0),
        dependencies=(
            PackageRequirement(
                package_id=CATALOG_PACKAGE_ID,
                minimum_version=ContentVersion(3, 0, 0),
                maximum_exclusive=ContentVersion(4, 0, 0),
            ),
        ),
    ),
    skin_packs=(CULTIVATION_SKIN, MAGIC_SKIN),
)


__all__ = ["WORLD_SKIN_PACKAGE", "WORLD_SKIN_PACKAGE_ID"]
