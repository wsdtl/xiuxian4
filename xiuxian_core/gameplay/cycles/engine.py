"""纯逻辑时间驱动的周期窗口查询与补偿发现。"""

from __future__ import annotations

from datetime import datetime

from ..ids import StableId
from ..registry import DefinitionRegistry
from .models import CatchUpPolicy, CycleDefinition, CycleDiscovery, CycleWindow
from .schedules import CycleScheduleHandlers, ScheduledWindow


class CycleEngine:
    def __init__(
        self,
        definitions: DefinitionRegistry[CycleDefinition],
        handlers: CycleScheduleHandlers | None = None,
    ) -> None:
        self.definitions = definitions
        self.handlers = handlers or CycleScheduleHandlers.with_defaults()
        self._finalize()

    def current_window(
        self,
        cycle_id: StableId,
        *,
        logical_time: datetime,
    ) -> CycleWindow | None:
        _aware(logical_time)
        definition = self.definitions.require(cycle_id)
        scheduled = self.handlers.containing(definition.schedule, logical_time)
        return self._window(definition, scheduled) if scheduled else None

    def discover(
        self,
        cycle_id: StableId,
        *,
        scanned_from: datetime,
        through: datetime,
    ) -> CycleDiscovery:
        _aware(scanned_from)
        _aware(through)
        if through < scanned_from:
            raise ValueError("周期扫描 through 不能早于 scanned_from")
        definition = self.definitions.require(cycle_id)
        if definition.catch_up is CatchUpPolicy.DISCARD:
            return CycleDiscovery(
                definition.id,
                scanned_from,
                through,
                through,
                (),
            )
        schedule_after = scanned_from - definition.settlement_delay
        schedule_through = through - definition.settlement_delay
        if definition.catch_up is CatchUpPolicy.LATEST:
            scheduled = self.handlers.latest_ending_at_or_before(
                definition.schedule,
                schedule_through,
            )
            windows = ()
            if scheduled is not None:
                candidate = self._window(definition, scheduled)
                if candidate.settlement_available_at > scanned_from:
                    windows = (candidate,)
            return CycleDiscovery(
                definition.id,
                scanned_from,
                through,
                through,
                windows,
            )

        limit = definition.maximum_backfill_per_scan
        scheduled = self.handlers.ending_between(
            definition.schedule,
            schedule_after,
            schedule_through,
            limit + 1,
        )
        truncated = len(scheduled) > limit
        selected = scheduled[:limit]
        windows = tuple(self._window(definition, value) for value in selected)
        advanced = (
            windows[-1].settlement_available_at
            if truncated and windows
            else through
        )
        return CycleDiscovery(
            definition.id,
            scanned_from,
            through,
            advanced,
            windows,
            truncated,
        )

    def _window(
        self,
        definition: CycleDefinition,
        scheduled: ScheduledWindow,
    ) -> CycleWindow:
        return CycleWindow(
            definition.id,
            f"{definition.id}@{scheduled.key}",
            scheduled.starts_at,
            scheduled.ends_at,
            scheduled.ends_at + definition.settlement_delay,
        )

    def _finalize(self) -> None:
        for definition in self.definitions:
            self.handlers.validate_schedule(definition.schedule)
        self.handlers.freeze()
        self.definitions.freeze()


def _aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("周期逻辑时间必须包含时区")


__all__ = ["CycleEngine"]
