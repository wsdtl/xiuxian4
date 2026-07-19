"""装备掉落保证类消耗品的类型化组件。"""

from dataclasses import dataclass

from ..inventory import ItemComponentType


EQUIPMENT_SET_GUARANTEE_ITEM_COMPONENT_ID = (
    "item_component.use_equipment_set_guarantee"
)


@dataclass(frozen=True)
class EquipmentSetGuaranteeItemComponent:
    charges: int = 1
    maximum_active_charges: int = 1

    def __post_init__(self) -> None:
        for field_name in ("charges", "maximum_active_charges"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"EquipmentSetGuaranteeItemComponent.{field_name} 必须是整数")
        if self.charges < 1 or self.maximum_active_charges < self.charges:
            raise ValueError("装备套装保证次数和激活上限无效")


EQUIPMENT_SET_GUARANTEE_ITEM_COMPONENT_TYPE = ItemComponentType(
    EQUIPMENT_SET_GUARANTEE_ITEM_COMPONENT_ID,
    EquipmentSetGuaranteeItemComponent,
)


__all__ = [
    "EQUIPMENT_SET_GUARANTEE_ITEM_COMPONENT_ID",
    "EQUIPMENT_SET_GUARANTEE_ITEM_COMPONENT_TYPE",
    "EquipmentSetGuaranteeItemComponent",
]
