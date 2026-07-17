"""汇总稳定名录定义；具体分类定义不得直接写在本文件。"""

from game.core.gameplay import ContentPackage, ContentPackageManifest, ContentVersion

from .foundation import (
    BASE_ATTRIBUTES,
    BASE_COMBAT_PROFILES,
    BASE_CURRENCIES,
    BASE_DISPLAY_CONTENT_IDS,
    BASE_QUALITIES,
    BASE_RESOURCES,
)
from .character.definitions import (
    CHARACTER_DISPLAY_CONTENT_IDS,
    CHARACTER_FEATURES,
    CHARACTER_LEVEL_PROGRESSION,
    DEFAULT_CHARACTER_TEMPLATE,
)
from .combat.definitions import (
    BASE_ABILITIES,
    BASE_CONTROLS,
    BASE_DAMAGE_TYPES,
    BASE_EFFECTS,
    COMBAT_DISPLAY_CONTENT_IDS,
)
from .item.definitions import ITEM_DISPLAY_CONTENT_IDS, MEDICINE_ITEMS
from .equipment.definitions import EQUIPMENT_CATALOG_CONTENT
from .equipment.properties import EQUIPMENT_PROPERTY_CONTENT
from .character.realms import (
    CHARACTER_REALM_CONTENT_DEFINITIONS,
    CHARACTER_REALM_DISPLAY_IDS,
)
from .weapon.definitions import (
    GENERATED_WEAPON_ITEMS,
    GENERATED_WEAPONS,
    STARTER_WEAPON,
    STARTER_WEAPON_ITEM,
    WEAPON_DISPLAY_CONTENT_IDS,
)
from .weapon.mechanics import WEAPON_MECHANIC_CONTENT
from .world.definitions import (
    PRIMARY_WORLD_SPACE,
    STARTING_CITY,
    WORLD_DISPLAY_CONTENT_IDS,
)
from .combat.valuation import BASE_ATTRIBUTE_VALUATIONS, BASE_REFERENCE_VALUATIONS


CATALOG_PACKAGE_ID = "content.catalog.base"


CATALOG_PACKAGE = ContentPackage(
    manifest=ContentPackageManifest(
        id=CATALOG_PACKAGE_ID,
        version=ContentVersion(3, 0, 0),
    ),
    display_definitions=CHARACTER_REALM_CONTENT_DEFINITIONS,
    currencies=BASE_CURRENCIES,
    qualities=BASE_QUALITIES,
    attributes=BASE_ATTRIBUTES,
    resources=BASE_RESOURCES,
    character_features=CHARACTER_FEATURES,
    progressions=(CHARACTER_LEVEL_PROGRESSION,),
    character_templates=(DEFAULT_CHARACTER_TEMPLATE,),
    items=(
        *MEDICINE_ITEMS,
        STARTER_WEAPON_ITEM,
        *GENERATED_WEAPON_ITEMS,
        *EQUIPMENT_CATALOG_CONTENT.items,
    ),
    weapons=(STARTER_WEAPON, *GENERATED_WEAPONS),
    equipment_families=EQUIPMENT_CATALOG_CONTENT.families,
    equipment_sets=EQUIPMENT_CATALOG_CONTENT.sets,
    equipment=EQUIPMENT_CATALOG_CONTENT.equipment,
    attribute_valuations=BASE_ATTRIBUTE_VALUATIONS,
    reference_valuations=(
        *BASE_REFERENCE_VALUATIONS,
        *WEAPON_MECHANIC_CONTENT.reference_valuations,
        *EQUIPMENT_PROPERTY_CONTENT.reference_valuations,
    ),
    random_properties=(
        *WEAPON_MECHANIC_CONTENT.properties,
        *EQUIPMENT_PROPERTY_CONTENT.properties,
    ),
    generation_profiles=(
        *WEAPON_MECHANIC_CONTENT.profiles,
        *EQUIPMENT_PROPERTY_CONTENT.profiles,
    ),
    combat_profiles=BASE_COMBAT_PROFILES,
    damage_types=BASE_DAMAGE_TYPES,
    controls=BASE_CONTROLS,
    effects=(
        *BASE_EFFECTS,
        *WEAPON_MECHANIC_CONTENT.effects,
        *EQUIPMENT_PROPERTY_CONTENT.effects,
    ),
    abilities=(*BASE_ABILITIES, *WEAPON_MECHANIC_CONTENT.abilities),
    battle_ability_targeting=WEAPON_MECHANIC_CONTENT.targeting,
    triggers=(
        *WEAPON_MECHANIC_CONTENT.triggers,
        *EQUIPMENT_PROPERTY_CONTENT.triggers,
    ),
    interceptors=WEAPON_MECHANIC_CONTENT.interceptors,
    target_constraints=WEAPON_MECHANIC_CONTENT.constraints,
    world_spaces=(PRIMARY_WORLD_SPACE,),
    world_locations=(STARTING_CITY,),
    display_content_ids=(
        BASE_DISPLAY_CONTENT_IDS
        | CHARACTER_DISPLAY_CONTENT_IDS
        | CHARACTER_REALM_DISPLAY_IDS
        | COMBAT_DISPLAY_CONTENT_IDS
        | ITEM_DISPLAY_CONTENT_IDS
        | WEAPON_DISPLAY_CONTENT_IDS
        | EQUIPMENT_CATALOG_CONTENT.display_ids
        | EQUIPMENT_PROPERTY_CONTENT.display_ids
        | WORLD_DISPLAY_CONTENT_IDS
    ),
)


__all__ = ["CATALOG_PACKAGE", "CATALOG_PACKAGE_ID"]
