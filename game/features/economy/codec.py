"""经济玩法持久状态的结构化白名单。"""

from game.rules.economy import (
    GearPriceQuote,
    MarketListing,
    MarketPriceQuote,
    MarketState,
    MarketTradeRecord,
)


def economy_codec_registrations() -> tuple[tuple[str, type[object]], ...]:
    return (
        ("game.economy.gear_price.v1", GearPriceQuote),
        ("game.economy.market_price.v1", MarketPriceQuote),
        ("game.economy.market_listing.v1", MarketListing),
        ("game.economy.market_trade.v1", MarketTradeRecord),
        ("game.economy.market_state.v1", MarketState),
    )


__all__ = ["economy_codec_registrations"]
