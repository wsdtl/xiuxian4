"""协议和具体玩法无关的活动实例与参与结算底座。"""

ACTIVITY_FOUNDATION_VERSION = "activity.foundation.v1"

from .engine import ActivityEngine
from .models import (
    ActivityCatalog,
    ActivityCommand,
    ActivityDefinition,
    ActivityExecution,
    ActivityInstance,
    ActivityParticipant,
    ActivityRankEntry,
    ActivityState,
    ActivityStatus,
    ActivityTieBreaker,
    CancelActivity,
    CloseActivity,
    CreateActivity,
    FinalizeActivity,
    JoinActivity,
    OpenActivity,
    RecordActivityContribution,
)

__all__ = [
    "ACTIVITY_FOUNDATION_VERSION",
    "ActivityCatalog",
    "ActivityCommand",
    "ActivityDefinition",
    "ActivityEngine",
    "ActivityExecution",
    "ActivityInstance",
    "ActivityParticipant",
    "ActivityRankEntry",
    "ActivityState",
    "ActivityStatus",
    "ActivityTieBreaker",
    "CancelActivity",
    "CloseActivity",
    "CreateActivity",
    "FinalizeActivity",
    "JoinActivity",
    "OpenActivity",
    "RecordActivityContribution",
]
