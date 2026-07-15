"""具体游戏的全服活动注册与顶部热点策略。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from game.core.gameplay import ActivityInstance, ActivityStatus, StableId, stable_id


GLOBAL_ACTIVITY_SCOPE_ID = "activity.scope.global"


@dataclass(frozen=True)
class ActivitySpotlightPolicy:
    """控制长活动只在开放初期和结束前进入顶部活动区。"""

    opening_window: timedelta = timedelta(hours=12)
    closing_window: timedelta = timedelta(hours=12)

    def __post_init__(self) -> None:
        if self.opening_window < timedelta(0) or self.closing_window < timedelta(0):
            raise ValueError("活动热点展示窗口不能小于 0")

    def visible(self, instance: ActivityInstance, logical_time: datetime) -> bool:
        _aware(logical_time)
        if instance.status is not ActivityStatus.OPEN:
            return False
        if not instance.opens_at <= logical_time < instance.closes_at:
            return False
        return (
            logical_time < instance.opens_at + self.opening_window
            or logical_time >= instance.closes_at - self.closing_window
        )


@dataclass(frozen=True)
class GlobalActivityRegistration:
    """由活动所属组件声明的全服展示信息。"""

    definition_id: StableId
    priority: int = 0
    spotlight: ActivitySpotlightPolicy = ActivitySpotlightPolicy()
    entry_intent_id: StableId | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "definition_id",
            stable_id(self.definition_id, field="global activity definition id"),
        )
        if self.priority < 0:
            raise ValueError("全服活动优先级不能小于 0")
        if self.entry_intent_id is not None:
            object.__setattr__(
                self,
                "entry_intent_id",
                stable_id(self.entry_intent_id, field="global activity entry intent id"),
            )


@dataclass(frozen=True)
class GlobalActivityView:
    """全服活动实例与注册策略的只读组合。"""

    instance: ActivityInstance
    registration: GlobalActivityRegistration


@dataclass(frozen=True)
class GlobalActivitySelection:
    """顶部最多两个热点活动及剩余热点数量。"""

    activities: tuple[GlobalActivityView, ...] = ()
    additional_count: int = 0

    def __post_init__(self) -> None:
        if self.additional_count < 0:
            raise ValueError("活动热点剩余数量不能小于 0")


def _aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("活动热点逻辑时间必须包含时区")


__all__ = [
    "ActivitySpotlightPolicy",
    "GLOBAL_ACTIVITY_SCOPE_ID",
    "GlobalActivityRegistration",
    "GlobalActivitySelection",
    "GlobalActivityView",
]
