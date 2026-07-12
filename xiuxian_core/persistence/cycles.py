"""把纯周期规则接到可重启、可抢占的 SQLite 工作队列。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from hashlib import sha256

from ..gameplay.cycles import CycleDiscovery, CycleEngine

from .errors import AggregateNotFound
from .sqlite import CycleCursorRow, CycleWorkItemRow, SqliteDatabase


class CycleWorkStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class CycleCursor:
    scope_id: str
    cycle_id: str
    revision: int
    scanned_through: datetime
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class CycleWorkItem:
    scope_id: str
    cycle_id: str
    instance_id: str
    transaction_id: str
    window_start: datetime
    window_end: datetime
    available_at: datetime
    status: CycleWorkStatus
    attempt_count: int
    lease_owner: str | None
    lease_until: datetime | None
    next_attempt_at: datetime | None
    completed_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class PersistentCycleService:
    """周期发现和执行状态的唯一持久化入口，不读取机器当前时间。"""

    def __init__(self, database: SqliteDatabase, engine: CycleEngine) -> None:
        self.database = database
        self.engine = engine

    def initialize_cursor(
        self,
        scope_id: str,
        cycle_id: str,
        *,
        scanned_from: datetime,
        logical_time: datetime,
    ) -> CycleCursor:
        scope_id = _required_text(scope_id, "scope_id")
        cycle_id = str(self.engine.definitions.require(cycle_id).id)
        scanned_from = _utc(scanned_from, "scanned_from")
        logical_time = _utc(logical_time, "logical_time")
        if scanned_from > logical_time:
            raise ValueError("scanned_from 不能晚于 logical_time")
        with self.database.unit_of_work() as uow:
            existing = uow.load_cycle_cursor(scope_id, cycle_id)
            if existing is None:
                uow.insert_cycle_cursor(
                    scope_id,
                    cycle_id,
                    scanned_from.isoformat(),
                    logical_time.isoformat(),
                )
                existing = uow.load_cycle_cursor(scope_id, cycle_id)
                assert existing is not None
            uow.commit()
        return _cursor(existing)

    def load_cursor(self, scope_id: str, cycle_id: str) -> CycleCursor | None:
        scope_id = _required_text(scope_id, "scope_id")
        cycle_id = str(self.engine.definitions.require(cycle_id).id)
        with self.database.unit_of_work(write=False) as uow:
            row = uow.load_cycle_cursor(scope_id, cycle_id)
        return _cursor(row) if row else None

    def discover(
        self,
        scope_id: str,
        cycle_id: str,
        *,
        through: datetime,
    ) -> CycleDiscovery:
        scope_id = _required_text(scope_id, "scope_id")
        cycle_id = str(self.engine.definitions.require(cycle_id).id)
        through = _utc(through, "through")
        with self.database.unit_of_work() as uow:
            cursor = uow.load_cycle_cursor(scope_id, cycle_id)
            if cursor is None:
                raise AggregateNotFound(f"周期游标尚未初始化：{scope_id}/{cycle_id}")
            if through < _parse(cursor.updated_at):
                raise ValueError("周期扫描逻辑时间不能早于上次游标更新时间")
            discovery = self.engine.discover(
                cycle_id,
                scanned_from=_parse(cursor.scanned_through),
                through=through,
            )
            for window in discovery.windows:
                transaction_id = cycle_transaction_id(
                    scope_id,
                    cycle_id,
                    window.instance_id,
                )
                now = through.isoformat()
                uow.insert_cycle_work_item(
                    CycleWorkItemRow(
                        scope_id,
                        cycle_id,
                        window.instance_id,
                        transaction_id,
                        _utc(window.starts_at, "window.starts_at").isoformat(),
                        _utc(window.ends_at, "window.ends_at").isoformat(),
                        _utc(
                            window.settlement_available_at,
                            "window.settlement_available_at",
                        ).isoformat(),
                        CycleWorkStatus.PENDING.value,
                        0,
                        None,
                        None,
                        None,
                        None,
                        None,
                        now,
                        now,
                    )
                )
            if discovery.advanced_through != _parse(cursor.scanned_through):
                uow.advance_cycle_cursor(
                    scope_id,
                    cycle_id,
                    cursor.revision,
                    _utc(discovery.advanced_through, "advanced_through").isoformat(),
                    through.isoformat(),
                )
            uow.commit()
        return discovery

    def claim(
        self,
        worker_id: str,
        *,
        logical_time: datetime,
        lease_duration: timedelta,
        cycle_id: str | None = None,
    ) -> CycleWorkItem | None:
        worker_id = _required_text(worker_id, "worker_id")
        logical_time = _utc(logical_time, "logical_time")
        if lease_duration <= timedelta(0):
            raise ValueError("lease_duration 必须大于 0")
        selected_cycle = (
            str(self.engine.definitions.require(cycle_id).id)
            if cycle_id is not None
            else None
        )
        with self.database.unit_of_work() as uow:
            row = uow.claim_cycle_work_item(
                worker_id,
                logical_time.isoformat(),
                (logical_time + lease_duration).isoformat(),
                selected_cycle,
            )
            uow.commit()
        return _work_item(row) if row else None

    def heartbeat(
        self,
        transaction_id: str,
        worker_id: str,
        *,
        logical_time: datetime,
        lease_duration: timedelta,
    ) -> CycleWorkItem:
        logical_time = _utc(logical_time, "logical_time")
        if lease_duration <= timedelta(0):
            raise ValueError("lease_duration 必须大于 0")
        transaction_id = _required_text(transaction_id, "transaction_id")
        worker_id = _required_text(worker_id, "worker_id")
        with self.database.unit_of_work() as uow:
            uow.heartbeat_cycle_work_item(
                transaction_id,
                worker_id,
                (logical_time + lease_duration).isoformat(),
                logical_time.isoformat(),
            )
            row = uow.load_cycle_work_item(transaction_id)
            assert row is not None
            uow.commit()
        return _work_item(row)

    def complete(
        self,
        transaction_id: str,
        worker_id: str,
        *,
        logical_time: datetime,
    ) -> CycleWorkItem:
        return self._finish(
            "complete", transaction_id, worker_id, logical_time=logical_time
        )

    def retry(
        self,
        transaction_id: str,
        worker_id: str,
        *,
        retry_at: datetime,
        logical_time: datetime,
        error: str,
    ) -> CycleWorkItem:
        logical_time = _utc(logical_time, "logical_time")
        retry_at = _utc(retry_at, "retry_at")
        if retry_at < logical_time:
            raise ValueError("retry_at 不能早于 logical_time")
        return self._finish(
            "retry",
            transaction_id,
            worker_id,
            logical_time=logical_time,
            retry_at=retry_at,
            error=_error(error),
        )

    def fail(
        self,
        transaction_id: str,
        worker_id: str,
        *,
        logical_time: datetime,
        error: str,
    ) -> CycleWorkItem:
        return self._finish(
            "fail",
            transaction_id,
            worker_id,
            logical_time=logical_time,
            error=_error(error),
        )

    def requeue_failed(
        self,
        transaction_id: str,
        *,
        retry_at: datetime,
        logical_time: datetime,
    ) -> CycleWorkItem:
        transaction_id = _required_text(transaction_id, "transaction_id")
        logical_time = _utc(logical_time, "logical_time")
        retry_at = _utc(retry_at, "retry_at")
        if retry_at < logical_time:
            raise ValueError("retry_at 不能早于 logical_time")
        with self.database.unit_of_work() as uow:
            uow.requeue_failed_cycle_work_item(
                transaction_id,
                retry_at.isoformat(),
                logical_time.isoformat(),
            )
            row = uow.load_cycle_work_item(transaction_id)
            assert row is not None
            uow.commit()
        return _work_item(row)

    def require_work(self, transaction_id: str) -> CycleWorkItem:
        transaction_id = _required_text(transaction_id, "transaction_id")
        with self.database.unit_of_work(write=False) as uow:
            row = uow.load_cycle_work_item(transaction_id)
        if row is None:
            raise AggregateNotFound(f"周期工作项不存在：{transaction_id}")
        return _work_item(row)

    def _finish(
        self,
        action: str,
        transaction_id: str,
        worker_id: str,
        *,
        logical_time: datetime,
        retry_at: datetime | None = None,
        error: str | None = None,
    ) -> CycleWorkItem:
        transaction_id = _required_text(transaction_id, "transaction_id")
        worker_id = _required_text(worker_id, "worker_id")
        logical_time = _utc(logical_time, "logical_time")
        with self.database.unit_of_work() as uow:
            if action == "complete":
                uow.complete_cycle_work_item(
                    transaction_id, worker_id, logical_time.isoformat()
                )
            elif action == "retry":
                assert retry_at is not None and error is not None
                uow.retry_cycle_work_item(
                    transaction_id,
                    worker_id,
                    retry_at.isoformat(),
                    error,
                    logical_time.isoformat(),
                )
            else:
                assert action == "fail" and error is not None
                uow.fail_cycle_work_item(
                    transaction_id,
                    worker_id,
                    error,
                    logical_time.isoformat(),
                )
            row = uow.load_cycle_work_item(transaction_id)
            assert row is not None
            uow.commit()
        return _work_item(row)


def cycle_transaction_id(scope_id: str, cycle_id: str, instance_id: str) -> str:
    """同一周期实例在重启和重放后始终得到相同事务 ID。"""

    values = (
        _required_text(scope_id, "scope_id"),
        _required_text(cycle_id, "cycle_id"),
        _required_text(instance_id, "instance_id"),
    )
    digest = sha256("|".join(values).encode("utf-8")).hexdigest()
    return f"cycle-work:{digest}"


def _cursor(row: CycleCursorRow) -> CycleCursor:
    return CycleCursor(
        row.scope_id,
        row.cycle_id,
        row.revision,
        _parse(row.scanned_through),
        _parse(row.created_at),
        _parse(row.updated_at),
    )


def _work_item(row: CycleWorkItemRow) -> CycleWorkItem:
    return CycleWorkItem(
        row.scope_id,
        row.cycle_id,
        row.instance_id,
        row.transaction_id,
        _parse(row.window_start),
        _parse(row.window_end),
        _parse(row.available_at),
        CycleWorkStatus(row.status),
        row.attempt_count,
        row.lease_owner,
        _optional_time(row.lease_until),
        _optional_time(row.next_attempt_at),
        _optional_time(row.completed_at),
        row.last_error,
        _parse(row.created_at),
        _parse(row.updated_at),
    )


def _utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} 必须包含时区")
    return value.astimezone(timezone.utc)


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return _utc(parsed, "数据库时间")


def _optional_time(value: str | None) -> datetime | None:
    return _parse(value) if value is not None else None


def _required_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} 不能为空")
    return value.strip()


def _error(value: str) -> str:
    value = _required_text(value, "error")
    if len(value) > 2_000:
        raise ValueError("error 不能超过 2000 个字符")
    return value


__all__ = [
    "CycleCursor",
    "CycleWorkItem",
    "CycleWorkStatus",
    "PersistentCycleService",
    "cycle_transaction_id",
]
