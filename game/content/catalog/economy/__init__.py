"""统一物价、系统回收与二手税务的正式内容参数。"""

from .lottery import (
    LOTTERY_CENTRAL_SUBSIDY_MULTIPLIER,
    LOTTERY_CENTRAL_SUBSIDY_RATE,
    LOTTERY_MIN_PRIZE,
    LOTTERY_MIN_PARTICIPANTS,
    LOTTERY_POOL_MAX,
    LOTTERY_TICKET_PRICE,
)

from .policy import *
from .policy import __all__ as _policy_exports


__all__ = [
    *_policy_exports,
    "LOTTERY_CENTRAL_SUBSIDY_MULTIPLIER",
    "LOTTERY_CENTRAL_SUBSIDY_RATE",
    "LOTTERY_MIN_PRIZE",
    "LOTTERY_MIN_PARTICIPANTS",
    "LOTTERY_POOL_MAX",
    "LOTTERY_TICKET_PRICE",
]
