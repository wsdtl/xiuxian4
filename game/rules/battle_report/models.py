"""与具体战斗模式无关的战报数据契约。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Mapping

from game.core.gameplay import RuleEvent


@dataclass(frozen=True)
class BattleReportParticipantDraft:
    """战斗现场提供的参与者快照；entity_id 不会写入公开战报。"""

    entity_id: str
    label: str
    team_id: str
    health: float | None = None
    health_maximum: float | None = None
    spirit: float | None = None
    spirit_maximum: float | None = None
    attributes: Mapping[str, float] = field(default_factory=dict)
    resources: Mapping[str, float] = field(default_factory=dict)
    abilities: tuple[str, ...] = ()
    effects: Mapping[str, int] = field(default_factory=dict)
    effect_remaining_turns: Mapping[str, tuple[int | None, ...]] = field(default_factory=dict)
    cooldowns: Mapping[str, int] = field(default_factory=dict)
    triggers: tuple[str, ...] = ()
    interceptors: tuple[str, ...] = ()
    target_constraints: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.entity_id.strip() or not self.label.strip() or not self.team_id.strip():
            raise ValueError("战报参与者缺少身份、名称或阵营")
        object.__setattr__(self, "attributes", MappingProxyType(dict(self.attributes)))
        object.__setattr__(self, "resources", MappingProxyType(dict(self.resources)))
        object.__setattr__(self, "effects", MappingProxyType(dict(self.effects)))
        object.__setattr__(
            self,
            "effect_remaining_turns",
            MappingProxyType(
                {key: tuple(values) for key, values in self.effect_remaining_turns.items()}
            ),
        )
        object.__setattr__(self, "cooldowns", MappingProxyType(dict(self.cooldowns)))


@dataclass(frozen=True)
class BattleReportRoundStateDraft:
    """一个回合开始时全部参与者的精确战斗状态。"""

    round_number: int
    participants: tuple[BattleReportParticipantDraft, ...]

    def __post_init__(self) -> None:
        if self.round_number < 1 or not self.participants:
            raise ValueError("战报回合状态缺少有效回合或参与者")


@dataclass(frozen=True)
class BattleReportTurnStateDraft:
    """每次角色行动开始前的完整战斗状态。"""

    turn_number: int
    round_number: int
    actor_entity_id: str
    participants: tuple[BattleReportParticipantDraft, ...]

    def __post_init__(self) -> None:
        if self.turn_number < 1 or self.round_number < 1:
            raise ValueError("战报行动状态缺少有效行动或回合")
        if not self.actor_entity_id.strip() or not self.participants:
            raise ValueError("战报行动状态缺少行动者或参与者")


@dataclass(frozen=True)
class BattleReportFrameDraft:
    """战斗核心一个 BattleFrame 的无业务投影。"""

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
        if not self.status.strip() or not self.participants:
            raise ValueError("战报帧缺少状态或参与者")
        object.__setattr__(
            self,
            "action_progress",
            MappingProxyType(
                {str(key): float(value) for key, value in self.action_progress.items()}
            ),
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
        if self.sequence < 0 or not self.kind.strip() or not self.subject_id.strip():
            raise ValueError("战报转场缺少序号、类型或主题")
        object.__setattr__(
            self,
            "action_parameters",
            MappingProxyType(
                {str(key): float(value) for key, value in self.action_parameters.items()}
            ),
        )
        object.__setattr__(self, "requested_target_ids", tuple(self.requested_target_ids))
        object.__setattr__(self, "resolved_target_ids", tuple(self.resolved_target_ids))
        object.__setattr__(self, "action_context_tags", tuple(self.action_context_tags))


@dataclass(frozen=True)
class BattleReportSummary:
    """QQ 摘要和详情过期后的公开内容。"""

    title: str
    outcome: str
    lines: tuple[str, ...] = ()


@dataclass(frozen=True)
class BattleReportSegmentDraft:
    """一个连续战斗片段；探险会向同一份报告追加多个片段。"""

    segment_id: str
    title: str
    participants: tuple[BattleReportParticipantDraft, ...]
    events: tuple[RuleEvent, ...]
    outcome: str
    started_at: datetime
    finished_at: datetime
    final_participants: tuple[BattleReportParticipantDraft, ...] = ()
    round_states: tuple[BattleReportRoundStateDraft, ...] = ()
    turn_states: tuple[BattleReportTurnStateDraft, ...] = ()
    transitions: tuple[BattleReportTransitionDraft, ...] = ()

    def __post_init__(self) -> None:
        if not self.segment_id.strip() or not self.title.strip():
            raise ValueError("战报片段缺少身份或标题")
        if not self.participants:
            raise ValueError("战报片段至少需要一个参与者")
        if not self.final_participants:
            object.__setattr__(self, "final_participants", self.participants)
        for name, values in (
            ("初始", self.participants),
            ("最终", self.final_participants),
        ):
            if len({value.entity_id for value in values}) != len(values):
                raise ValueError(f"战报{name}参与者不能包含重复实体")
        if len({value.round_number for value in self.round_states}) != len(self.round_states):
            raise ValueError("战报回合状态不能包含重复回合")
        if len({value.turn_number for value in self.turn_states}) != len(self.turn_states):
            raise ValueError("战报行动状态不能包含重复行动")
        if len({value.sequence for value in self.transitions}) != len(self.transitions):
            raise ValueError("战报转场不能包含重复序号")
        _aware(self.started_at, "started_at")
        _aware(self.finished_at, "finished_at")
        if self.finished_at < self.started_at:
            raise ValueError("战报片段结束时间不能早于开始时间")


@dataclass(frozen=True)
class BattleReportDraft:
    """玩法层交给战报服务的统一写入请求。"""

    report_id: str
    mode_id: str
    presentation_skin_id: str
    presentation_skin_version: int
    content_fingerprint: str
    summary: BattleReportSummary
    segment: BattleReportSegmentDraft

    def __post_init__(self) -> None:
        for field_name in (
            "report_id",
            "mode_id",
            "presentation_skin_id",
            "content_fingerprint",
        ):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"战报缺少 {field_name}")
        if self.presentation_skin_version < 1:
            raise ValueError("战报世界皮肤版本必须大于 0")


@dataclass(frozen=True)
class StoredBattleEvent:
    """已将实体身份改写为局部代号的规则事件。"""

    kind: str
    source: str
    target: str
    subject: str
    logical_time: datetime
    values: Mapping[str, object] = field(default_factory=dict)
    phase: str = "resolve"


@dataclass(frozen=True)
class StoredBattleParticipant:
    key: str
    label: str
    team_id: str
    health: float | None = None
    health_maximum: float | None = None
    spirit: float | None = None
    spirit_maximum: float | None = None
    attributes: Mapping[str, float] = field(default_factory=dict)
    resources: Mapping[str, float] = field(default_factory=dict)
    abilities: tuple[str, ...] = ()
    effects: Mapping[str, int] = field(default_factory=dict)
    effect_remaining_turns: Mapping[str, tuple[int | None, ...]] = field(default_factory=dict)
    cooldowns: Mapping[str, int] = field(default_factory=dict)
    triggers: tuple[str, ...] = ()
    interceptors: tuple[str, ...] = ()
    target_constraints: tuple[str, ...] = ()


@dataclass(frozen=True)
class StoredBattleSegment:
    segment_id: str
    title: str
    participants: tuple[StoredBattleParticipant, ...]
    events: tuple[StoredBattleEvent, ...]
    outcome: str
    started_at: datetime
    finished_at: datetime
    final_participants: tuple[StoredBattleParticipant, ...] = ()
    round_states: tuple["StoredBattleRoundState", ...] = ()
    turn_states: tuple["StoredBattleTurnState", ...] = ()
    transitions: tuple["StoredBattleTransition", ...] = ()


@dataclass(frozen=True)
class StoredBattleRoundState:
    round_number: int
    participants: tuple[StoredBattleParticipant, ...]


@dataclass(frozen=True)
class StoredBattleTurnState:
    turn_number: int
    round_number: int
    actor_key: str
    participants: tuple[StoredBattleParticipant, ...]


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
    """去除内部实体身份后的公开战斗转场。"""

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
class BattleReportReference:
    report_id: str
    share_id: str


@dataclass(frozen=True)
class BattleReportView:
    share_id: str
    mode_id: str
    presentation_skin_id: str
    presentation_skin_version: int
    content_fingerprint: str
    summary: BattleReportSummary
    started_at: datetime
    finished_at: datetime
    detail_available: bool
    segments: tuple[StoredBattleSegment, ...] = ()


def _aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"战报 {field_name} 必须包含时区")


__all__ = [
    "BattleReportDraft",
    "BattleReportFrameDraft",
    "BattleReportParticipantDraft",
    "BattleReportReference",
    "BattleReportRoundStateDraft",
    "BattleReportSegmentDraft",
    "BattleReportSummary",
    "BattleReportTurnStateDraft",
    "BattleReportTransitionDraft",
    "BattleReportView",
    "StoredBattleEvent",
    "StoredBattleFrame",
    "StoredBattleParticipant",
    "StoredBattleRoundState",
    "StoredBattleSegment",
    "StoredBattleTurnState",
    "StoredBattleTransition",
]
