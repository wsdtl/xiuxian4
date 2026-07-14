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

from .base import COMMON_QUALITY_ID
from .combat import BREAKING_STRIKE_ABILITY_ID
from .items import STARTER_WEAPON_ITEM_ID


STARTER_WEAPON_ID = "weapon.starter_sword"

STARTER_WEAPON_ITEM = ItemDefinition(
    STARTER_WEAPON_ITEM_ID,
    ItemAssetKind.INSTANCE,
    TagSet.of("item.weapon"),
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

WEAPON_DISPLAY_CONTENT_IDS = frozenset({STARTER_WEAPON_ID})


__all__ = [
    "STARTER_WEAPON",
    "STARTER_WEAPON_ID",
    "STARTER_WEAPON_ITEM",
    "WEAPON_DISPLAY_CONTENT_IDS",
]
