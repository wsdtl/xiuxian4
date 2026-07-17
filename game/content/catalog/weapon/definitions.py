"""固定新手武器定义。"""

from game.core.gameplay import (
    COMBAT_ATTACK,
    LOADOUT_ITEM_COMPONENT_ID,
    WEAPON_SLOT_ID,
    AttributeGrant,
    ContributionSpec,
    ItemAssetKind,
    ItemDefinition,
    LoadoutItemComponent,
    ModifierLayer,
    TagSet,
    WeaponDefinition,
    WeaponQualityProfile,
)

from ..foundation import COMMON_QUALITY_ID
from ..combat.definitions import BREAKING_STRIKE_ABILITY_ID
from ..item.definitions import STARTER_WEAPON_ITEM_ID
from .mechanics import WEAPON_MECHANIC_CONTENT


STARTER_WEAPON_ID = "weapon.starter_sword"

STARTER_WEAPON_ITEM = ItemDefinition(
    STARTER_WEAPON_ITEM_ID,
    ItemAssetKind.INSTANCE,
    TagSet.of("item.weapon", "item.armament"),
    components={
        LOADOUT_ITEM_COMPONENT_ID: LoadoutItemComponent(
            frozenset({WEAPON_SLOT_ID})
        )
    },
)

STARTER_WEAPON = WeaponDefinition(
    STARTER_WEAPON_ID,
    STARTER_WEAPON_ITEM_ID,
    ContributionSpec(
        attributes=(
            AttributeGrant(COMBAT_ATTACK, ModifierLayer.LOCAL_FLAT, 2),
        ),
        abilities=frozenset({BREAKING_STRIKE_ABILITY_ID}),
    ),
    {
        COMMON_QUALITY_ID: WeaponQualityProfile(
            COMMON_QUALITY_ID,
            experience_requirements=(),
        )
    },
)

GENERATED_WEAPON_ITEMS = WEAPON_MECHANIC_CONTENT.items
GENERATED_WEAPONS = WEAPON_MECHANIC_CONTENT.weapons
WEAPON_DISPLAY_CONTENT_IDS = frozenset(
    {STARTER_WEAPON_ID, *WEAPON_MECHANIC_CONTENT.display_ids}
)


__all__ = [
    "STARTER_WEAPON",
    "STARTER_WEAPON_ID",
    "STARTER_WEAPON_ITEM",
    "GENERATED_WEAPON_ITEMS",
    "GENERATED_WEAPONS",
    "WEAPON_DISPLAY_CONTENT_IDS",
]
