"""规则内核产生的结构化事实。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Mapping

from .ids import StableId, stable_id
from .phases import ExecutionPhase
from .context import RuleContext


@dataclass(frozen=True)
class RuleEvent:
    """一次已经发生的规则事实。

    日志、QQ 消息和网页只负责翻译这些事实，不能反向参与结算。
    """

    kind: StableId
    source_id: str
    target_id: str
    subject_id: StableId
    trace_id: str
    rule_version: StableId
    ruleset_id: StableId
    logical_time: datetime
    values: Mapping[str, object] = field(default_factory=dict)
    phase: ExecutionPhase = ExecutionPhase.RESOLVE

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", stable_id(self.kind, field="event kind"))
        object.__setattr__(self, "subject_id", stable_id(self.subject_id, field="event subject id"))
        object.__setattr__(self, "rule_version", stable_id(self.rule_version, field="rule version"))
        object.__setattr__(self, "ruleset_id", stable_id(self.ruleset_id, field="ruleset id"))
        if not self.trace_id.strip():
            raise ValueError("RuleEvent 缺少 trace_id")
        if self.logical_time.tzinfo is None or self.logical_time.utcoffset() is None:
            raise ValueError("RuleEvent.logical_time 必须包含时区")
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))

    @classmethod
    def from_context(
        cls,
        context: RuleContext,
        *,
        kind: StableId,
        source_id: str,
        target_id: str,
        subject_id: StableId,
        values: Mapping[str, object] | None = None,
        phase: ExecutionPhase | None = None,
    ) -> "RuleEvent":
        """使用 RuleContext 生成带完整审计元数据的事件。"""

        return cls(
            kind=kind,
            source_id=source_id,
            target_id=target_id,
            subject_id=subject_id,
            trace_id=context.trace_id,
            rule_version=context.rule_version,
            ruleset_id=context.ruleset.id,
            logical_time=context.logical_time,
            values=values or {},
            phase=phase or context.phase,
        )


__all__ = ["RuleEvent"]
