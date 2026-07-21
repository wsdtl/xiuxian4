"""把非货币战斗评分转换成统一整数参考价。"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from game.content.catalog.economy import (
    ECONOMY_POLICY_ID,
    ECONOMY_POLICY_VERSION,
    EQUIPMENT_SET_PREMIUM_BPS,
    GEAR_VALUE_POINT_PRICE,
    WEAPON_LEVEL_PREMIUM_BPS,
    WEAPON_MAXIMUM_LEVEL_PREMIUM_BPS,
    WEAPON_MAXIMUM_LEVEL_PREMIUM_BASE,
)
from game.content.catalog.foundation import PRIMARY_CURRENCY_ID
from game.core.gameplay import (
    EQUIPMENT_SLOT_IDS,
    WEAPON_SLOT_ID,
    ItemInstance,
    equipment_state_from_instance,
    weapon_state_from_instance,
)

from .models import GearPriceQuote


class GearPriceService:
    """只认正式实例评分；固定新手武器没有随机评分，不进入经济市场。"""

    def __init__(self, content) -> None:
        self.content = content

    def quote(self, instance: ItemInstance) -> GearPriceQuote:
        definition = self.content.items.require(instance.definition_id)
        if definition.tags.has("item.weapon"):
            state = weapon_state_from_instance(instance)
            if state.roll is None:
                raise ValueError("固定新手武器不能回收或进入归航市场")
            score = state.roll.intrinsic_value.total
            price = _score_price(score)
            price = _scale_bps(
                price,
                10_000 + (state.level - 1) * WEAPON_LEVEL_PREMIUM_BPS,
            )
            price = _scale_bps(
                price,
                10_000
                + max(0, state.maximum_level - WEAPON_MAXIMUM_LEVEL_PREMIUM_BASE)
                * WEAPON_MAXIMUM_LEVEL_PREMIUM_BPS,
            )
            return GearPriceQuote(
                instance.id,
                state.definition_id,
                "weapon",
                state.quality_id,
                WEAPON_SLOT_ID,
                score,
                price,
                PRIMARY_CURRENCY_ID,
                ECONOMY_POLICY_ID,
                ECONOMY_POLICY_VERSION,
            )
        if definition.tags.has("item.equipment"):
            state = equipment_state_from_instance(instance)
            if state.roll is None:
                raise ValueError("固定装备不能回收或进入归航市场")
            score = state.roll.intrinsic_value.total
            price = _score_price(score)
            if state.set_id is not None:
                price = _scale_bps(price, 10_000 + EQUIPMENT_SET_PREMIUM_BPS)
            slot_id = self.content.equipment.require(state.definition_id).slot_id
            if slot_id not in EQUIPMENT_SLOT_IDS:
                raise ValueError("装备实例引用了未知部位")
            return GearPriceQuote(
                instance.id,
                state.definition_id,
                "equipment",
                state.quality_id,
                slot_id,
                score,
                price,
                PRIMARY_CURRENCY_ID,
                ECONOMY_POLICY_ID,
                ECONOMY_POLICY_VERSION,
            )
        raise ValueError("只有正式武器和装备具有统一装备参考价")


def _score_price(score: float) -> int:
    value = Decimal(str(score)) * GEAR_VALUE_POINT_PRICE
    return max(1, int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)))


def _scale_bps(amount: int, basis_points: int) -> int:
    return max(1, (amount * basis_points + 5_000) // 10_000)


__all__ = ["GearPriceService"]
