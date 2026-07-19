"""纳戒物品分类、铭刻之羽定义与特殊物品构造约束。"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from game.core.gameplay import (
    ITEM_STORAGE_COMPONENT_ID,
    ItemAssetKind,
    ItemDefinition,
    ItemStorageComponent,
    StableId,
    TagSet,
    stable_id,
)


CONSUMABLE_ITEM_TAG = "item.consumable"
MEDICINE_ITEM_TAG = "item.medicine"
SPECIAL_ITEM_TAG = "item.special"
INSCRIPTION_MEDIUM_ITEM_TAG = "item.inscription_medium"
SPECIAL_STORAGE_TAG = "storage.special"
INSCRIPTION_STORAGE_TAG = "storage.inscription"

INSCRIPTION_FEATHER_ITEM_ID = "item.inscription.feather"
SPECIAL_ITEM_STACK_LIMIT = 99


INSCRIPTION_FEATHER_ITEM = ItemDefinition(
    INSCRIPTION_FEATHER_ITEM_ID,
    ItemAssetKind.INSTANCE,
    TagSet.of(INSCRIPTION_MEDIUM_ITEM_TAG, INSCRIPTION_STORAGE_TAG),
    components={ITEM_STORAGE_COMPONENT_ID: ItemStorageComponent(1)},
)


def special_item_definition(
    item_id: StableId,
    *,
    use_components: Mapping[StableId, object],
    stack_limit: int = SPECIAL_ITEM_STACK_LIMIT,
) -> ItemDefinition:
    """构造一个可堆叠特殊物品；实际用途必须由类型化使用组件声明。"""

    components = {
        stable_id(component_id, field="item component id"): value
        for component_id, value in use_components.items()
    }
    if not components:
        raise ValueError("特殊物品必须声明至少一个类型化使用组件")
    invalid = sorted(
        component_id
        for component_id in components
        if not component_id.startswith("item_component.use_")
    )
    if invalid:
        raise ValueError(f"特殊物品包含非使用组件：{invalid[0]}")
    components[ITEM_STORAGE_COMPONENT_ID] = ItemStorageComponent(1)
    definition = ItemDefinition(
        item_id,
        ItemAssetKind.STACK,
        TagSet.of(CONSUMABLE_ITEM_TAG, SPECIAL_ITEM_TAG, SPECIAL_STORAGE_TAG),
        stack_limit,
        components,
    )
    validate_nacre_item_categories((definition,))
    return definition


def validate_nacre_item_categories(definitions: Iterable[ItemDefinition]) -> None:
    """锁定恢复药、特殊物品和铭刻之羽互斥且各自形态正确。"""

    for definition in definitions:
        category_tags = tuple(
            tag
            for tag in (MEDICINE_ITEM_TAG, SPECIAL_ITEM_TAG, INSCRIPTION_MEDIUM_ITEM_TAG)
            if definition.tags.has(tag)
        )
        if not category_tags:
            continue
        if len(category_tags) != 1:
            raise ValueError(f"纳戒物品 {definition.id} 不能同时属于多个物品分类")
        category = category_tags[0]
        if category in (MEDICINE_ITEM_TAG, SPECIAL_ITEM_TAG):
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


__all__ = [
    "CONSUMABLE_ITEM_TAG",
    "INSCRIPTION_FEATHER_ITEM",
    "INSCRIPTION_FEATHER_ITEM_ID",
    "INSCRIPTION_MEDIUM_ITEM_TAG",
    "INSCRIPTION_STORAGE_TAG",
    "MEDICINE_ITEM_TAG",
    "SPECIAL_ITEM_STACK_LIMIT",
    "SPECIAL_ITEM_TAG",
    "SPECIAL_STORAGE_TAG",
    "special_item_definition",
    "validate_nacre_item_categories",
]
