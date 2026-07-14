"""汇总稳定名录定义；具体分类定义不得直接写在本文件。"""

from game.core.gameplay import ContentPackage, ContentPackageManifest, ContentVersion

from .base import (
    BASE_ATTRIBUTES,
    BASE_COMBAT_PROFILES,
    BASE_CURRENCIES,
    BASE_DISPLAY_CONTENT_IDS,
    BASE_QUALITIES,
    BASE_RESOURCES,
)
from .characters import (
    CHARACTER_DISPLAY_CONTENT_IDS,
    CHARACTER_FEATURES,
    CHARACTER_LEVEL_PROGRESSION,
    DEFAULT_CHARACTER_TEMPLATE,
)
from .combat import (
    BASE_ABILITIES,
    BASE_DAMAGE_TYPES,
    BASE_EFFECTS,
    COMBAT_DISPLAY_CONTENT_IDS,
)
from .items import ITEM_DISPLAY_CONTENT_IDS, STARTER_ITEMS
from .weapons import (
    STARTER_WEAPON,
    STARTER_WEAPON_ITEM,
    WEAPON_DISPLAY_CONTENT_IDS,
)
from .world import (
    PRIMARY_WORLD_SPACE,
    STARTING_CITY,
    WORLD_DISPLAY_CONTENT_IDS,
)
from .valuation import BASE_ATTRIBUTE_VALUATIONS, BASE_REFERENCE_VALUATIONS


CATALOG_PACKAGE_ID = "content.catalog.base"


CATALOG_PACKAGE = ContentPackage(
    manifest=ContentPackageManifest(
        id=CATALOG_PACKAGE_ID,
        version=ContentVersion(1, 0, 0),
    ),
    currencies=BASE_CURRENCIES,
    qualities=BASE_QUALITIES,
    attributes=BASE_ATTRIBUTES,
    resources=BASE_RESOURCES,
    character_features=CHARACTER_FEATURES,
    progressions=(CHARACTER_LEVEL_PROGRESSION,),
    character_templates=(DEFAULT_CHARACTER_TEMPLATE,),
    items=(*STARTER_ITEMS, STARTER_WEAPON_ITEM),
    weapons=(STARTER_WEAPON,),
    attribute_valuations=BASE_ATTRIBUTE_VALUATIONS,
    reference_valuations=BASE_REFERENCE_VALUATIONS,
    combat_profiles=BASE_COMBAT_PROFILES,
    damage_types=BASE_DAMAGE_TYPES,
    effects=BASE_EFFECTS,
    abilities=BASE_ABILITIES,
    world_spaces=(PRIMARY_WORLD_SPACE,),
    world_locations=(STARTING_CITY,),
    display_content_ids=(
        BASE_DISPLAY_CONTENT_IDS
        | CHARACTER_DISPLAY_CONTENT_IDS
        | COMBAT_DISPLAY_CONTENT_IDS
        | ITEM_DISPLAY_CONTENT_IDS
        | WEAPON_DISPLAY_CONTENT_IDS
        | WORLD_DISPLAY_CONTENT_IDS
    ),
)


__all__ = ["CATALOG_PACKAGE", "CATALOG_PACKAGE_ID"]
