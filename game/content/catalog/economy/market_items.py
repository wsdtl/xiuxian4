"""可进入归航市场的固定物品参考价与价格纠偏区间。"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class MarketItemPolicy:
    definition_id: str
    category: str
    unit_reference_price: int
    minimum_price_bps: int
    maximum_price_bps: int
    minimum_quantity: int = 1
    maximum_quantity: int = 99

    def __post_init__(self) -> None:
        if not self.definition_id.strip() or not self.category.strip():
            raise ValueError("市场物品政策缺少物品或分类身份")
        integers = (
            self.unit_reference_price,
            self.minimum_price_bps,
            self.maximum_price_bps,
            self.minimum_quantity,
            self.maximum_quantity,
        )
        if any(isinstance(value, bool) or not isinstance(value, int) for value in integers):
            raise TypeError("市场物品政策数值必须是整数")
        if self.unit_reference_price < 1:
            raise ValueError("市场物品参考单价必须大于 0")
        if not 1 <= self.minimum_price_bps <= 10_000:
            raise ValueError("市场物品最低正常价格比例无效")
        if self.maximum_price_bps < 10_000:
            raise ValueError("市场物品最高正常价格比例不能低于 100%")
        if not 1 <= self.minimum_quantity <= self.maximum_quantity:
            raise ValueError("市场物品交易数量区间无效")


def _policy(
    definition_id: str,
    category: str,
    price: int,
    price_range: tuple[int, int],
    *,
    maximum_quantity: int = 99,
) -> MarketItemPolicy:
    return MarketItemPolicy(
        definition_id,
        category,
        price,
        price_range[0],
        price_range[1],
        maximum_quantity=maximum_quantity,
    )


_MEDICINE_RANGE = (6_000, 18_000)
_ORDINARY_RANGE = (5_000, 20_000)
_RARE_RANGE = (3_000, 30_000)

_POLICIES = (
    _policy("item.consumable.small_health_medicine", "medicine", 12, _MEDICINE_RANGE),
    _policy("item.consumable.medium_health_medicine", "medicine", 30, _MEDICINE_RANGE),
    _policy("item.consumable.large_health_medicine", "medicine", 70, _MEDICINE_RANGE),
    _policy("item.consumable.small_spirit_medicine", "medicine", 12, _MEDICINE_RANGE),
    _policy("item.consumable.medium_spirit_medicine", "medicine", 30, _MEDICINE_RANGE),
    _policy("item.consumable.large_spirit_medicine", "medicine", 70, _MEDICINE_RANGE),
    _policy("item.special.dimension_shift", "special", 800, _ORDINARY_RANGE),
    _policy("item.special.companion_sanctuary", "special", 1_200, _ORDINARY_RANGE),
    _policy("item.special.weapon_experience", "growth", 2_500, _RARE_RANGE),
    _policy("item.special.companion_experience", "growth", 2_200, _RARE_RANGE),
    _policy("item.special.weapon_maximum_level", "growth", 3_500, _RARE_RANGE),
    _policy("item.special.backpack_capacity", "permanent", 4_000, _RARE_RANGE),
    _policy("item.special.character_experience", "growth", 5_000, _RARE_RANGE),
    _policy("item.inscription.feather", "inscription", 5_000, _RARE_RANGE, maximum_quantity=1),
    _policy("item.draw.ticket", "draw", 200, _ORDINARY_RANGE),
    _policy("item.breakthrough_token.realm", "breakthrough", 6_000, _RARE_RANGE),
)

MARKET_ITEM_POLICIES: Mapping[str, MarketItemPolicy] = MappingProxyType(
    {value.definition_id: value for value in _POLICIES}
)

if len(MARKET_ITEM_POLICIES) != len(_POLICIES):
    raise ValueError("市场物品政策包含重复物品")


__all__ = ["MARKET_ITEM_POLICIES", "MarketItemPolicy"]
