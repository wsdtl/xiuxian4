"""系统回收与归航市场税务报价。"""

from __future__ import annotations

from game.content.catalog.economy import (
    ECONOMY_POLICY_ID,
    ECONOMY_POLICY_VERSION,
    GEAR_RECYCLE_RATE_BPS,
    MARKET_ASSET_REPEAT_TAX_BPS,
    MARKET_BASE_TAX_BPS,
    MARKET_MAX_SELLER_PRICE_BPS,
    MARKET_MIN_PRICE_BPS,
    MARKET_NORMAL_TAX_MAX_BPS,
    MARKET_PAIR_REPEAT_TAX_BPS,
)

from .models import GearPriceQuote, MarketTaxQuote


def recycle_amount(price: GearPriceQuote) -> int:
    return max(1, price.reference_price * GEAR_RECYCLE_RATE_BPS // 10_000)


def quote_market_tax(
    reference_price: int,
    list_price: int,
    *,
    repeated_pair_trades: int = 0,
    repeated_asset_trades: int = 0,
) -> MarketTaxQuote:
    if reference_price < 1 or list_price < 1:
        raise ValueError("二手参考价和上架价必须大于 0")
    if repeated_pair_trades < 0 or repeated_asset_trades < 0:
        raise ValueError("二手风险成交次数不能小于 0")
    minimum_buyer_total = _ceil_bps(reference_price, MARKET_MIN_PRICE_BPS)
    seller_gross_cap = reference_price * MARKET_MAX_SELLER_PRICE_BPS // 10_000
    recognized_gross = min(list_price, max(1, seller_gross_cap))
    low_surcharge = max(0, minimum_buyer_total - list_price)
    high_tax = max(0, list_price - recognized_gross)
    normal_rate = min(
        MARKET_NORMAL_TAX_MAX_BPS,
        MARKET_BASE_TAX_BPS
        + repeated_pair_trades * MARKET_PAIR_REPEAT_TAX_BPS
        + repeated_asset_trades * MARKET_ASSET_REPEAT_TAX_BPS,
    )
    seller_tax = recognized_gross * MARKET_BASE_TAX_BPS // 10_000
    risk_rate = normal_rate - MARKET_BASE_TAX_BPS
    risk_surcharge = recognized_gross * risk_rate // 10_000
    seller_proceeds = max(1, recognized_gross - seller_tax)
    buyer_total = list_price + low_surcharge + risk_surcharge
    tax_amount = buyer_total - seller_proceeds
    return MarketTaxQuote(
        reference_price,
        list_price,
        buyer_total,
        seller_proceeds,
        tax_amount,
        normal_rate,
        low_surcharge,
        high_tax,
        risk_surcharge,
        repeated_pair_trades,
        repeated_asset_trades,
        ECONOMY_POLICY_ID,
        ECONOMY_POLICY_VERSION,
    )


def _ceil_bps(amount: int, basis_points: int) -> int:
    return max(1, (amount * basis_points + 9_999) // 10_000)


__all__ = ["quote_market_tax", "recycle_amount"]
