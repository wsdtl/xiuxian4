"""次元灾厄的活动、周期和首版参与参数。"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from game.core.gameplay import (
    ActivityDefinition,
    CatchUpPolicy,
    CycleDefinition,
    FixedIntervalSchedule,
)


DIMENSIONAL_DISASTER_ACTIVITY_ID = "activity.dimensional_disaster"
DIMENSIONAL_DISASTER_CYCLE_EARLY_ID = "cycle.dimensional_disaster.early_week"
DIMENSIONAL_DISASTER_CYCLE_LATE_ID = "cycle.dimensional_disaster.late_week"
DIMENSIONAL_DISASTER_CYCLE_IDS = (
    DIMENSIONAL_DISASTER_CYCLE_EARLY_ID,
    DIMENSIONAL_DISASTER_CYCLE_LATE_ID,
)

DIMENSIONAL_DISASTER_DURATION = timedelta(hours=48)
DIMENSIONAL_DISASTER_DAILY_ATTEMPTS = 2
DIMENSIONAL_DISASTER_BATTLE_ROUNDS = 12
DIMENSIONAL_DISASTER_RECENT_EXCLUSION = 4
DIMENSIONAL_DISASTER_MINIMUM_CONTRIBUTION_RATIO = 0.001
DIMENSIONAL_DISASTER_BUSINESS_DAY_RESET_HOUR = 4
DIMENSIONAL_DISASTER_DRAW_TICKET_CHANCE = 250_000

_ZONE = ZoneInfo("Asia/Shanghai")
_WEEK = timedelta(days=7)


DIMENSIONAL_DISASTER_ACTIVITY = ActivityDefinition(
    DIMENSIONAL_DISASTER_ACTIVITY_ID,
    version=1,
    minimum_rank_contribution=1,
)

DIMENSIONAL_DISASTER_CYCLES = (
    CycleDefinition(
        DIMENSIONAL_DISASTER_CYCLE_EARLY_ID,
        FixedIntervalSchedule(
            datetime(2026, 1, 5, 4, tzinfo=_ZONE),
            _WEEK,
            DIMENSIONAL_DISASTER_DURATION,
        ),
        catch_up=CatchUpPolicy.LATEST,
    ),
    CycleDefinition(
        DIMENSIONAL_DISASTER_CYCLE_LATE_ID,
        FixedIntervalSchedule(
            datetime(2026, 1, 9, 4, tzinfo=_ZONE),
            _WEEK,
            DIMENSIONAL_DISASTER_DURATION,
        ),
        catch_up=CatchUpPolicy.LATEST,
    ),
)


__all__ = [name for name in globals() if name.startswith("DIMENSIONAL_DISASTER_")]
