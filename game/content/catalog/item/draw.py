"""抽奖签的独立物品定义；它不是特殊物品奖项。"""

from game.core.gameplay import (
    ITEM_STORAGE_COMPONENT_ID,
    ItemAssetKind,
    ItemDefinition,
    ItemStorageComponent,
    TagSet,
)

from .special import CONSUMABLE_ITEM_TAG, SPECIAL_ITEM_STACK_LIMIT, SPECIAL_STORAGE_TAG


DRAW_TICKET_ITEM_ID = "item.draw.ticket"
DRAW_TICKET_ITEM_TAG = "item.draw_ticket"


DRAW_TICKET_ITEM = ItemDefinition(
    DRAW_TICKET_ITEM_ID,
    ItemAssetKind.STACK,
    TagSet.of(CONSUMABLE_ITEM_TAG, DRAW_TICKET_ITEM_TAG, SPECIAL_STORAGE_TAG),
    SPECIAL_ITEM_STACK_LIMIT,
    {ITEM_STORAGE_COMPONENT_ID: ItemStorageComponent(1)},
)


__all__ = ["DRAW_TICKET_ITEM", "DRAW_TICKET_ITEM_ID", "DRAW_TICKET_ITEM_TAG"]
