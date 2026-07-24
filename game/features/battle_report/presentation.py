"""把统一战报事实投影成与网页实现无关的公共展示协议。"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
import json
from types import MappingProxyType

from game.core.gameplay import HEALTH_CURRENT, SPIRIT_CURRENT
from game.rules.battle_report import (
    KNOWN_BATTLE_EVENT_KINDS,
    BattleReportView,
    StoredBattleEvent,
    StoredBattleFrame,
    StoredBattleParticipant,
    StoredBattleSegment,
    StoredBattleTransition,
)


PUBLIC_BATTLE_REPORT_SCHEMA = "game.battle_report.presentation"
PUBLIC_BATTLE_REPORT_VERSION = 1


_VALUE_LABELS = {
    "raw": "原始值",
    "requested_damage": "请求伤害",
    "effective_damage": "有效伤害",
    "health_damage": "血气伤害",
    "shield_damage": "护盾伤害",
    "overkill": "溢出伤害",
    "health_before": "伤前血气",
    "health_after": "伤后血气",
    "defense": "防御",
    "effective_defense": "有效防御",
    "defense_multiplier": "防御倍率",
    "rate_multiplier": "增伤倍率",
    "hit_chance": "命中率",
    "hit_roll": "命中判定",
    "critical_chance": "暴击率",
    "critical_roll": "暴击判定",
    "critical_multiplier": "暴击倍率",
    "block_chance": "格挡率",
    "block_roll": "格挡判定",
    "block_reduction": "格挡减免",
    "delta": "变化",
    "current": "当前值",
    "requested": "请求值",
    "actual": "实际值",
    "overheal": "溢出治疗",
    "chance": "成功率",
    "roll": "判定值",
    "duration_turns": "持续回合",
    "remaining_turns": "剩余回合",
    "turns": "回合",
    "stacks": "层数",
    "removed_stacks": "移除层数",
    "before": "变化前",
    "after": "变化后",
    "before_amount": "拦截前",
    "after_amount": "拦截后",
    "amount": "数值",
    "positions": "后移位数",
    "threshold": "阶段阈值",
    "health_ratio": "当前血气比例",
    "behavior_count": "新增能力数",
    "behavior_ids": "新增能力",
    "drained": "转移数值",
    "received": "获得数值",
    "applied": "是否生效",
    "branch": "分支",
    "reason": "原因",
    "failure_code": "失败码",
    "conditions": "未满足条件",
    "round": "回合",
    "turn": "行动",
}

_PRIVATE_VALUE_KEYS = frozenset(
    {
        "battle_id",
        "grant_source_id",
        "instance_id",
        "operation_id",
        "owner_id",
        "request_id",
        "use_id",
    }
)


@dataclass(frozen=True)
class EventPresentationContext:
    labels: Mapping[str, str]
    content_name: Callable[[str, str], str]

    def actor(self, key: str, fallback: str = "战场") -> str:
        return self.labels.get(str(key or ""), fallback)

    def subject(self, event: StoredBattleEvent, fallback: str = "效果") -> str:
        if event.subject in self.labels:
            return self.labels[event.subject]
        return self.content_name(event.subject, fallback)


EventTextRenderer = Callable[[StoredBattleEvent, EventPresentationContext], str]


@dataclass(frozen=True)
class EventPresentationDescriptor:
    kind: str
    label: str
    tone: str
    render: EventTextRenderer


class BattleEventPresentationRegistry:
    """事件语义到公共展示描述的唯一注册表。"""

    def __init__(self) -> None:
        self._entries: dict[str, EventPresentationDescriptor] = {}

    def register(
        self,
        kind: str,
        *,
        label: str,
        tone: str,
        render: EventTextRenderer,
    ) -> None:
        event_kind = str(kind or "").strip()
        if not event_kind or not label.strip() or not tone.strip():
            raise ValueError("战报事件展示注册缺少类型、名称或语气")
        if event_kind in self._entries:
            raise ValueError(f"战报事件展示重复注册: {event_kind}")
        self._entries[event_kind] = EventPresentationDescriptor(
            event_kind,
            label.strip(),
            tone.strip(),
            render,
        )

    @property
    def registered_kinds(self) -> frozenset[str]:
        return frozenset(self._entries)

    def present(
        self,
        event: StoredBattleEvent,
        context: EventPresentationContext,
    ) -> dict[str, object]:
        descriptor = self._entries.get(event.kind)
        source = context.actor(event.source)
        target = context.actor(event.target)
        subject = context.subject(event)
        public_values, omitted_keys = _public_values(event.values)
        if descriptor is None:
            label = "未注册事件"
            tone = "unknown"
            text = f"{source} 对 {target} 触发未识别的战斗事件，关联 {subject}"
        else:
            label = descriptor.label
            tone = descriptor.tone
            text = descriptor.render(event, context)
        return {
            "kind": event.kind,
            "label": label,
            "tone": tone,
            "registered": descriptor is not None,
            "text": text,
            "source": {"key": event.source, "label": source},
            "target": {"key": event.target, "label": target},
            "subject": {"id": event.subject, "label": subject},
            "phase": event.phase,
            "logical_time": event.logical_time.isoformat(),
            "facts": _fact_entries(public_values),
            "raw": {
                "kind": event.kind,
                "source": event.source,
                "target": event.target,
                "subject": event.subject,
                "phase": event.phase,
                "values": public_values,
                "omitted_private_keys": omitted_keys,
            },
        }


class BattleReportPresenter:
    """将一份存储战报投影成前端只需按节点类型渲染的公共文档。"""

    def __init__(
        self,
        view,
        event_registry: BattleEventPresentationRegistry,
    ) -> None:
        self.view = view
        self.event_registry = event_registry
        self._glossary: dict[str, str] = {}

    def build(self, report: BattleReportView) -> dict[str, object]:
        segments = [self._segment(value) for value in report.segments]
        return {
            "schema": PUBLIC_BATTLE_REPORT_SCHEMA,
            "version": PUBLIC_BATTLE_REPORT_VERSION,
            "share_id": report.share_id,
            "mode_id": report.mode_id,
            "presentation": {
                "skin_id": report.presentation_skin_id,
                "skin_version": report.presentation_skin_version,
                "content_fingerprint": report.content_fingerprint,
            },
            "summary": {
                "title": report.summary.title,
                "outcome": report.summary.outcome,
                "lines": list(report.summary.lines),
            },
            "started_at": report.started_at.isoformat(),
            "finished_at": report.finished_at.isoformat(),
            "detail": {
                "available": report.detail_available,
                "retention_notice": (
                    "完整行动保留 7 天；当前仅保留本场结算摘要。"
                    if not report.detail_available
                    else ""
                ),
                "segments": segments,
            },
            "glossary": [
                {"id": content_id, "name": name}
                for content_id, name in sorted(self._glossary.items())
            ],
        }

    def _segment(self, segment: StoredBattleSegment) -> dict[str, object]:
        labels = _segment_labels(segment)
        context = EventPresentationContext(labels, self.content_name)
        if segment.transitions:
            timeline = [
                self._transition(transition, context)
                for transition in segment.transitions
            ]
        else:
            round_states = {state.round_number: state for state in segment.round_states}
            turn_states = {state.turn_number: state for state in segment.turn_states}
            timeline = []
            for event in segment.events:
                state = None
                if event.kind == "combat.round.started":
                    round_state = round_states.get(_integer(event.values.get("round")))
                    if round_state is not None:
                        state = self._state(
                            "本回合开始状态",
                            round_state.participants,
                        )
                elif event.kind == "combat.turn.started":
                    turn_state = turn_states.get(_integer(event.values.get("turn")))
                    if turn_state is not None:
                        actor = labels.get(turn_state.actor_key, "行动者")
                        state = self._state(
                            f"{actor} 行动前状态",
                            turn_state.participants,
                        )
                timeline.append(
                    {
                        "type": "event",
                        "event": self.event_registry.present(event, context),
                        "state": state,
                    }
                )
        return {
            "id": segment.segment_id,
            "title": segment.title,
            "outcome": segment.outcome,
            "started_at": segment.started_at.isoformat(),
            "finished_at": segment.finished_at.isoformat(),
            "initial_participants": [
                self._participant(value) for value in segment.participants
            ],
            "final_participants": [
                self._participant(value) for value in segment.final_participants
            ],
            "timeline": timeline,
        }

    def _transition(
        self,
        transition: StoredBattleTransition,
        context: EventPresentationContext,
    ) -> dict[str, object]:
        after_title = "战斗建立状态" if transition.kind == "start" else "动作后完整状态"
        return {
            "type": "transition",
            "sequence": transition.sequence,
            "kind": transition.kind,
            "title": self._transition_title(transition, context.labels),
            "facts": self._transition_facts(transition, context.labels),
            "events": [
                self.event_registry.present(event, context)
                for event in transition.events
            ],
            "before": (
                self._frame(transition.before, context.labels, "动作前完整状态")
                if transition.before is not None
                else None
            ),
            "after": self._frame(transition.after, context.labels, after_title),
        }

    def _transition_title(
        self,
        transition: StoredBattleTransition,
        labels: Mapping[str, str],
    ) -> str:
        actor = labels.get(transition.actor_key or "", "战场")
        if transition.kind == "start":
            return "战斗建立"
        if transition.kind == "turn":
            ability = self.content_name(transition.ability_id or "", "普通行动")
            targets = "、".join(
                labels.get(value, "未知目标")
                for value in transition.resolved_target_keys
            ) or "无目标"
            return f"{actor} 对 {targets} 使用 {ability}"
        names = {
            "join": "参与者加入",
            "withdraw": "参与者退出",
            "external": "外部战斗阶段",
        }
        fallback = names.get(transition.kind, "状态转移")
        subject = self.content_name(transition.subject_id, fallback)
        return f"{fallback} · {subject}"

    def _transition_facts(
        self,
        transition: StoredBattleTransition,
        labels: Mapping[str, str],
    ) -> list[dict[str, object]]:
        facts: list[dict[str, object]] = [
            {"label": "序号", "value": transition.sequence},
            {"label": "回合", "value": transition.after.round_number},
            {"label": "行动", "value": transition.after.turn_number},
        ]
        if transition.decision_rule_id:
            facts.append(
                {
                    "label": "决策",
                    "value": self.content_name(
                        transition.decision_rule_id,
                        "自动决策",
                    ),
                }
            )
        if transition.requested_selector_id:
            facts.append(
                {
                    "label": "选取",
                    "value": self.content_name(
                        transition.requested_selector_id,
                        "目标选择",
                    ),
                }
            )
        if transition.requested_target_keys:
            facts.append(
                {
                    "label": "请求目标",
                    "value": [
                        labels.get(value, "未知目标")
                        for value in transition.requested_target_keys
                    ],
                }
            )
        if transition.resolved_target_keys:
            facts.append(
                {
                    "label": "实际目标",
                    "value": [
                        labels.get(value, "未知目标")
                        for value in transition.resolved_target_keys
                    ],
                }
            )
        if transition.action_parameters:
            facts.append(
                {
                    "label": "参数",
                    "value": dict(sorted(transition.action_parameters.items())),
                }
            )
        if transition.action_context_tags:
            facts.append(
                {"label": "上下文", "value": list(transition.action_context_tags)}
            )
        return facts

    def _frame(
        self,
        frame: StoredBattleFrame,
        labels: Mapping[str, str],
        title: str,
    ) -> dict[str, object]:
        return {
            "title": title,
            "logical_time": frame.logical_time.isoformat(),
            "round": frame.round_number,
            "turn": frame.turn_number,
            "status": frame.status,
            "revision": frame.revision,
            "current_actor": labels.get(frame.current_actor_key or "", "无"),
            "turn_order": [
                labels.get(value, "未知参与者") for value in frame.turn_order_keys
            ],
            "inactive": [
                labels.get(value, "未知参与者") for value in frame.inactive_keys
            ],
            "winning_teams": list(frame.winning_team_ids),
            "action_progress": [
                {
                    "participant": labels.get(key, "未知参与者"),
                    "value": value,
                }
                for key, value in sorted(frame.action_progress.items())
            ],
            "participants": [self._participant(value) for value in frame.participants],
        }

    def _state(
        self,
        title: str,
        participants: tuple[StoredBattleParticipant, ...],
    ) -> dict[str, object]:
        return {
            "title": title,
            "participants": [self._participant(value) for value in participants],
        }

    def _participant(self, participant: StoredBattleParticipant) -> dict[str, object]:
        effects = []
        for effect_id, stacks in sorted(participant.effects.items()):
            effects.append(
                {
                    "id": effect_id,
                    "name": self.content_name(effect_id, "战斗效果"),
                    "stacks": stacks,
                    "duration": _effect_duration(participant, effect_id),
                    "polarity": self._effect_polarity(effect_id),
                }
            )
        return {
            "key": participant.key,
            "label": participant.label,
            "team_id": participant.team_id,
            "health": {
                "current": participant.health,
                "maximum": participant.health_maximum,
            },
            "spirit": {
                "current": participant.spirit,
                "maximum": participant.spirit_maximum,
            },
            "attributes": self._named_values(participant.attributes, "属性"),
            "resources": self._named_values(participant.resources, "资源"),
            "abilities": self._named_identifiers(participant.abilities, "未命名招式"),
            "effects": effects,
            "cooldowns": [
                {
                    "id": ability_id,
                    "name": self.content_name(ability_id, "未命名招式"),
                    "turns": turns,
                }
                for ability_id, turns in sorted(participant.cooldowns.items())
            ],
            "mechanisms": {
                "triggers": self._named_identifiers(
                    participant.triggers,
                    "未命名触发",
                ),
                "interceptors": self._named_identifiers(
                    participant.interceptors,
                    "未命名拦截",
                ),
                "target_constraints": self._named_identifiers(
                    participant.target_constraints,
                    "未命名限制",
                ),
            },
        }

    def _named_values(
        self,
        values: Mapping[str, float],
        fallback: str,
    ) -> list[dict[str, object]]:
        return [
            {
                "id": content_id,
                "name": self.content_name(content_id, fallback),
                "value": value,
            }
            for content_id, value in sorted(values.items())
        ]

    def _named_identifiers(
        self,
        identifiers: tuple[str, ...],
        fallback: str,
    ) -> list[dict[str, str]]:
        return [
            {"id": content_id, "name": self.content_name(content_id, fallback)}
            for content_id in identifiers
        ]

    def content_name(self, content_id: str, fallback: str) -> str:
        identifier = str(content_id or "").strip()
        if not identifier:
            return fallback
        name = resolve_battle_content_name(self.view, identifier, fallback)
        self._glossary[identifier] = name
        return name

    def _effect_polarity(self, effect_id: str) -> str:
        try:
            tags = self.view.catalog.effects.require(effect_id).tags
        except KeyError:
            return "positive"
        if tags.has("status.negative"):
            return "negative"
        if tags.has("status.positive"):
            return "positive"
        return "neutral"


def build_public_battle_report(
    report: BattleReportView,
    view,
    *,
    event_registry: BattleEventPresentationRegistry | None = None,
) -> dict[str, object]:
    """建立公开战报 DTO；前端不得再解释具体战斗事件。"""

    return BattleReportPresenter(
        view,
        event_registry or BATTLE_EVENT_PRESENTATIONS,
    ).build(report)


def present_battle_event(
    event: StoredBattleEvent,
    labels: Mapping[str, str],
    view,
    *,
    event_registry: BattleEventPresentationRegistry | None = None,
) -> dict[str, object]:
    """单独投影一个事件，供契约测试和未来非网页消费者复用。"""

    presenter = BattleReportPresenter(
        view,
        event_registry or BATTLE_EVENT_PRESENTATIONS,
    )
    context = EventPresentationContext(MappingProxyType(dict(labels)), presenter.content_name)
    return presenter.event_registry.present(event, context)


def resolve_battle_content_name(view, content_id: str, fallback: str) -> str:
    """按历史世界皮肤解析战报机制名，未知 ID 仅留在结构化字段中。"""

    identifier = str(content_id or "").strip()
    if not identifier:
        return fallback
    set_id, marker, pieces = identifier.rpartition(".bonus.pieces_")
    if marker and pieces in {"2", "3", "4"}:
        try:
            return f"{view.projector.name(set_id)}·{pieces}件效果"
        except KeyError:
            pass
    try:
        return view.projector.name(identifier)
    except KeyError:
        return fallback


def _phase_activated_text(
    event: StoredBattleEvent,
    context: EventPresentationContext,
) -> str:
    behavior_ids = event.values.get("behavior_ids", ())
    if not isinstance(behavior_ids, (tuple, list)) or not behavior_ids:
        return f"{context.actor(event.source)} 进入新的战斗阶段"
    names = tuple(
        context.content_name(str(behavior_id), "未知能力")
        for behavior_id in behavior_ids
    )
    return f"{context.actor(event.source)} 进入新的战斗阶段，获得{'、'.join(names)}"


def _build_event_registry() -> BattleEventPresentationRegistry:
    registry = BattleEventPresentationRegistry()

    def add(
        kind: str,
        label: str,
        tone: str,
        render: EventTextRenderer,
    ) -> None:
        registry.register(kind, label=label, tone=tone, render=render)

    add("combat.battle.started", "战斗开始", "phase", lambda _e, _c: "战斗开始")
    add(
        "combat.round.started",
        "回合开始",
        "phase",
        lambda event, _context: f"第 {_number(event.values.get('round'))} 回合",
    )
    add(
        "combat.turn.started",
        "行动开始",
        "action",
        lambda event, context: (
            f"第 {_number(event.values.get('turn'))} 次行动，"
            f"由 {context.actor(event.source)} 出手"
        ),
    )
    add(
        "combat.turn.ended",
        "行动结束",
        "action",
        lambda event, context: f"{context.actor(event.source)} 结束行动",
    )
    add("combat.turn.skipped", "跳过行动", "control", _turn_skipped_text)
    add("ability.started", "发动招式", "action", _ability_started_text)
    add("ability.completed", "完成招式", "action", _ability_completed_text)
    add(
        "ability.cooldown_started",
        "进入冷却",
        "resource",
        _ability_cooldown_started_text,
    )
    add(
        "ability.cooldown_changed",
        "冷却变化",
        "resource",
        _ability_cooldown_changed_text,
    )
    add(
        "ability.ready",
        "招式就绪",
        "resource",
        lambda event, context: f"{context.subject(event, '招式')} 已可再次使用",
    )
    add("resource.changed", "资源变化", "resource", _resource_changed_text)
    add("resource.transferred", "资源转移", "resource", _resource_transferred_text)
    add(
        "combat.attack.hit",
        "攻击命中",
        "damage",
        lambda event, context: (
            f"{context.actor(event.source)} 命中 {context.actor(event.target)}"
        ),
    )
    add(
        "combat.attack.missed",
        "攻击落空",
        "control",
        lambda event, context: (
            f"{context.actor(event.target)} 避开了 {context.actor(event.source)} 的攻击"
        ),
    )
    add("combat.attack.critical", "暴击", "damage", _critical_text)
    add(
        "combat.attack.blocked",
        "格挡",
        "control",
        lambda event, context: (
            f"{context.actor(event.target)} 格挡了 {context.actor(event.source)} 的攻击"
        ),
    )
    add("combat.damage.dealt", "伤害结算", "damage", _damage_dealt_text)
    add(
        "combat.damage.prevented",
        "伤害化解",
        "control",
        lambda event, context: (
            f"{context.actor(event.target)} 完全化解了 "
            f"{context.actor(event.source)} 的伤害"
        ),
    )
    add(
        "combat.damage.intercepted",
        "伤害拦截",
        "control",
        _damage_intercepted_text,
    )
    add(
        "combat.damage.redirected",
        "伤害转移",
        "control",
        _damage_redirected_text,
    )
    add("combat.healing.resolved", "治疗结算", "healing", _healing_text)
    add("combat.target.revived", "目标复起", "healing", _target_revived_text)
    add("combat.shield.granted", "获得护盾", "healing", _shield_granted_text)
    add("combat.shield.damaged", "护盾受击", "damage", _shield_damaged_text)
    add(
        "combat.shield.broken",
        "护盾破碎",
        "damage",
        lambda event, context: f"{context.actor(event.target)} 的护盾破碎",
    )
    add("combat.control.resolved", "控制结算", "control", _control_text)
    add(
        "combat.target.defeated",
        "目标击败",
        "damage",
        lambda event, context: f"{context.actor(event.target)} 被击败",
    )
    add(
        "combat.action.interrupted",
        "行动打断",
        "control",
        lambda event, context: f"{context.actor(event.target)} 的行动被打断",
    )
    add(
        "combat.timeline.extra_turn_requested",
        "额外行动",
        "action",
        lambda event, context: f"{context.actor(event.source)} 获得一次额外行动",
    )
    add(
        "combat.timeline.delay_requested",
        "行动延后",
        "control",
        _timeline_delay_text,
    )
    add("effect.applied", "施加效果", "status", _effect_applied_text)
    add(
        "effect.application.rejected",
        "效果未生效",
        "status",
        _effect_rejected_text,
    )
    add(
        "effect.expired",
        "效果结束",
        "status",
        lambda event, context: (
            f"{context.actor(event.target)} 的 {context.subject(event)} 结束"
        ),
    )
    add(
        "effect.removed",
        "移除效果",
        "status",
        lambda event, context: (
            f"{context.actor(event.target)} 的 {context.subject(event)} 被移除"
        ),
    )
    add("effect.stacks_changed", "层数变化", "status", _effect_stacks_text)
    add("effect.duration_changed", "持续变化", "status", _effect_duration_text)
    add("effect.choice.selected", "效果分支", "status", _effect_choice_text)
    add(
        "trigger.activated",
        "机制触发",
        "status",
        lambda event, context: (
            f"{context.actor(event.source)} 的 {context.subject(event, '触发')} 被触发"
        ),
    )
    add(
        "combat.participant.joined",
        "加入战斗",
        "system",
        lambda event, context: f"{context.actor(event.source)} 加入战斗",
    )
    add(
        "combat.phase.activated",
        "阶段变化",
        "phase",
        _phase_activated_text,
    )
    add(
        "combat.participant.left",
        "退出战斗",
        "system",
        lambda event, context: f"{context.actor(event.source)} 退出战斗",
    )
    add("combat.battle.finished", "战斗结束", "phase", lambda _e, _c: "战斗结束")
    return registry


def _turn_skipped_text(event: StoredBattleEvent, context: EventPresentationContext) -> str:
    reasons = {
        "defeated": "已经倒下",
        "incapacitated": "无法行动",
        "passed": "放弃行动",
    }
    return (
        f"{context.actor(event.source)}"
        f"{reasons.get(str(event.values.get('reason')), '跳过行动')}"
    )


def _ability_started_text(event: StoredBattleEvent, context: EventPresentationContext) -> str:
    return (
        f"{context.actor(event.source)} 对 {context.actor(event.target)} "
        f"发动 {context.subject(event, '招式')}"
    )


def _ability_completed_text(event: StoredBattleEvent, context: EventPresentationContext) -> str:
    return f"{context.actor(event.source)} 完成 {context.subject(event, '招式')}"


def _ability_cooldown_started_text(
    event: StoredBattleEvent,
    context: EventPresentationContext,
) -> str:
    return (
        f"{context.subject(event, '招式')} 进入 "
        f"{_number(event.values.get('turns'))} 回合冷却"
    )


def _ability_cooldown_changed_text(
    event: StoredBattleEvent,
    context: EventPresentationContext,
) -> str:
    after = event.values.get("after", event.values.get("turns"))
    return f"{context.subject(event, '招式')} 的冷却调整为 {_number(after)} 回合"


def _resource_changed_text(event: StoredBattleEvent, context: EventPresentationContext) -> str:
    delta = _float(event.values.get("delta"))
    amount = _number(abs(delta))
    target = context.actor(event.target)
    if event.subject == str(HEALTH_CURRENT):
        if delta < 0:
            return f"{target} 受到 {amount} 点伤害"
        if delta > 0:
            return f"{target} 恢复 {amount} 点血气"
    if event.subject == str(SPIRIT_CURRENT) and delta:
        action = "恢复" if delta > 0 else "消耗"
        return f"{target} {action} {amount} 点灵力"
    return f"{target} 的 {context.subject(event, '战斗资源')} 发生变化"


def _resource_transferred_text(
    event: StoredBattleEvent,
    context: EventPresentationContext,
) -> str:
    return (
        f"{context.actor(event.target)} 被转移 "
        f"{_number(event.values.get('drained'))} 点资源，"
        f"{context.actor(event.source)} 获得 "
        f"{_number(event.values.get('received'))} 点"
    )


def _critical_text(event: StoredBattleEvent, context: EventPresentationContext) -> str:
    multiplier = event.values.get("critical_multiplier")
    suffix = f"，倍率 {_number(multiplier)}" if multiplier is not None else ""
    return f"{context.actor(event.source)} 触发暴击{suffix}"


def _damage_dealt_text(event: StoredBattleEvent, context: EventPresentationContext) -> str:
    return (
        f"{context.actor(event.source)} 对 {context.actor(event.target)} 造成 "
        f"{_number(event.values.get('effective_damage'))} 点有效伤害"
        f"（血气 {_number(event.values.get('health_damage'))}，"
        f"护盾 {_number(event.values.get('shield_damage'))}）"
    )


def _damage_intercepted_text(
    event: StoredBattleEvent,
    context: EventPresentationContext,
) -> str:
    return (
        f"{context.actor(event.target)} 的伤害被拦截："
        f"{_number(event.values.get('before_amount'))} -> "
        f"{_number(event.values.get('after_amount'))}"
    )


def _damage_redirected_text(
    event: StoredBattleEvent,
    context: EventPresentationContext,
) -> str:
    return (
        f"{context.actor(event.source)} 的 {_number(event.values.get('amount'))} 点伤害"
        f"转移至 {context.actor(event.target)}"
    )


def _healing_text(event: StoredBattleEvent, context: EventPresentationContext) -> str:
    return (
        f"{context.actor(event.source)} 为 {context.actor(event.target)} 恢复 "
        f"{_number(event.values.get('actual'))} 点血气"
    )


def _target_revived_text(
    event: StoredBattleEvent,
    context: EventPresentationContext,
) -> str:
    source = context.actor(event.source)
    target = context.actor(event.target)
    if event.source == event.target:
        return f"{target}重新投入战斗"
    return f"{source}使{target}重新投入战斗"


def _shield_granted_text(event: StoredBattleEvent, context: EventPresentationContext) -> str:
    return (
        f"{context.actor(event.target)} 获得 "
        f"{_number(event.values.get('actual'))} 点护盾"
    )


def _shield_damaged_text(event: StoredBattleEvent, context: EventPresentationContext) -> str:
    return (
        f"{context.actor(event.target)} 的护盾承受 "
        f"{_number(event.values.get('shield_damage'))} 点伤害"
    )


def _control_text(event: StoredBattleEvent, context: EventPresentationContext) -> str:
    result = "生效" if bool(event.values.get("applied")) else "被抵抗"
    return (
        f"{context.actor(event.source)} 对 {context.actor(event.target)} 施加的 "
        f"{context.subject(event)}{result}"
    )


def _timeline_delay_text(event: StoredBattleEvent, context: EventPresentationContext) -> str:
    return (
        f"{context.actor(event.target)} 的行动顺序后移 "
        f"{_number(event.values.get('positions', 1))} 位"
    )


def _effect_applied_text(event: StoredBattleEvent, context: EventPresentationContext) -> str:
    stacks = _integer(event.values.get("stacks", 1))
    if stacks <= 0:
        return (
            f"{context.actor(event.target)} 受到 "
            f"{context.subject(event)} 影响"
        )
    return (
        f"{context.actor(event.target)} 获得 {context.subject(event)}，"
        f"当前 {stacks} 层"
    )


def _effect_rejected_text(
    event: StoredBattleEvent,
    context: EventPresentationContext,
) -> str:
    source = context.actor(event.source)
    target = context.actor(event.target)
    subject = context.subject(event)
    reason = str(event.values.get("reason") or "")
    if reason == "control_resisted":
        return f"{target}抵抗了{source}施加的{subject}"
    if reason == "condition_failed":
        return f"{subject}的触发条件未满足，未影响{target}"
    if event.source == event.target:
        return f"{target}未能获得{subject}"
    return f"{target}未受{source}施加的{subject}影响"


def _effect_stacks_text(event: StoredBattleEvent, context: EventPresentationContext) -> str:
    return (
        f"{context.actor(event.target)} 的 {context.subject(event)} 调整为 "
        f"{_number(event.values.get('stacks'))} 层"
    )


def _effect_duration_text(event: StoredBattleEvent, context: EventPresentationContext) -> str:
    return (
        f"{context.actor(event.target)} 的 {context.subject(event)} 剩余 "
        f"{_number(event.values.get('remaining_turns'))} 回合"
    )


def _effect_choice_text(event: StoredBattleEvent, context: EventPresentationContext) -> str:
    branch = _integer(event.values.get("branch")) + 1
    return (
        f"{context.actor(event.source)} 的 {context.subject(event)} "
        f"选择了第 {branch} 种效果"
    )


def _segment_labels(segment: StoredBattleSegment) -> dict[str, str]:
    labels = {
        participant.key: participant.label
        for participant in (*segment.participants, *segment.final_participants)
    }
    for transition in segment.transitions:
        for frame in (transition.before, transition.after):
            if frame is not None:
                labels.update(
                    {participant.key: participant.label for participant in frame.participants}
                )
    return labels


def _effect_duration(participant: StoredBattleParticipant, effect_id: str) -> str:
    values = participant.effect_remaining_turns.get(effect_id, ())
    if not values or all(value is None for value in values):
        return "永久"
    finite = [value for value in values if value is not None]
    if not finite:
        return "永久"
    low, high = min(finite), max(finite)
    return f"剩余{low}回合" if low == high else f"剩余{low}-{high}回合"


def _public_values(values: Mapping[str, object]) -> tuple[dict[str, object], list[str]]:
    omitted = sorted(key for key in values if key in _PRIVATE_VALUE_KEYS)
    return (
        {
            str(key): _json_value(value)
            for key, value in values.items()
            if key not in _PRIVATE_VALUE_KEYS
        },
        omitted,
    )


def _fact_entries(values: Mapping[str, object]) -> list[dict[str, object]]:
    return [
        {
            "key": key,
            "label": _VALUE_LABELS.get(key, key),
            "value": value,
            "display": _display_value(value),
        }
        for key, value in values.items()
    ]


def _json_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_json_value(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def _display_value(value: object) -> str:
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (int, float)):
        return _number(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if value is None:
        return "无"
    return str(value)


def _float(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _integer(value: object) -> int:
    return int(_float(value))


def _number(value: object) -> str:
    number = _float(value)
    return str(round(number)) if number.is_integer() else f"{number:.2f}".rstrip("0").rstrip(".")


BATTLE_EVENT_PRESENTATIONS = _build_event_registry()

if BATTLE_EVENT_PRESENTATIONS.registered_kinds != KNOWN_BATTLE_EVENT_KINDS:
    missing = sorted(KNOWN_BATTLE_EVENT_KINDS - BATTLE_EVENT_PRESENTATIONS.registered_kinds)
    extra = sorted(BATTLE_EVENT_PRESENTATIONS.registered_kinds - KNOWN_BATTLE_EVENT_KINDS)
    raise RuntimeError(f"战报事件展示注册不完整: missing={missing}, extra={extra}")


__all__ = [
    "BATTLE_EVENT_PRESENTATIONS",
    "BattleEventPresentationRegistry",
    "BattleReportPresenter",
    "EventPresentationContext",
    "EventPresentationDescriptor",
    "PUBLIC_BATTLE_REPORT_SCHEMA",
    "PUBLIC_BATTLE_REPORT_VERSION",
    "build_public_battle_report",
    "present_battle_event",
    "resolve_battle_content_name",
]
