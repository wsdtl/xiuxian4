"""协议和具体玩法无关的事实投影、通知与排名底座。"""

PROJECTION_FOUNDATION_VERSION = "projection.foundation.v1"

from .engine import RankingEngine
from .models import (
    FactRecord,
    NotificationAction,
    NotificationEntry,
    NotificationStatus,
    ProjectionValue,
    RankingCandidate,
    RankingDirection,
    RankingEntry,
    RankingSnapshot,
)

__all__ = [
    "PROJECTION_FOUNDATION_VERSION",
    "FactRecord",
    "NotificationAction",
    "NotificationEntry",
    "NotificationStatus",
    "ProjectionValue",
    "RankingCandidate",
    "RankingDirection",
    "RankingEngine",
    "RankingEntry",
    "RankingSnapshot",
]
