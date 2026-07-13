"""周期窗口、调度声明、补偿策略和发现结果。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from enum import Enum
from types import MappingProxyType
from typing import Mapping, Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..ids import StableId, stable_id


class CycleSchedule(Protocol):
    """具体调度声明由 CycleScheduleHandlers 解释。"""


class CalendarUnit(str, Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class CatchUpPolicy(str, Enum):
    ALL = "all"
    LATEST = "latest"
    DISCARD = "discard"


@dataclass(frozen=True)
class FixedIntervalSchedule:
    anchor_at: datetime
    interval: timedelta
    active_duration: timedelta | None = None

    def __post_init__(self) -> None:
        _aware(self.anchor_at, "FixedIntervalSchedule.anchor_at")
        if self.interval <= timedelta(0):
            raise ValueError("固定周期 interval 必须大于 0")
        duration = self.active_duration or self.interval
        if duration <= timedelta(0) or duration > self.interval:
            raise ValueError("active_duration 必须大于 0 且不能超过 interval")
        object.__setattr__(self, "active_duration", duration)


@dataclass(frozen=True)
class CalendarSchedule:
    timezone: str
    unit: CalendarUnit
    boundary: time = time(0, 0)
    week_start: int = 0

    def __post_init__(self) -> None:
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"未知周期时区：{self.timezone}") from exc
        object.__setattr__(self, "unit", CalendarUnit(self.unit))
        if self.boundary.tzinfo is not None:
            raise ValueError("CalendarSchedule.boundary 只保存当地墙上时间，不能带时区")
        if not 0 <= self.week_start <= 6:
            raise ValueError("week_start 必须在 0 到 6 之间，0 表示周一")


@dataclass(frozen=True)
class ExplicitWindow:
    key: str
    starts_at: datetime
    ends_at: datetime

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("ExplicitWindow.key 不能为空")
        _aware(self.starts_at, "ExplicitWindow.starts_at")
        _aware(self.ends_at, "ExplicitWindow.ends_at")
        if self.ends_at <= self.starts_at:
            raise ValueError("ExplicitWindow.ends_at 必须晚于 starts_at")


@dataclass(frozen=True)
class ExplicitSchedule:
    windows: tuple[ExplicitWindow, ...]

    def __post_init__(self) -> None:
        windows = tuple(sorted(self.windows, key=lambda value: value.starts_at))
        if not windows:
            raise ValueError("ExplicitSchedule.windows 不能为空")
        if len({value.key for value in windows}) != len(windows):
            raise ValueError("ExplicitSchedule.window key 不能重复")
        for previous, current in zip(windows, windows[1:]):
            if current.starts_at < previous.ends_at:
                raise ValueError("ExplicitSchedule 窗口不能重叠")
        object.__setattr__(self, "windows", windows)


@dataclass(frozen=True)
class CycleDefinition:
    id: StableId
    schedule: CycleSchedule
    settlement_delay: timedelta = timedelta(0)
    catch_up: CatchUpPolicy = CatchUpPolicy.ALL
    maximum_backfill_per_scan: int = 128
    metadata: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="cycle id"))
        if self.settlement_delay < timedelta(0):
            raise ValueError("settlement_delay 不能小于 0")
        object.__setattr__(self, "catch_up", CatchUpPolicy(self.catch_up))
        if self.maximum_backfill_per_scan < 1:
            raise ValueError("maximum_backfill_per_scan 必须大于 0")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata or {})))


@dataclass(frozen=True)
class CycleWindow:
    cycle_id: StableId
    instance_id: str
    starts_at: datetime
    ends_at: datetime
    settlement_available_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "cycle_id", stable_id(self.cycle_id, field="cycle id"))
        if not self.instance_id.strip():
            raise ValueError("CycleWindow.instance_id 不能为空")
        for field_name in ("starts_at", "ends_at", "settlement_available_at"):
            _aware(getattr(self, field_name), f"CycleWindow.{field_name}")
        if not self.starts_at < self.ends_at <= self.settlement_available_at:
            raise ValueError("CycleWindow 时间边界无效")


@dataclass(frozen=True)
class CycleDiscovery:
    cycle_id: StableId
    scanned_from: datetime
    requested_through: datetime
    advanced_through: datetime
    windows: tuple[CycleWindow, ...]
    truncated: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "cycle_id", stable_id(self.cycle_id, field="cycle id"))
        for field_name in ("scanned_from", "requested_through", "advanced_through"):
            _aware(getattr(self, field_name), f"CycleDiscovery.{field_name}")
        if self.requested_through < self.scanned_from:
            raise ValueError("周期扫描不能倒退")
        if not self.scanned_from <= self.advanced_through <= self.requested_through:
            raise ValueError("周期扫描推进边界无效")


def _aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} 必须包含时区")


__all__ = [
    "CalendarSchedule",
    "CalendarUnit",
    "CatchUpPolicy",
    "CycleDefinition",
    "CycleDiscovery",
    "CycleSchedule",
    "CycleWindow",
    "ExplicitSchedule",
    "ExplicitWindow",
    "FixedIntervalSchedule",
]
