"""活动定义、实例、参与贡献、冻结排名与生命周期命令。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from ..events import RuleEvent
from ..ids import StableId, stable_id
from ..registry import DefinitionRegistry


class ActivityStatus(str, Enum):
    SCHEDULED = "scheduled"
    OPEN = "open"
    SETTLING = "settling"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class ActivityTieBreaker(str, Enum):
    EARLIER_JOIN = "earlier_join"
    SUBJECT_ID = "subject_id"


@dataclass(frozen=True)
class ActivityDefinition:
    id: StableId
    version: int
    capacity: int | None = None
    maximum_attempts_per_participant: int | None = None
    minimum_rank_contribution: int = 0
    tie_breaker: ActivityTieBreaker = ActivityTieBreaker.EARLIER_JOIN

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="activity definition id"))
        if self.version < 1 or self.minimum_rank_contribution < 0:
            raise ValueError("活动定义版本或最低贡献无效")
        if self.capacity is not None and self.capacity < 1:
            raise ValueError("活动容量必须大于 0")
        if self.maximum_attempts_per_participant is not None and self.maximum_attempts_per_participant < 1:
            raise ValueError("活动参与次数上限必须大于 0")
        object.__setattr__(self, "tie_breaker", ActivityTieBreaker(self.tie_breaker))


class ActivityCatalog:
    def __init__(self) -> None:
        self.definitions = DefinitionRegistry[ActivityDefinition]("Activity")
        self._finalized = False

    def register(self, definition: ActivityDefinition) -> ActivityDefinition:
        if self._finalized:
            raise RuntimeError("活动目录已经完成组装")
        return self.definitions.register(definition)

    def require(self, definition_id: StableId) -> ActivityDefinition:
        return self.definitions.require(definition_id)

    def finalize(self) -> None:
        if self._finalized:
            return
        self.definitions.freeze()
        self._finalized = True

    @property
    def finalized(self) -> bool:
        return self._finalized


@dataclass(frozen=True)
class ActivityParticipant:
    subject_id: str
    joined_at: datetime
    contribution: int = 0
    attempts: int = 0
    last_participated_at: datetime | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.subject_id.strip() or self.contribution < 0 or self.attempts < 0:
            raise ValueError("活动参与者身份或计数无效")
        _aware(self.joined_at, "ActivityParticipant.joined_at")
        if self.last_participated_at is not None:
            _aware(self.last_participated_at, "ActivityParticipant.last_participated_at")
            if self.last_participated_at < self.joined_at:
                raise ValueError("最后参与时间不能早于加入时间")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class ActivityRankEntry:
    rank: int
    subject_id: str
    contribution: int
    attempts: int
    joined_at: datetime


@dataclass(frozen=True)
class ActivityInstance:
    id: str
    definition_id: StableId
    definition_version: int
    opens_at: datetime
    closes_at: datetime
    status: ActivityStatus = ActivityStatus.SCHEDULED
    participants: Mapping[str, ActivityParticipant] = field(default_factory=dict)
    ranking: tuple[ActivityRankEntry, ...] = ()
    revision: int = 0
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip() or self.definition_version < 1 or self.revision < 0:
            raise ValueError("活动实例身份、版本或 revision 无效")
        object.__setattr__(
            self,
            "definition_id",
            stable_id(self.definition_id, field="activity definition id"),
        )
        _aware(self.opens_at, "ActivityInstance.opens_at")
        _aware(self.closes_at, "ActivityInstance.closes_at")
        if self.closes_at <= self.opens_at:
            raise ValueError("活动关闭时间必须晚于开放时间")
        status = ActivityStatus(self.status)
        participants = dict(self.participants)
        if any(key != value.subject_id for key, value in participants.items()):
            raise ValueError("活动参与者映射键与身份不一致")
        ranking = tuple(self.ranking)
        if status in {ActivityStatus.SCHEDULED, ActivityStatus.OPEN} and ranking:
            raise ValueError("活动结算前不能存在冻结排名")
        if status in {ActivityStatus.SETTLING, ActivityStatus.CLOSED}:
            if [entry.rank for entry in ranking] != list(range(1, len(ranking) + 1)):
                raise ValueError("活动冻结排名必须连续")
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "participants", MappingProxyType(participants))
        object.__setattr__(self, "ranking", ranking)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class ActivityState:
    scope_id: str
    instances: Mapping[str, ActivityInstance] = field(default_factory=dict)
    revision: int = 0

    def __post_init__(self) -> None:
        if not self.scope_id.strip() or self.revision < 0:
            raise ValueError("ActivityState 身份或 revision 无效")
        instances = dict(self.instances)
        if any(key != value.id for key, value in instances.items()):
            raise ValueError("活动实例映射键与 ID 不一致")
        object.__setattr__(self, "instances", MappingProxyType(instances))


@dataclass(frozen=True)
class CreateActivity:
    instance: ActivityInstance


@dataclass(frozen=True)
class OpenActivity:
    instance_id: str


@dataclass(frozen=True)
class JoinActivity:
    instance_id: str
    subject_id: str
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class RecordActivityContribution:
    instance_id: str
    subject_id: str
    amount: int

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValueError("活动贡献不能小于 0")


@dataclass(frozen=True)
class CloseActivity:
    instance_id: str


@dataclass(frozen=True)
class FinalizeActivity:
    instance_id: str


@dataclass(frozen=True)
class CancelActivity:
    instance_id: str


@dataclass(frozen=True)
class ActivityCommand:
    id: str
    actor_id: str
    expected_revision: int
    operation: object

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.actor_id.strip() or self.expected_revision < 0:
            raise ValueError("ActivityCommand 身份或 revision 无效")


@dataclass(frozen=True)
class ActivityExecution:
    command_id: str
    state: ActivityState
    instance: ActivityInstance
    events: tuple[RuleEvent, ...]


def _aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} 必须包含时区")


__all__ = [
    "ActivityCatalog",
    "ActivityCommand",
    "ActivityDefinition",
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
