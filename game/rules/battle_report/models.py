"""与具体战斗模式和展示世界无关的战报数据契约。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Mapping

from game.core.gameplay import RuleEvent


@dataclass(frozen=True)
class BattleReportTerm:
    """战斗发生时冻结的一项玩家可见术语。"""

    name: str
    compact_name: str = ""

    def __post_init__(self) -> None:
        name = str(self.name or "").strip()
        if not name:
            raise ValueError("战报术语缺少名称")
        object.__setattr__(self, "name", name)
        object.__setattr__(
            self,
            "compact_name",
            str(self.compact_name or "").strip() or name,
        )


@dataclass(frozen=True)
class BattleReportGear:
    """参战时已经完成世界投影与铭刻覆盖的装备名称。"""

    slot_id: str
    slot_name: str
    name: str

    def __post_init__(self) -> None:
        for field_name in ("slot_id", "slot_name", "name"):
            value = str(getattr(self, field_name) or "").strip()
            if not value:
                raise ValueError(f"战报配装缺少 {field_name}")
            object.__setattr__(self, field_name, value)


@dataclass(frozen=True)
class BattleReportCombatantDraft:
    """只在片段开头保存一次的参战者身份与冻结展示词表。"""

    entity_id: str
    label: str
    team_id: str
    team_label: str
    unit_kind: str
    projection_kind: str
    projection_id: str
    projection_version: int
    terms: Mapping[str, BattleReportTerm] = field(default_factory=dict)
    gear: tuple[BattleReportGear, ...] = ()
    source_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "entity_id",
            "label",
            "team_id",
            "team_label",
            "unit_kind",
            "projection_kind",
            "projection_id",
        ):
            value = str(getattr(self, field_name) or "").strip()
            if not value:
                raise ValueError(f"战报参战者缺少 {field_name}")
            object.__setattr__(self, field_name, value)
        if self.projection_version < 1:
            raise ValueError("战报参战者展示版本必须大于 0")
        normalized = {
            str(content_id).strip(): term
            for content_id, term in self.terms.items()
            if str(content_id).strip()
        }
        if len(normalized) != len(self.terms):
            raise ValueError("战报参战者词表包含空内容 ID")
        object.__setattr__(self, "terms", MappingProxyType(normalized))
        object.__setattr__(self, "gear", tuple(self.gear))
        sources = tuple(str(value).strip() for value in self.source_ids if str(value).strip())
        if len(sources) != len(set(sources)):
            raise ValueError("战报参战者来源 ID 不能重复")
        object.__setattr__(self, "source_ids", sources)


@dataclass(frozen=True)
class BattleReportEffectDraft:
    """不合并的活动效果实例。"""

    instance_id: str
    definition_id: str
    source_id: str
    stacks: int
    remaining_turns: int | None
    polarity: str

    def __post_init__(self) -> None:
        for field_name in ("instance_id", "definition_id", "source_id", "polarity"):
            value = str(getattr(self, field_name) or "").strip()
            if not value:
                raise ValueError(f"战报效果实例缺少 {field_name}")
            object.__setattr__(self, field_name, value)
        if self.stacks < 1:
            raise ValueError("战报效果层数必须大于 0")
        if self.remaining_turns is not None and self.remaining_turns < 1:
            raise ValueError("战报效果剩余回合必须大于 0")


@dataclass(frozen=True)
class BattleReportParticipantDraft:
    """某个状态帧中的纯动态参战者状态。"""

    entity_id: str
    attributes: Mapping[str, float] = field(default_factory=dict)
    resources: Mapping[str, float] = field(default_factory=dict)
    abilities: tuple[str, ...] = ()
    effects: tuple[BattleReportEffectDraft, ...] = ()
    cooldowns: Mapping[str, int] = field(default_factory=dict)
    triggers: tuple[str, ...] = ()
    interceptors: tuple[str, ...] = ()
    target_constraints: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not str(self.entity_id or "").strip():
            raise ValueError("战报参与者状态缺少实体身份")
        object.__setattr__(self, "entity_id", str(self.entity_id).strip())
        object.__setattr__(
            self,
            "attributes",
            MappingProxyType({str(key): float(value) for key, value in self.attributes.items()}),
        )
        object.__setattr__(
            self,
            "resources",
            MappingProxyType({str(key): float(value) for key, value in self.resources.items()}),
        )
        object.__setattr__(
            self,
            "cooldowns",
            MappingProxyType({str(key): int(value) for key, value in self.cooldowns.items()}),
        )
        for field_name in ("abilities", "effects", "triggers", "interceptors", "target_constraints"):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))


@dataclass(frozen=True)
class BattleReportFrameDraft:
    """战斗核心一个 BattleFrame 的无业务动态投影。"""

    logical_time: datetime
    round_number: int
    turn_number: int
    status: str
    revision: int
    current_actor_entity_id: str | None
    turn_order_entity_ids: tuple[str, ...]
    inactive_entity_ids: tuple[str, ...]
    winning_team_ids: tuple[str, ...]
    action_progress: Mapping[str, float]
    participants: tuple[BattleReportParticipantDraft, ...]

    def __post_init__(self) -> None:
        _aware(self.logical_time, "frame.logical_time")
        if self.round_number < 1 or self.turn_number < 0 or self.revision < 0:
            raise ValueError("战报帧的回合、行动或修订编号无效")
        if not str(self.status or "").strip() or not self.participants:
            raise ValueError("战报帧缺少状态或参与者")
        object.__setattr__(self, "status", str(self.status).strip())
        object.__setattr__(
            self,
            "action_progress",
            MappingProxyType({str(key): float(value) for key, value in self.action_progress.items()}),
        )


@dataclass(frozen=True)
class BattleReportTransitionDraft:
    """战斗核心一次状态转移在公开战报中的完整投影。"""

    sequence: int
    kind: str
    subject_id: str
    before: BattleReportFrameDraft | None
    after: BattleReportFrameDraft
    events: tuple[RuleEvent, ...] = ()
    actor_entity_id: str | None = None
    action_id: str | None = None
    ability_id: str | None = None
    decision_rule_id: str | None = None
    requested_selector_id: str | None = None
    requested_target_ids: tuple[str, ...] = ()
    resolved_target_ids: tuple[str, ...] = ()
    action_parameters: Mapping[str, float] = field(default_factory=dict)
    action_context_tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.sequence < 0 or not str(self.kind or "").strip() or not str(self.subject_id or "").strip():
            raise ValueError("战报转场缺少序号、类型或主题")
        object.__setattr__(
            self,
            "action_parameters",
            MappingProxyType({str(key): float(value) for key, value in self.action_parameters.items()}),
        )
        object.__setattr__(self, "requested_target_ids", tuple(self.requested_target_ids))
        object.__setattr__(self, "resolved_target_ids", tuple(self.resolved_target_ids))
        object.__setattr__(self, "action_context_tags", tuple(self.action_context_tags))


@dataclass(frozen=True)
class BattleReportSummary:
    """聊天摘要和详情过期后的公开内容。"""

    title: str
    outcome: str
    lines: tuple[str, ...] = ()
    tone: str = "neutral"

    def __post_init__(self) -> None:
        if not str(self.title or "").strip() or not str(self.outcome or "").strip():
            raise ValueError("战报摘要缺少标题或结局")
        if not str(self.tone or "").strip():
            raise ValueError("战报摘要缺少展示语气")
        object.__setattr__(self, "lines", tuple(str(value) for value in self.lines))


@dataclass(frozen=True)
class BattleReportSegmentDraft:
    """一段自解释的连续战斗；身份清单只保存一次。"""

    segment_id: str
    title: str
    combatants: tuple[BattleReportCombatantDraft, ...]
    initial_participants: tuple[BattleReportParticipantDraft, ...]
    final_participants: tuple[BattleReportParticipantDraft, ...]
    transitions: tuple[BattleReportTransitionDraft, ...]
    source_owners: Mapping[str, str]
    outcome: str
    started_at: datetime
    finished_at: datetime

    def __post_init__(self) -> None:
        if not str(self.segment_id or "").strip() or not str(self.title or "").strip():
            raise ValueError("战报片段缺少身份或标题")
        if not self.combatants or not self.initial_participants or not self.final_participants:
            raise ValueError("战报片段缺少参战者或状态")
        entity_ids = tuple(value.entity_id for value in self.combatants)
        if len(entity_ids) != len(set(entity_ids)):
            raise ValueError("战报参战者清单不能包含重复实体")
        expected = set(entity_ids)
        for label, values in (
            ("初始", self.initial_participants),
            ("最终", self.final_participants),
        ):
            actual = {value.entity_id for value in values}
            if not actual or not actual.issubset(expected) or len(actual) != len(values):
                raise ValueError(f"战报{label}状态包含未知、重复或空参战者")
        if len({value.sequence for value in self.transitions}) != len(self.transitions):
            raise ValueError("战报转场不能包含重复序号")
        owners = {str(key): str(value) for key, value in self.source_owners.items()}
        if not set(owners.values()).issubset(expected):
            raise ValueError("战报来源图指向未知参战者")
        object.__setattr__(self, "source_owners", MappingProxyType(owners))
        _aware(self.started_at, "started_at")
        _aware(self.finished_at, "finished_at")
        if self.finished_at < self.started_at:
            raise ValueError("战报片段结束时间不能早于开始时间")


@dataclass(frozen=True)
class BattleReportDraft:
    """玩法层交给战报服务的统一写入请求。"""

    report_id: str
    mode_id: str
    content_fingerprint: str
    summary: BattleReportSummary
    segment: BattleReportSegmentDraft

    def __post_init__(self) -> None:
        for field_name in ("report_id", "mode_id", "content_fingerprint"):
            if not str(getattr(self, field_name) or "").strip():
                raise ValueError(f"战报缺少 {field_name}")


@dataclass(frozen=True)
class StoredBattleEvent:
    """已经把全部内部来源改写为局部参战者代号的规则事件。"""

    kind: str
    source: str
    target: str
    subject: str
    logical_time: datetime
    values: Mapping[str, object] = field(default_factory=dict)
    phase: str = "resolve"


@dataclass(frozen=True)
class StoredBattleCombatant:
    key: str
    label: str
    team_id: str
    team_label: str
    unit_kind: str
    projection_kind: str
    projection_id: str
    projection_version: int
    terms: Mapping[str, BattleReportTerm] = field(default_factory=dict)
    gear: tuple[BattleReportGear, ...] = ()


@dataclass(frozen=True)
class StoredBattleEffect:
    key: str
    definition_id: str
    source_key: str
    stacks: int
    remaining_turns: int | None
    polarity: str


@dataclass(frozen=True)
class StoredBattleParticipant:
    key: str
    attributes: Mapping[str, float] = field(default_factory=dict)
    resources: Mapping[str, float] = field(default_factory=dict)
    abilities: tuple[str, ...] = ()
    effects: tuple[StoredBattleEffect, ...] = ()
    cooldowns: Mapping[str, int] = field(default_factory=dict)
    triggers: tuple[str, ...] = ()
    interceptors: tuple[str, ...] = ()
    target_constraints: tuple[str, ...] = ()


@dataclass(frozen=True)
class StoredBattleFrame:
    logical_time: datetime
    round_number: int
    turn_number: int
    status: str
    revision: int
    current_actor_key: str | None
    turn_order_keys: tuple[str, ...]
    inactive_keys: tuple[str, ...]
    winning_team_ids: tuple[str, ...]
    action_progress: Mapping[str, float]
    participants: tuple[StoredBattleParticipant, ...]


@dataclass(frozen=True)
class StoredBattleTransition:
    sequence: int
    kind: str
    subject_id: str
    before: StoredBattleFrame | None
    after: StoredBattleFrame
    events: tuple[StoredBattleEvent, ...]
    actor_key: str | None = None
    action_id: str | None = None
    ability_id: str | None = None
    decision_rule_id: str | None = None
    requested_selector_id: str | None = None
    requested_target_keys: tuple[str, ...] = ()
    resolved_target_keys: tuple[str, ...] = ()
    action_parameters: Mapping[str, float] = field(default_factory=dict)
    action_context_tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class StoredBattleSegment:
    segment_id: str
    title: str
    combatants: tuple[StoredBattleCombatant, ...]
    initial_participants: tuple[StoredBattleParticipant, ...]
    final_participants: tuple[StoredBattleParticipant, ...]
    transitions: tuple[StoredBattleTransition, ...]
    outcome: str
    started_at: datetime
    finished_at: datetime

    @property
    def events(self) -> tuple[StoredBattleEvent, ...]:
        return tuple(event for transition in self.transitions for event in transition.events)


@dataclass(frozen=True)
class BattleReportReference:
    report_id: str
    share_id: str


@dataclass(frozen=True)
class BattleReportView:
    share_id: str
    mode_id: str
    content_fingerprint: str
    summary: BattleReportSummary
    started_at: datetime
    finished_at: datetime
    detail_available: bool
    segments: tuple[StoredBattleSegment, ...] = ()


def _aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"战报 {field_name} 必须包含时区")


__all__ = [name for name in globals() if name.startswith("BattleReport") or name.startswith("StoredBattle")]
