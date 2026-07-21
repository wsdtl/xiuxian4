"""永久事实、投影检查点、通知收件箱和排名快照持久化。"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from hashlib import sha256
import sqlite3
from typing import Mapping

from ..gameplay.projections import (
    FactRecord,
    NotificationEntry,
    NotificationStatus,
    ProjectionValue,
    RankingSnapshot,
)
from ..gameplay.ids import stable_id

from .errors import ConcurrencyConflict, TransactionMismatch
from .snapshots import SnapshotRepository
from .sqlite import SqliteDatabase


class FactJournalService:
    def __init__(self, database: SqliteDatabase) -> None:
        self.database = database

    def list(
        self,
        *,
        after_offset: int = 0,
        limit: int = 100,
        kinds: tuple[str, ...] = (),
    ) -> tuple[FactRecord, ...]:
        if after_offset < 0 or limit < 1:
            raise ValueError("事实查询偏移或数量无效")
        parameters: list[object] = [after_offset]
        where = "fact_offset > ?"
        if kinds:
            normalized = tuple(stable_id(value, field="fact kind") for value in kinds)
            where += " AND event_kind IN (" + ",".join("?" for _ in normalized) + ")"
            parameters.extend(normalized)
        parameters.append(limit)
        with self.database.unit_of_work(write=False) as uow:
            rows = uow.connection.execute(
                f"""
                SELECT fact_offset, transaction_id, sequence, event_kind, payload, occurred_at
                FROM fact_journal WHERE {where}
                ORDER BY fact_offset LIMIT ?
                """,
                tuple(parameters),
            ).fetchall()
        return tuple(
            FactRecord(
                int(row["fact_offset"]),
                str(row["transaction_id"]),
                int(row["sequence"]),
                str(row["event_kind"]),
                str(row["payload"]),
                datetime.fromisoformat(str(row["occurred_at"])),
            )
            for row in rows
        )

    def maximum_offset(self) -> int:
        with self.database.unit_of_work(write=False) as uow:
            return self.maximum_offset_in_uow(uow)

    @staticmethod
    def maximum_offset_in_uow(uow) -> int:
        """返回调用方事务当前可见的最大永久事实偏移。"""

        row = uow.connection.execute(
            "SELECT COALESCE(MAX(fact_offset), 0) AS value FROM fact_journal"
        ).fetchone()
        return int(row["value"])


class ProjectionStore:
    """只提交次核心已经计算好的投影，不在读取时运行副作用。"""

    def __init__(
        self,
        database: SqliteDatabase,
        snapshots: SnapshotRepository | None = None,
    ) -> None:
        self.database = database
        self.codec = (snapshots or SnapshotRepository()).codec

    def initialize(
        self,
        projector_id: str,
        partition_id: str,
        *,
        logical_time: datetime,
    ) -> None:
        projector_id = stable_id(projector_id, field="projector id")
        partition_id = _non_empty(partition_id, field="projection partition id")
        _aware(logical_time)
        with self.database.unit_of_work() as uow:
            self.initialize_in_uow(
                uow,
                projector_id,
                partition_id,
                logical_time=logical_time,
            )
            uow.commit()

    def maximum_fact_offset(self) -> int:
        with self.database.unit_of_work(write=False) as uow:
            return self.maximum_fact_offset_in_uow(uow)

    @staticmethod
    def maximum_fact_offset_in_uow(uow) -> int:
        """返回调用方事务当前可见的最大永久事实偏移。"""

        row = uow.connection.execute(
            "SELECT COALESCE(MAX(fact_offset), 0) AS value FROM fact_journal"
        ).fetchone()
        return int(row["value"])

    def initialize_in_uow(
        self,
        uow,
        projector_id: str,
        partition_id: str,
        *,
        logical_time: datetime,
    ) -> None:
        """在调用方事务内幂等初始化投影检查点。"""

        projector_id = stable_id(projector_id, field="projector id")
        partition_id = _non_empty(partition_id, field="projection partition id")
        _aware(logical_time)
        uow.connection.execute(
            """
            INSERT OR IGNORE INTO projection_checkpoint(
                projector_id, partition_id, fact_offset, revision, updated_at
            ) VALUES (?, ?, 0, 0, ?)
            """,
            (projector_id, partition_id, logical_time.isoformat()),
        )

    def checkpoint(self, projector_id: str, partition_id: str) -> tuple[int, int] | None:
        projector_id = stable_id(projector_id, field="projector id")
        partition_id = _non_empty(partition_id, field="projection partition id")
        with self.database.unit_of_work(write=False) as uow:
            row = uow.connection.execute(
                """
                SELECT fact_offset, revision FROM projection_checkpoint
                WHERE projector_id = ? AND partition_id = ?
                """,
                (projector_id, partition_id),
            ).fetchone()
        return (int(row["fact_offset"]), int(row["revision"])) if row else None

    def checkpoint_in_uow(
        self,
        uow,
        projector_id: str,
        partition_id: str,
    ) -> tuple[int, int] | None:
        """读取调用方事务当前可见的投影检查点。"""

        projector_id = stable_id(projector_id, field="projector id")
        partition_id = _non_empty(partition_id, field="projection partition id")
        row = uow.connection.execute(
            """
            SELECT fact_offset, revision FROM projection_checkpoint
            WHERE projector_id = ? AND partition_id = ?
            """,
            (projector_id, partition_id),
        ).fetchone()
        return (int(row["fact_offset"]), int(row["revision"])) if row else None

    def records(self, projector_id: str, partition_id: str) -> tuple[ProjectionValue, ...]:
        projector_id = stable_id(projector_id, field="projector id")
        partition_id = _non_empty(partition_id, field="projection partition id")
        with self.database.unit_of_work(write=False) as uow:
            rows = uow.connection.execute(
                """
                SELECT record_key, revision, payload, fact_offset
                FROM projection_record
                WHERE projector_id = ? AND partition_id = ?
                ORDER BY record_key
                """,
                (projector_id, partition_id),
            ).fetchall()
        return self._decode_records(projector_id, partition_id, rows)

    def records_in_uow(
        self,
        uow,
        projector_id: str,
        partition_id: str,
    ) -> tuple[ProjectionValue, ...]:
        """读取调用方事务当前可见的投影记录。"""

        projector_id = stable_id(projector_id, field="projector id")
        partition_id = _non_empty(partition_id, field="projection partition id")
        rows = uow.connection.execute(
            """
            SELECT record_key, revision, payload, fact_offset
            FROM projection_record
            WHERE projector_id = ? AND partition_id = ?
            ORDER BY record_key
            """,
            (projector_id, partition_id),
        ).fetchall()
        return self._decode_records(projector_id, partition_id, rows)

    def record_in_uow(
        self,
        uow,
        projector_id: str,
        partition_id: str,
        record_key: str,
    ) -> ProjectionValue | None:
        """按键读取调用方事务当前可见的一条投影记录。"""

        projector_id = stable_id(projector_id, field="projector id")
        partition_id = _non_empty(partition_id, field="projection partition id")
        record_key = _non_empty(record_key, field="projection record key")
        row = uow.connection.execute(
            """
            SELECT record_key, revision, payload, fact_offset
            FROM projection_record
            WHERE projector_id = ? AND partition_id = ? AND record_key = ?
            """,
            (projector_id, partition_id, record_key),
        ).fetchone()
        if row is None:
            return None
        return self._decode_records(projector_id, partition_id, (row,))[0]

    def _decode_records(self, projector_id, partition_id, rows):
        return tuple(
            ProjectionValue(
                projector_id,
                partition_id,
                str(row["record_key"]),
                int(row["revision"]),
                self.codec.loads(str(row["payload"]), dict),
                int(row["fact_offset"]),
            )
            for row in rows
        )

    def commit(
        self,
        projector_id: str,
        partition_id: str,
        *,
        expected_revision: int,
        through_fact_offset: int,
        updates: Mapping[str, Mapping[str, object]],
        deletes: tuple[str, ...] = (),
        logical_time: datetime,
    ) -> tuple[ProjectionValue, ...]:
        with self.database.unit_of_work() as uow:
            written = self.commit_in_uow(
                uow,
                projector_id,
                partition_id,
                expected_revision=expected_revision,
                through_fact_offset=through_fact_offset,
                updates=updates,
                deletes=deletes,
                logical_time=logical_time,
            )
            uow.commit()
        return written

    def commit_in_uow(
        self,
        uow,
        projector_id: str,
        partition_id: str,
        *,
        expected_revision: int,
        through_fact_offset: int,
        updates: Mapping[str, Mapping[str, object]],
        deletes: tuple[str, ...] = (),
        logical_time: datetime,
    ) -> tuple[ProjectionValue, ...]:
        """把投影记录和检查点推进加入调用方事务，不自行提交。"""

        projector_id = stable_id(projector_id, field="projector id")
        partition_id = _non_empty(partition_id, field="projection partition id")
        _aware(logical_time)
        if expected_revision < 0 or through_fact_offset < 0:
            raise ValueError("投影 revision 或事实偏移无效")
        if set(updates) & set(deletes):
            raise ValueError("同一投影键不能同时更新和删除")
        if len(deletes) != len(set(deletes)):
            raise ValueError("投影删除键不能重复")
        for key in (*updates, *deletes):
            _non_empty(key, field="projection record key")
        checkpoint = self.checkpoint_in_uow(uow, projector_id, partition_id)
        if checkpoint is None:
            raise ValueError("投影检查点尚未初始化")
        current_offset, current_revision = checkpoint
        if current_revision != expected_revision:
            raise ConcurrencyConflict("投影检查点 revision 冲突")
        if through_fact_offset < current_offset:
            raise ValueError("投影事实偏移不能倒退")
        maximum = uow.connection.execute(
            "SELECT COALESCE(MAX(fact_offset), 0) AS value FROM fact_journal"
        ).fetchone()
        if through_fact_offset > int(maximum["value"]):
            raise ValueError("投影不能越过尚不存在的事实")

        timestamp = logical_time.isoformat()
        written = []
        for key, payload in updates.items():
            row = uow.connection.execute(
                """
                SELECT revision FROM projection_record
                WHERE projector_id = ? AND partition_id = ? AND record_key = ?
                """,
                (projector_id, partition_id, key),
            ).fetchone()
            revision = int(row["revision"]) + 1 if row else 0
            encoded = self.codec.dumps(dict(payload))
            uow.connection.execute(
                """
                INSERT INTO projection_record(
                    projector_id, partition_id, record_key, revision,
                    payload, fact_offset, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(projector_id, partition_id, record_key) DO UPDATE SET
                    revision = excluded.revision,
                    payload = excluded.payload,
                    fact_offset = excluded.fact_offset,
                    updated_at = excluded.updated_at
                """,
                (
                    projector_id,
                    partition_id,
                    key,
                    revision,
                    encoded,
                    through_fact_offset,
                    timestamp,
                ),
            )
            written.append(
                ProjectionValue(
                    projector_id,
                    partition_id,
                    key,
                    revision,
                    payload,
                    through_fact_offset,
                )
            )
        for key in deletes:
            uow.connection.execute(
                """
                DELETE FROM projection_record
                WHERE projector_id = ? AND partition_id = ? AND record_key = ?
                """,
                (projector_id, partition_id, key),
            )
        cursor = uow.connection.execute(
            """
            UPDATE projection_checkpoint
            SET fact_offset = ?, revision = revision + 1, updated_at = ?
            WHERE projector_id = ? AND partition_id = ? AND revision = ?
            """,
            (
                through_fact_offset,
                timestamp,
                projector_id,
                partition_id,
                expected_revision,
            ),
        )
        if cursor.rowcount != 1:
            raise ConcurrencyConflict("投影检查点并发更新失败")
        return tuple(written)

    def reset(
        self,
        projector_id: str,
        partition_id: str,
        *,
        expected_revision: int,
        logical_time: datetime,
    ) -> int:
        """显式归零一个投影分区，随后可从永久事实 offset 0 重建。"""

        projector_id = stable_id(projector_id, field="projector id")
        partition_id = _non_empty(partition_id, field="projection partition id")
        if expected_revision < 0:
            raise ValueError("投影 revision 不能小于 0")
        _aware(logical_time)
        with self.database.unit_of_work() as uow:
            uow.connection.execute(
                """
                DELETE FROM projection_record
                WHERE projector_id = ? AND partition_id = ?
                """,
                (projector_id, partition_id),
            )
            cursor = uow.connection.execute(
                """
                UPDATE projection_checkpoint
                SET fact_offset = 0, revision = revision + 1, updated_at = ?
                WHERE projector_id = ? AND partition_id = ? AND revision = ?
                """,
                (
                    logical_time.isoformat(),
                    projector_id,
                    partition_id,
                    expected_revision,
                ),
            )
            if cursor.rowcount != 1:
                raise ConcurrencyConflict("投影归零 revision 冲突")
            uow.commit()
        return expected_revision + 1


class NotificationInboxService:
    def __init__(
        self,
        database: SqliteDatabase,
        snapshots: SnapshotRepository | None = None,
    ) -> None:
        self.database = database
        self.codec = (snapshots or SnapshotRepository()).codec

    def issue(self, entry: NotificationEntry) -> NotificationEntry:
        payload = self.codec.dumps(entry)
        with self.database.unit_of_work() as uow:
            previous = uow.connection.execute(
                """
                SELECT notification_id, payload FROM notification_entry
                WHERE recipient_id = ? AND dedupe_key = ?
                """,
                (entry.recipient_id, entry.dedupe_key),
            ).fetchone()
            if previous is not None:
                restored = self.codec.loads(str(previous["payload"]), NotificationEntry)
                if restored != entry:
                    raise TransactionMismatch("同一通知防重键对应不同内容")
                return restored
            try:
                uow.connection.execute(
                    """
                    INSERT INTO notification_entry(
                        notification_id, recipient_id, kind_id, dedupe_key, priority,
                        source_fact_offset, status, payload, created_at, expires_at,
                        read_at, revision
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry.id,
                        entry.recipient_id,
                        entry.kind_id,
                        entry.dedupe_key,
                        entry.priority,
                        entry.source_fact_offset,
                        entry.status.value,
                        payload,
                        entry.created_at.isoformat(),
                        entry.expires_at.isoformat() if entry.expires_at else None,
                        entry.read_at.isoformat() if entry.read_at else None,
                        entry.revision,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ConcurrencyConflict("通知身份、事实或防重键冲突") from exc
            uow.commit()
        return entry

    def list_unread(
        self,
        recipient_id: str,
        *,
        logical_time: datetime,
        limit: int = 20,
    ) -> tuple[NotificationEntry, ...]:
        _aware(logical_time)
        if limit < 1:
            raise ValueError("通知查询数量必须大于 0")
        with self.database.unit_of_work(write=False) as uow:
            rows = uow.connection.execute(
                """
                SELECT payload FROM notification_entry
                WHERE recipient_id = ? AND status = 'unread'
                  AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY priority DESC, created_at, notification_id
                LIMIT ?
                """,
                (recipient_id, logical_time.isoformat(), limit),
            ).fetchall()
        return tuple(
            self.codec.loads(str(row["payload"]), NotificationEntry) for row in rows
        )

    def count_unread(
        self,
        recipient_id: str,
        *,
        logical_time: datetime,
    ) -> int:
        """只读统计当前有效未读通知，不改变通知状态。"""

        _aware(logical_time)
        normalized_recipient = str(recipient_id or "").strip()
        if not normalized_recipient:
            raise ValueError("通知查询缺少接收主体")
        with self.database.unit_of_work(write=False) as uow:
            row = uow.connection.execute(
                """
                SELECT COUNT(*) AS total FROM notification_entry
                WHERE recipient_id = ? AND status = 'unread'
                  AND (expires_at IS NULL OR expires_at > ?)
                """,
                (normalized_recipient, logical_time.isoformat()),
            ).fetchone()
        return int(row["total"])

    def mark(
        self,
        notification_id: str,
        status: NotificationStatus,
        *,
        expected_revision: int,
        logical_time: datetime,
    ) -> NotificationEntry:
        status = NotificationStatus(status)
        if status is NotificationStatus.UNREAD:
            raise ValueError("通知不能通过 mark 恢复为未读")
        _aware(logical_time)
        with self.database.unit_of_work() as uow:
            row = uow.connection.execute(
                "SELECT payload FROM notification_entry WHERE notification_id = ?",
                (notification_id,),
            ).fetchone()
            if row is None:
                raise ValueError("通知不存在")
            previous = self.codec.loads(str(row["payload"]), NotificationEntry)
            if previous.revision != expected_revision or previous.status is not NotificationStatus.UNREAD:
                raise ConcurrencyConflict("通知 revision 或状态冲突")
            current = replace(
                previous,
                status=status,
                read_at=logical_time,
                revision=previous.revision + 1,
            )
            cursor = uow.connection.execute(
                """
                UPDATE notification_entry
                SET status = ?, payload = ?, read_at = ?, revision = ?
                WHERE notification_id = ? AND revision = ? AND status = 'unread'
                """,
                (
                    current.status.value,
                    self.codec.dumps(current),
                    logical_time.isoformat(),
                    current.revision,
                    notification_id,
                    expected_revision,
                ),
            )
            if cursor.rowcount != 1:
                raise ConcurrencyConflict("通知并发更新失败")
            uow.commit()
        return current


class RankingSnapshotStore:
    def __init__(
        self,
        database: SqliteDatabase,
        snapshots: SnapshotRepository | None = None,
    ) -> None:
        self.database = database
        self.codec = (snapshots or SnapshotRepository()).codec

    def save(self, snapshot: RankingSnapshot) -> RankingSnapshot:
        payload = self.codec.dumps(snapshot)
        fingerprint = sha256(("ranking-snapshot.v1\0" + payload).encode("utf-8")).hexdigest()
        key = (snapshot.board_id, snapshot.scope_id, snapshot.period_id, snapshot.version)
        with self.database.unit_of_work() as uow:
            maximum = uow.connection.execute(
                "SELECT COALESCE(MAX(fact_offset), 0) AS value FROM fact_journal"
            ).fetchone()
            if snapshot.through_fact_offset > int(maximum["value"]):
                raise ValueError("排名快照不能越过尚不存在的事实")
            row = uow.connection.execute(
                """
                SELECT fingerprint, payload FROM ranking_snapshot
                WHERE board_id = ? AND scope_id = ? AND period_id = ? AND version = ?
                """,
                key,
            ).fetchone()
            if row is not None:
                if str(row["fingerprint"]) != fingerprint:
                    raise TransactionMismatch("同一排名快照身份对应不同内容")
                return self.codec.loads(str(row["payload"]), RankingSnapshot)
            uow.connection.execute(
                """
                INSERT INTO ranking_snapshot(
                    board_id, scope_id, period_id, version, fingerprint,
                    payload, frozen_at, through_fact_offset
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    *key,
                    fingerprint,
                    payload,
                    snapshot.frozen_at.isoformat(),
                    snapshot.through_fact_offset,
                ),
            )
            uow.commit()
        return snapshot

    def load(
        self,
        board_id: str,
        scope_id: str,
        period_id: str,
        version: int,
    ) -> RankingSnapshot | None:
        with self.database.unit_of_work(write=False) as uow:
            row = uow.connection.execute(
                """
                SELECT payload FROM ranking_snapshot
                WHERE board_id = ? AND scope_id = ? AND period_id = ? AND version = ?
                """,
                (board_id, scope_id, period_id, version),
            ).fetchone()
        return self.codec.loads(str(row["payload"]), RankingSnapshot) if row else None


def _aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("事实投影逻辑时间必须包含时区")


def _non_empty(value: str, *, field: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field} 不能为空")
    return text


__all__ = [
    "FactJournalService",
    "NotificationInboxService",
    "ProjectionStore",
    "RankingSnapshotStore",
]
