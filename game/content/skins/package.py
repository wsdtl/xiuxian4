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


SKIN_PACKAGE_ID = "content.skins.official"


SKIN_PACKAGE = ContentPackage(
    manifest=ContentPackageManifest(
        id=SKIN_PACKAGE_ID,
        version=ContentVersion(1, 0, 0),
        dependencies=(
            PackageRequirement(
                package_id=CATALOG_PACKAGE_ID,
                minimum_version=ContentVersion(1, 0, 0),
                maximum_exclusive=ContentVersion(2, 0, 0),
            ),
        ),
    ),
    skin_packs=(CULTIVATION_SKIN, MAGIC_SKIN),
)


__all__ = ["SKIN_PACKAGE", "SKIN_PACKAGE_ID"]
