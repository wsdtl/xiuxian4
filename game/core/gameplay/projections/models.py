"""长期事实引用、通知语义和不可变排名快照。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from ..ids import StableId, stable_id


@dataclass(frozen=True)
class FactRecord:
    offset: int
    transaction_id: str
    sequence: int
    kind: StableId
    payload: str
    occurred_at: datetime

    def __post_init__(self) -> None:
        if self.offset < 1 or not self.transaction_id.strip() or self.sequence < 0:
            raise ValueError("事实记录身份或序号无效")
        object.__setattr__(self, "kind", stable_id(self.kind, field="fact kind"))
        _aware(self.occurred_at, "FactRecord.occurred_at")


@dataclass(frozen=True)
class ProjectionValue:
    projector_id: StableId
    partition_id: str
    key: str
    revision: int
    payload: Mapping[str, object]
    fact_offset: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "projector_id", stable_id(self.projector_id, field="projector id"))
        if not self.partition_id.strip() or not self.key.strip() or self.revision < 0:
            raise ValueError("投影值身份或 revision 无效")
        if self.fact_offset < 0:
            raise ValueError("投影事实偏移不能小于 0")
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))


class NotificationStatus(str, Enum):
    UNREAD = "unread"
    READ = "read"
    DISMISSED = "dismissed"


@dataclass(frozen=True)
class NotificationAction:
    kind_id: StableId
    payload: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind_id", stable_id(self.kind_id, field="notification action id"))
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))


@dataclass(frozen=True)
class NotificationEntry:
    id: str
    recipient_id: str
    kind_id: StableId
    dedupe_key: str
    priority: int
    source_fact_offset: int
    created_at: datetime
    expires_at: datetime | None = None
    action: NotificationAction | None = None
    data: Mapping[str, object] = field(default_factory=dict)
    status: NotificationStatus = NotificationStatus.UNREAD
    read_at: datetime | None = None
    revision: int = 0

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.recipient_id.strip() or not self.dedupe_key.strip():
            raise ValueError("通知缺少身份或防重键")
        object.__setattr__(self, "kind_id", stable_id(self.kind_id, field="notification kind id"))
        if self.source_fact_offset < 1 or self.revision < 0:
            raise ValueError("通知事实偏移或 revision 无效")
        _aware(self.created_at, "NotificationEntry.created_at")
        if self.expires_at is not None:
            _aware(self.expires_at, "NotificationEntry.expires_at")
            if self.expires_at <= self.created_at:
                raise ValueError("通知期限必须晚于创建时间")
        status = NotificationStatus(self.status)
        if status is NotificationStatus.UNREAD and self.read_at is not None:
            raise ValueError("未读通知不能携带读取时间")
        if status is not NotificationStatus.UNREAD and self.read_at is None:
            raise ValueError("已处理通知必须携带处理时间")
        if self.read_at is not None:
            _aware(self.read_at, "NotificationEntry.read_at")
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "data", MappingProxyType(dict(self.data)))


class RankingDirection(str, Enum):
    DESCENDING = "descending"
    ASCENDING = "ascending"


@dataclass(frozen=True)
class RankingCandidate:
    subject_id: str
    score: int
    tie_value: int = 0

    def __post_init__(self) -> None:
        if not self.subject_id.strip():
            raise ValueError("排名候选缺少主体身份")


@dataclass(frozen=True)
class RankingEntry:
    rank: int
    subject_id: str
    score: int
    tie_value: int


@dataclass(frozen=True)
class RankingSnapshot:
    board_id: StableId
    scope_id: str
    period_id: str
    version: int
    direction: RankingDirection
    entries: tuple[RankingEntry, ...]
    frozen_at: datetime
    through_fact_offset: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "board_id", stable_id(self.board_id, field="ranking board id"))
        if not self.scope_id.strip() or not self.period_id.strip() or self.version < 1:
            raise ValueError("排名快照身份或版本无效")
        direction = RankingDirection(self.direction)
        entries = tuple(self.entries)
        if [entry.rank for entry in entries] != list(range(1, len(entries) + 1)):
            raise ValueError("排名位次必须连续")
        if len({entry.subject_id for entry in entries}) != len(entries):
            raise ValueError("排名主体不能重复")
        _aware(self.frozen_at, "RankingSnapshot.frozen_at")
        if self.through_fact_offset < 0:
            raise ValueError("排名事实偏移不能小于 0")
        object.__setattr__(self, "direction", direction)
        object.__setattr__(self, "entries", entries)


def _aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} 必须包含时区")


__all__ = [
    "FactRecord",
    "NotificationAction",
    "NotificationEntry",
    "NotificationStatus",
    "ProjectionValue",
    "RankingCandidate",
    "RankingDirection",
    "RankingEntry",
    "RankingSnapshot",
]
