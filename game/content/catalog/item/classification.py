"""纳戒物品的互斥分类和存储边界。"""

from __future__ import annotations

from collections.abc import Iterable

from game.core.gameplay import ItemAssetKind, ItemDefinition


CONSUMABLE_ITEM_TAG = "item.consumable"
MEDICINE_ITEM_TAG = "item.medicine"
SPECIAL_ITEM_TAG = "item.special"
BREAKTHROUGH_TOKEN_ITEM_TAG = "item.breakthrough_token"
INSCRIPTION_MEDIUM_ITEM_TAG = "item.inscription_medium"
SPECIAL_STORAGE_TAG = "storage.special"
INSCRIPTION_STORAGE_TAG = "storage.inscription"


def validate_nacre_item_categories(definitions: Iterable[ItemDefinition]) -> None:
    """锁定纳戒物品分类互斥，并校验各分类的资产形态。"""

    stack_categories = (
        MEDICINE_ITEM_TAG,
        SPECIAL_ITEM_TAG,
        BREAKTHROUGH_TOKEN_ITEM_TAG,
    )
    all_categories = (*stack_categories, INSCRIPTION_MEDIUM_ITEM_TAG)
    for definition in definitions:
        category_tags = tuple(tag for tag in all_categories if definition.tags.has(tag))
        if not category_tags:
            continue
        if len(category_tags) != 1:
            raise ValueError(f"纳戒物品 {definition.id} 不能同时属于多个物品分类")
        category = category_tags[0]
        if category in stack_categories:
            if not definition.tags.has(SPECIAL_STORAGE_TAG):
                raise ValueError(f"纳戒物品 {definition.id} 缺少 {SPECIAL_STORAGE_TAG} 标签")
            if definition.tags.has(INSCRIPTION_STORAGE_TAG):
                raise ValueError(f"纳戒物品 {definition.id} 不能进入铭刻保管区")
            if definition.asset_kind is not ItemAssetKind.STACK:
                raise ValueError(f"可消耗物品 {definition.id} 必须是可堆叠资产")
            if not definition.tags.has(CONSUMABLE_ITEM_TAG):
                raise ValueError(f"可消耗物品 {definition.id} 缺少消耗品标签")
        if category == SPECIAL_ITEM_TAG and not any(
            component_id.startswith("item_component.use_")
            for component_id in definition.components
        ):
            raise ValueError(f"特殊物品 {definition.id} 没有类型化使用组件")
        if category == INSCRIPTION_MEDIUM_ITEM_TAG:
            if not definition.tags.has(INSCRIPTION_STORAGE_TAG):
                raise ValueError(
                    f"铭刻之羽 {definition.id} 缺少 {INSCRIPTION_STORAGE_TAG} 标签"
                )
            if definition.tags.has(SPECIAL_STORAGE_TAG):
                raise ValueError(f"铭刻之羽 {definition.id} 不能进入纳戒")
            if definition.asset_kind is not ItemAssetKind.INSTANCE:
                raise ValueError(f"铭刻之羽 {definition.id} 必须是独立实例")
            if definition.tags.has(CONSUMABLE_ITEM_TAG):
                raise ValueError(f"铭刻之羽 {definition.id} 不能进入普通消耗品流程")


__all__ = [name for name in globals() if not name.startswith("_")]
