"""纳戒物品分类、铭刻之羽定义与特殊物品构造约束。"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from game.core.gameplay import (
    ITEM_STORAGE_COMPONENT_ID,
    ITEM_CONTAINER_CAPACITY_COMPONENT_ID,
    ContainerCapacityItemComponent,
    EQUIPMENT_SET_GUARANTEE_ITEM_COMPONENT_ID,
    EquipmentSetGuaranteeItemComponent,
    ItemAssetKind,
    ItemDefinition,
    ItemComponentType,
    ItemStorageComponent,
    StableId,
    TagSet,
    WEAPON_LEVEL_ITEM_COMPONENT_ID,
    WEAPON_MAXIMUM_LEVEL_ITEM_COMPONENT_ID,
    WeaponLevelItemComponent,
    WeaponMaximumLevelItemComponent,
    stable_id,
)


CONSUMABLE_ITEM_TAG = "item.consumable"
MEDICINE_ITEM_TAG = "item.medicine"
SPECIAL_ITEM_TAG = "item.special"
INSCRIPTION_MEDIUM_ITEM_TAG = "item.inscription_medium"
SPECIAL_STORAGE_TAG = "storage.special"
INSCRIPTION_STORAGE_TAG = "storage.inscription"

INSCRIPTION_FEATHER_ITEM_ID = "item.inscription.feather"
WEAPON_MAXIMUM_LEVEL_ITEM_ID = "item.special.weapon_maximum_level"
WEAPON_LEVEL_ITEM_ID = "item.special.weapon_level"
BACKPACK_CAPACITY_ITEM_ID = "item.special.backpack_capacity"
EQUIPMENT_SET_GUARANTEE_ITEM_ID = "item.special.equipment_set_guarantee"
DIMENSION_SHIFT_ITEM_ID = "item.special.dimension_shift"
DIMENSION_SHIFT_ITEM_COMPONENT_ID = "item_component.use_dimension_shift"
COMPANION_SANCTUARY_ITEM_ID = "item.special.companion_sanctuary"
COMPANION_SANCTUARY_ITEM_COMPONENT_ID = "item_component.use_companion_sanctuary"
BACKPACK_CAPACITY_INCREMENT = 5
BACKPACK_CAPACITY_MAXIMUM = 140
SPECIAL_ITEM_STACK_LIMIT = 99


@dataclass(frozen=True)
class DimensionShiftItemComponent:
    """标记该特殊物品由跃迁业务自动消耗。"""

    quantity: int = 1

    def __post_init__(self) -> None:
        if self.quantity != 1:
            raise ValueError("每次跃迁必须且只能消耗一枚跃迁凭证")


DIMENSION_SHIFT_ITEM_COMPONENT_TYPE = ItemComponentType(
    DIMENSION_SHIFT_ITEM_COMPONENT_ID,
    DimensionShiftItemComponent,
)


@dataclass(frozen=True)
class CompanionSanctuaryItemComponent:
    """标记该特殊物品用于开启角色当前世界的伙伴秘境。"""

    quantity: int = 1

    def __post_init__(self) -> None:
        if self.quantity != 1:
            raise ValueError("每次开启伙伴秘境必须且只能消耗一枚万灵引")


COMPANION_SANCTUARY_ITEM_COMPONENT_TYPE = ItemComponentType(
    COMPANION_SANCTUARY_ITEM_COMPONENT_ID,
    CompanionSanctuaryItemComponent,
)


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


WEAPON_MAXIMUM_LEVEL_ITEM = special_item_definition(
    WEAPON_MAXIMUM_LEVEL_ITEM_ID,
    use_components={
        WEAPON_MAXIMUM_LEVEL_ITEM_COMPONENT_ID: WeaponMaximumLevelItemComponent(),
    },
)
WEAPON_LEVEL_ITEM = special_item_definition(
    WEAPON_LEVEL_ITEM_ID,
    use_components={
        WEAPON_LEVEL_ITEM_COMPONENT_ID: WeaponLevelItemComponent(),
    },
)
BACKPACK_CAPACITY_ITEM = special_item_definition(
    BACKPACK_CAPACITY_ITEM_ID,
    use_components={
        ITEM_CONTAINER_CAPACITY_COMPONENT_ID: ContainerCapacityItemComponent(
            "container.backpack",
            BACKPACK_CAPACITY_INCREMENT,
            BACKPACK_CAPACITY_MAXIMUM,
        ),
    },
)
EQUIPMENT_SET_GUARANTEE_ITEM = special_item_definition(
    EQUIPMENT_SET_GUARANTEE_ITEM_ID,
    use_components={
        EQUIPMENT_SET_GUARANTEE_ITEM_COMPONENT_ID: EquipmentSetGuaranteeItemComponent(),
    },
)
DIMENSION_SHIFT_ITEM = special_item_definition(
    DIMENSION_SHIFT_ITEM_ID,
    use_components={
        DIMENSION_SHIFT_ITEM_COMPONENT_ID: DimensionShiftItemComponent(),
    },
)
COMPANION_SANCTUARY_ITEM = special_item_definition(
    COMPANION_SANCTUARY_ITEM_ID,
    use_components={
        COMPANION_SANCTUARY_ITEM_COMPONENT_ID: CompanionSanctuaryItemComponent(),
    },
)
SPECIAL_ITEMS: tuple[ItemDefinition, ...] = (
    WEAPON_MAXIMUM_LEVEL_ITEM,
    WEAPON_LEVEL_ITEM,
    BACKPACK_CAPACITY_ITEM,
    EQUIPMENT_SET_GUARANTEE_ITEM,
    DIMENSION_SHIFT_ITEM,
    COMPANION_SANCTUARY_ITEM,
)


__all__ = [
    "CONSUMABLE_ITEM_TAG",
    "COMPANION_SANCTUARY_ITEM",
    "COMPANION_SANCTUARY_ITEM_COMPONENT_ID",
    "COMPANION_SANCTUARY_ITEM_COMPONENT_TYPE",
    "COMPANION_SANCTUARY_ITEM_ID",
    "CompanionSanctuaryItemComponent",
    "BACKPACK_CAPACITY_INCREMENT",
    "BACKPACK_CAPACITY_ITEM",
    "BACKPACK_CAPACITY_ITEM_ID",
    "BACKPACK_CAPACITY_MAXIMUM",
    "EQUIPMENT_SET_GUARANTEE_ITEM",
    "EQUIPMENT_SET_GUARANTEE_ITEM_ID",
    "DIMENSION_SHIFT_ITEM",
    "DIMENSION_SHIFT_ITEM_COMPONENT_ID",
    "DIMENSION_SHIFT_ITEM_COMPONENT_TYPE",
    "DIMENSION_SHIFT_ITEM_ID",
    "DimensionShiftItemComponent",
    "INSCRIPTION_FEATHER_ITEM",
    "INSCRIPTION_FEATHER_ITEM_ID",
    "INSCRIPTION_MEDIUM_ITEM_TAG",
    "INSCRIPTION_STORAGE_TAG",
    "MEDICINE_ITEM_TAG",
    "SPECIAL_ITEM_STACK_LIMIT",
    "SPECIAL_ITEMS",
    "SPECIAL_ITEM_TAG",
    "SPECIAL_STORAGE_TAG",
    "WEAPON_LEVEL_ITEM",
    "WEAPON_LEVEL_ITEM_ID",
    "WEAPON_MAXIMUM_LEVEL_ITEM",
    "WEAPON_MAXIMUM_LEVEL_ITEM_ID",
    "special_item_definition",
    "validate_nacre_item_categories",
]
