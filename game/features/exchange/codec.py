"""归航兑换回执白名单。"""

from .models import CovenantExchangeHistory, CovenantExchangeReceipt


def covenant_exchange_codec_registrations() -> tuple[tuple[str, type[object]], ...]:
    return (
        ("game.covenant_exchange.receipt.v1", CovenantExchangeReceipt),
        ("game.covenant_exchange.history.v1", CovenantExchangeHistory),
    )


__all__ = ["covenant_exchange_codec_registrations"]
