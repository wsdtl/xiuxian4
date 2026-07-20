"""突破业务回执的结构化持久化白名单。"""

from .models import BreakthroughReceipt


def breakthrough_codec_registrations() -> tuple[tuple[str, type[object]], ...]:
    return (("game.breakthrough.receipt.v1", BreakthroughReceipt),)


__all__ = ["breakthrough_codec_registrations"]
