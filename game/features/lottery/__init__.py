"""彩票系统玩法。"""

from .codec import lottery_codec_registrations
from .models import LotteryPlayerView
from .service import LOTTERY_AGGREGATE, LotteryFeature, LotteryStorageKinds

__all__ = [
    "LOTTERY_AGGREGATE",
    "LotteryFeature",
    "LotteryPlayerView",
    "LotteryStorageKinds",
    "lottery_codec_registrations",
]
