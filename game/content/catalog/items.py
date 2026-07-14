"""角色创世阶段使用的最小物品名录。"""

from game.core.gameplay import (
    ITEM_ABILITY_COMPONENT_ID,
    ItemAbilityComponent,
    ItemAssetKind,
    ItemDefinition,
    TagSet,
)

from .combat import (
    SMALL_HEALTH_MEDICINE_ABILITY_ID,
    SMALL_SPIRIT_MEDICINE_ABILITY_ID,
)


SMALL_HEALTH_MEDICINE_ITEM_ID = "item.consumable.small_health_medicine"
SMALL_SPIRIT_MEDICINE_ITEM_ID = "item.consumable.small_spirit_medicine"
STARTER_WEAPON_ITEM_ID = "item.weapon.starter_sword"

STARTER_ITEMS = (
    ItemDefinition(
        SMALL_HEALTH_MEDICINE_ITEM_ID,
        ItemAssetKind.STACK,
        TagSet.of("item.consumable", "item.medicine", "resource.health"),
        99,
        {
            ITEM_ABILITY_COMPONENT_ID: ItemAbilityComponent(
                SMALL_HEALTH_MEDICINE_ABILITY_ID
            )
        },
    ),
    ItemDefinition(
        SMALL_SPIRIT_MEDICINE_ITEM_ID,
        ItemAssetKind.STACK,
        TagSet.of("item.consumable", "item.medicine", "resource.spirit"),
        99,
        {
            ITEM_ABILITY_COMPONENT_ID: ItemAbilityComponent(
                SMALL_SPIRIT_MEDICINE_ABILITY_ID
            )
        },
    ),
)

ITEM_DISPLAY_CONTENT_IDS = frozenset(
    {
        SMALL_HEALTH_MEDICINE_ITEM_ID,
        SMALL_SPIRIT_MEDICINE_ITEM_ID,
        STARTER_WEAPON_ITEM_ID,
    }
)


__all__ = [
    "ITEM_DISPLAY_CONTENT_IDS",
    "SMALL_HEALTH_MEDICINE_ITEM_ID",
    "SMALL_SPIRIT_MEDICINE_ITEM_ID",
    "STARTER_ITEMS",
    "STARTER_WEAPON_ITEM_ID",
]
