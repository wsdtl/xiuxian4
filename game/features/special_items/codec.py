"""特殊物品业务快照的结构化白名单。"""

from .models import SpecialItemUseReceipt


def special_item_codec_registrations() -> tuple[tuple[str, type[object]], ...]:
    return (
        ("game.special_item.use_receipt.v1", SpecialItemUseReceipt),
    )


__all__ = ["special_item_codec_registrations"]
