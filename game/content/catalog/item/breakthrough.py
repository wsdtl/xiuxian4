"""独立于特殊物品的通用破境凭证定义。"""

from game.core.gameplay import (
    ITEM_STORAGE_COMPONENT_ID,
    ItemAssetKind,
    ItemDefinition,
    ItemStorageComponent,
    TagSet,
)

from .classification import (
    BREAKTHROUGH_TOKEN_ITEM_TAG,
    CONSUMABLE_ITEM_TAG,
    SPECIAL_STORAGE_TAG,
    validate_nacre_item_categories,
)


BREAKTHROUGH_TOKEN_ITEM_ID = "item.breakthrough_token.realm"
BREAKTHROUGH_TOKEN_STACK_LIMIT = 99

BREAKTHROUGH_TOKEN_ITEM = ItemDefinition(
    BREAKTHROUGH_TOKEN_ITEM_ID,
    ItemAssetKind.STACK,
    TagSet.of(
        CONSUMABLE_ITEM_TAG,
        BREAKTHROUGH_TOKEN_ITEM_TAG,
        SPECIAL_STORAGE_TAG,
    ),
    BREAKTHROUGH_TOKEN_STACK_LIMIT,
    components={ITEM_STORAGE_COMPONENT_ID: ItemStorageComponent(1)},
)
validate_nacre_item_categories((BREAKTHROUGH_TOKEN_ITEM,))


__all__ = [name for name in globals() if not name.startswith("_")]
