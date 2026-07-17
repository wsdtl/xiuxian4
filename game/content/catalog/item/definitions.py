"""基础消耗品和角色创世所需物品名录。"""

from game.core.gameplay import (
    ITEM_ABILITY_COMPONENT_ID,
    ITEM_STORAGE_COMPONENT_ID,
    ItemAbilityComponent,
    ItemAssetKind,
    ItemDefinition,
    ItemStorageComponent,
    TagSet,
)

from ..combat.definitions import (
    LARGE_HEALTH_MEDICINE_ABILITY_ID,
    LARGE_SPIRIT_MEDICINE_ABILITY_ID,
    MEDIUM_HEALTH_MEDICINE_ABILITY_ID,
    MEDIUM_SPIRIT_MEDICINE_ABILITY_ID,
    SMALL_HEALTH_MEDICINE_ABILITY_ID,
    SMALL_SPIRIT_MEDICINE_ABILITY_ID,
)


SMALL_HEALTH_MEDICINE_ITEM_ID = "item.consumable.small_health_medicine"
MEDIUM_HEALTH_MEDICINE_ITEM_ID = "item.consumable.medium_health_medicine"
LARGE_HEALTH_MEDICINE_ITEM_ID = "item.consumable.large_health_medicine"
SMALL_SPIRIT_MEDICINE_ITEM_ID = "item.consumable.small_spirit_medicine"
MEDIUM_SPIRIT_MEDICINE_ITEM_ID = "item.consumable.medium_spirit_medicine"
LARGE_SPIRIT_MEDICINE_ITEM_ID = "item.consumable.large_spirit_medicine"
STARTER_WEAPON_ITEM_ID = "item.weapon.starter_sword"

MEDICINE_ITEMS = tuple(
    ItemDefinition(
        item_id,
        ItemAssetKind.STACK,
        TagSet.of(
            "item.consumable",
            "item.medicine",
            "storage.special",
            resource_tag,
            tier_tag,
        ),
        99,
        {
            ITEM_ABILITY_COMPONENT_ID: ItemAbilityComponent(ability_id),
            ITEM_STORAGE_COMPONENT_ID: ItemStorageComponent(1),
        },
    )
    for item_id, ability_id, resource_tag, tier_tag in (
        (
            SMALL_HEALTH_MEDICINE_ITEM_ID,
            SMALL_HEALTH_MEDICINE_ABILITY_ID,
            "resource.health",
            "medicine.tier.small",
        ),
        (
            MEDIUM_HEALTH_MEDICINE_ITEM_ID,
            MEDIUM_HEALTH_MEDICINE_ABILITY_ID,
            "resource.health",
            "medicine.tier.medium",
        ),
        (
            LARGE_HEALTH_MEDICINE_ITEM_ID,
            LARGE_HEALTH_MEDICINE_ABILITY_ID,
            "resource.health",
            "medicine.tier.large",
        ),
        (
            SMALL_SPIRIT_MEDICINE_ITEM_ID,
            SMALL_SPIRIT_MEDICINE_ABILITY_ID,
            "resource.spirit",
            "medicine.tier.small",
        ),
        (
            MEDIUM_SPIRIT_MEDICINE_ITEM_ID,
            MEDIUM_SPIRIT_MEDICINE_ABILITY_ID,
            "resource.spirit",
            "medicine.tier.medium",
        ),
        (
            LARGE_SPIRIT_MEDICINE_ITEM_ID,
            LARGE_SPIRIT_MEDICINE_ABILITY_ID,
            "resource.spirit",
            "medicine.tier.large",
        ),
    )
)

ITEM_DISPLAY_CONTENT_IDS = frozenset(
    {
        SMALL_HEALTH_MEDICINE_ITEM_ID,
        MEDIUM_HEALTH_MEDICINE_ITEM_ID,
        LARGE_HEALTH_MEDICINE_ITEM_ID,
        SMALL_SPIRIT_MEDICINE_ITEM_ID,
        MEDIUM_SPIRIT_MEDICINE_ITEM_ID,
        LARGE_SPIRIT_MEDICINE_ITEM_ID,
        STARTER_WEAPON_ITEM_ID,
    }
)


__all__ = [
    "ITEM_DISPLAY_CONTENT_IDS",
    "LARGE_HEALTH_MEDICINE_ITEM_ID",
    "LARGE_SPIRIT_MEDICINE_ITEM_ID",
    "MEDICINE_ITEMS",
    "MEDIUM_HEALTH_MEDICINE_ITEM_ID",
    "MEDIUM_SPIRIT_MEDICINE_ITEM_ID",
    "SMALL_HEALTH_MEDICINE_ITEM_ID",
    "SMALL_SPIRIT_MEDICINE_ITEM_ID",
    "STARTER_WEAPON_ITEM_ID",
]
