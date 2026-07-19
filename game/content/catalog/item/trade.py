"""物品固定回收价的类型化内容组件。"""

from __future__ import annotations

from dataclasses import dataclass

from game.core.gameplay import ItemComponentType, StableId, stable_id


ITEM_RECYCLE_COMPONENT_ID = "item_component.recycle_value"


@dataclass(frozen=True)
class ItemRecycleValue:
    """系统回收物品时使用的币种与整数单价。"""

    currency_id: StableId
    unit_amount: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "currency_id",
            stable_id(self.currency_id, field="recycle currency id"),
        )
        if isinstance(self.unit_amount, bool) or not isinstance(self.unit_amount, int):
            raise TypeError("物品回收单价必须是整数")
        if self.unit_amount < 1:
            raise ValueError("物品回收单价必须大于 0")


ITEM_RECYCLE_COMPONENT_TYPE = ItemComponentType(
    ITEM_RECYCLE_COMPONENT_ID,
    ItemRecycleValue,
)


__all__ = [
    "ITEM_RECYCLE_COMPONENT_ID",
    "ITEM_RECYCLE_COMPONENT_TYPE",
    "ItemRecycleValue",
]
