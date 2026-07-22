"""可堆叠特殊物品的业务使用入口。"""

from .codec import special_item_codec_registrations
from .models import SpecialItemUseCommand, SpecialItemUseReceipt
from .service import (
    BACKPACK_CAPACITY_EFFECT_KIND,
    SpecialItemUseService,
)


__all__ = [
    "BACKPACK_CAPACITY_EFFECT_KIND",
    "SpecialItemUseCommand",
    "SpecialItemUseReceipt",
    "SpecialItemUseService",
    "special_item_codec_registrations",
]
