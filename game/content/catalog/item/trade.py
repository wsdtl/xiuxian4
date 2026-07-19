"""物品固定收购价的类型化内容组件。"""

from __future__ import annotations

from dataclasses import dataclass

from game.core.gameplay import ItemComponentType, StableId, stable_id


ITEM_SALE_COMPONENT_ID = "item_component.sale_value"


@dataclass(frozen=True)
class ItemSaleValue:
    """系统收购物品时使用的币种与整数单价。"""

    currency_id: StableId
    unit_price: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "currency_id",
            stable_id(self.currency_id, field="sale currency id"),
        )
        if isinstance(self.unit_price, bool) or not isinstance(self.unit_price, int):
            raise TypeError("物品收购单价必须是整数")
        if self.unit_price < 1:
            raise ValueError("物品收购单价必须大于 0")


ITEM_SALE_COMPONENT_TYPE = ItemComponentType(
    ITEM_SALE_COMPONENT_ID,
    ItemSaleValue,
)


__all__ = [
    "ITEM_SALE_COMPONENT_ID",
    "ITEM_SALE_COMPONENT_TYPE",
    "ItemSaleValue",
]
