"""异步行动定义、冻结快照、结果与玩家当前行动状态。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from ..ids import StableId, stable_id
from ..registry import DefinitionRegistry
from ..tags import EMPTY_TAGS, TagSet


ACTION_FOUNDATION_VERSION = "action.foundation.v1"


class ActionSlotKind(str, Enum):
    """行动占用方式；即时行动不占持续槽位。"""

    MAIN = "main"
    COMMISSION = "commission"
    INSTANT = "instant"


class ActionStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"


@dataclass(frozen=True)
class ActionDefinition:
    """内容包声明的行动规则，不包含具体业务结算代码。"""

    id: StableId
    slot_kind: ActionSlotKind
    duration: timedelta
    cancellable: bool = True
    interruptible: bool = True
    tags: TagSet = EMPTY_TAGS
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="action id"))
        object.__setattr__(self, "slot_kind", ActionSlotKind(self.slot_kind))
        if self.duration < timedelta(0):
            raise ValueError("ActionDefinition.duration 不能小于 0")
        if self.slot_kind is ActionSlotKind.INSTANT and self.duration != timedelta(0):
            raise ValueError("即时行动的 duration 必须为 0")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


class ActionCatalog:
    """启动期登记并冻结全部行动定义。"""

    def __init__(self) -> None:
        self.definitions = DefinitionRegistry[ActionDefinition]("Action")
        self._finalized = False

    def register(self, definition: ActionDefinition) -> ActionDefinition:
        if self._finalized:
            raise RuntimeError("行动目录已经完成组装")
        return self.definitions.register(definition)

    def require(self, action_id: StableId) -> ActionDefinition:
        return self.definitions.require(action_id)

    def finalize(self) -> None:
        if self._finalized:
            return
        self.definitions.freeze()
        self._finalized = True

    @property
    def finalized(self) -> bool:
        return self._finalized


@dataclass(frozen=True)
class ActionSnapshot:
    """行动开始时冻结的重放依据；业务附加值只能使用结构化数据。"""

    captured_at: datetime
    ruleset_version: str
    content_fingerprint: str
    random_seed: str
    actor_revision: int
    loadout_revision: int | None = None
    values: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _aware(self.captured_at, "ActionSnapshot.captured_at")
        if not self.ruleset_version.strip():
            raise ValueError("ActionSnapshot.ruleset_version 不能为空")
        if not self.content_fingerprint.strip():
            raise ValueError("ActionSnapshot.content_fingerprint 不能为空")
        if not self.random_seed.strip():
            raise ValueError("ActionSnapshot.random_seed 不能为空")
        if self.actor_revision < 0:
            raise ValueError("ActionSnapshot.actor_revision 不能小于 0")
        if self.loadout_revision is not None and self.loadout_revision < 0:
            raise ValueError("ActionSnapshot.loadout_revision 不能小于 0")
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))


@dataclass(frozen=True)
class ActionResult:
    """行动完成后冻结的领域结果；资产仍由奖励系统结算。"""

    outcome_id: StableId
    resolved_at: datetime
    settlement_id: str | None = None
    facts: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "outcome_id", stable_id(self.outcome_id, field="action outcome id"))
        _aware(self.resolved_at, "ActionResult.resolved_at")
        if self.settlement_id is not None and not self.settlement_id.strip():
            raise ValueError("ActionResult.settlement_id 不能是空字符串")
        object.__setattr__(self, "facts", MappingProxyType(dict(self.facts)))


@dataclass(frozen=True)
class ActionRecord:
    id: str
    definition_id: StableId
    sequence: int
    slot_kind: ActionSlotKind
    status: ActionStatus
    started_at: datetime
    completes_at: datetime
    snapshot: ActionSnapshot
    result: ActionResult | None = None

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("ActionRecord.id 不能为空")
        object.__setattr__(self, "definition_id", stable_id(self.definition_id, field="action id"))
        object.__setattr__(self, "slot_kind", ActionSlotKind(self.slot_kind))
        object.__setattr__(self, "status", ActionStatus(self.status))
        if self.sequence < 1:
            raise ValueError("ActionRecord.sequence 必须大于 0")
        _aware(self.started_at, "ActionRecord.started_at")
        _aware(self.completes_at, "ActionRecord.completes_at")
        if self.completes_at < self.started_at:
            raise ValueError("ActionRecord.completes_at 不能早于 started_at")
        if self.status is ActionStatus.RUNNING and self.result is not None:
            raise ValueError("进行中的行动不能已经拥有结果")
        if self.status is ActionStatus.COMPLETED and self.result is None:
            raise ValueError("已完成行动必须拥有结果")


@dataclass(frozen=True)
class ActionState:
    """只保存正在进行和待领取行动；终态审计由领域事件负责。"""

    owner_id: str
    records: Mapping[str, ActionRecord] = field(default_factory=dict)
    next_sequence: int = 1
    revision: int = 0

    def __post_init__(self) -> None:
        if not self.owner_id.strip():
            raise ValueError("ActionState.owner_id 不能为空")
        records = dict(self.records)
        if any(key != value.id for key, value in records.items()):
            raise ValueError("ActionState.records 的键必须等于行动 ID")
        sequences = [value.sequence for value in records.values()]
        if len(sequences) != len(set(sequences)):
            raise ValueError("ActionState 中行动序号不能重复")
        if self.next_sequence < 1 or self.revision < 0:
            raise ValueError("ActionState 序号或 revision 边界无效")
        if sequences and max(sequences) >= self.next_sequence:
            raise ValueError("ActionState.next_sequence 必须大于已有行动序号")
        object.__setattr__(self, "records", MappingProxyType(records))

    def running(self, slot_kind: ActionSlotKind | None = None) -> tuple[ActionRecord, ...]:
        return tuple(
            sorted(
                (
                    value
                    for value in self.records.values()
                    if value.status is ActionStatus.RUNNING
                    and (slot_kind is None or value.slot_kind is slot_kind)
                ),
                key=lambda value: value.sequence,
            )
        )

    def completed(self, definition_id: StableId | None = None) -> tuple[ActionRecord, ...]:
        return tuple(
            sorted(
                (
                    value
                    for value in self.records.values()
                    if value.status is ActionStatus.COMPLETED
                    and (definition_id is None or value.definition_id == definition_id)
                ),
                key=lambda value: value.sequence,
            )
        )


def _aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} 必须包含时区")


__all__ = [
    "ACTION_FOUNDATION_VERSION",
    "ActionCatalog",
    "ActionDefinition",
    "ActionRecord",
    "ActionResult",
    "ActionSlotKind",
    "ActionSnapshot",
    "ActionState",
    "ActionStatus",
]
