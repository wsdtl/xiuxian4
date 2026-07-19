"""统一公开战报网页；只翻译事实，不参与任何战斗结算。"""

from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from game.app import current_game_services
from game.core.gameplay import HEALTH_CURRENT, SPIRIT_CURRENT
from game.rules.battle_report import (
    KNOWN_BATTLE_EVENT_KINDS,
    BattleReportView,
    StoredBattleEvent,
    StoredBattleFrame,
    StoredBattleSegment,
    StoredBattleTransition,
)
from launch import config


router = APIRouter()

@router.get("/battle/{share_id}", response_class=HTMLResponse)
def public_battle_report(share_id: str) -> HTMLResponse:
    """公开分享页不检查账号归属；随机 share_id 本身就是不可枚举入口。"""

    services = current_game_services()
    report = services.battle_reports.load_public(
        share_id,
        logical_time=datetime.now(ZoneInfo(config.project.timezone)),
    )
    if report is None:
        raise HTTPException(status_code=404, detail="战报不存在或已经过期")
    return HTMLResponse(
        _render_page(report, services),
        headers={
            "Cache-Control": "public, max-age=60",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        },
    )


def _render_page(report: BattleReportView, services) -> str:
    summary = report.summary
    lines = "".join(f"<li>{escape(line)}</li>" for line in summary.lines)
    detail = ""
    if report.detail_available and report.segments:
        view = services.world_views.require(
            report.presentation_skin_id,
            report.presentation_skin_version,
        )
        detail = "".join(_render_segment(segment, view) for segment in report.segments)
    else:
        detail = (
            '<section class="expired"><h2>完整战报已归档</h2>'
            "<p>详细行动保留 7 天；当前仅保留本场结算摘要。</p></section>"
        )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>{escape(summary.title)}</title>
  <style>
    :root {{ color: #18201d; background: #eef1ed; font-family: system-ui, "Microsoft YaHei", sans-serif; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; line-height: 1.65; }}
    main {{ width: min(920px, 100%); margin: 0 auto; padding: 20px 14px 48px; }}
    header, section {{ background: #fff; border: 1px solid #d7ddd8; border-radius: 6px; margin-bottom: 14px; }}
    header {{ padding: 20px; border-top: 4px solid #147d64; }}
    section {{ padding: 16px 18px; }}
    h1 {{ margin: 0 0 6px; font-size: 1.55rem; }}
    h2 {{ margin: 0 0 10px; font-size: 1.08rem; }}
    h3 {{ margin: 16px 0 7px; font-size: 1rem; }}
    p, ol, ul {{ margin: 7px 0; }}
    .outcome {{ color: #9d342c; font-weight: 700; }}
    .meta {{ color: #65706a; font-size: .88rem; }}
    .participants {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 10px; padding: 0; list-style: none; }}
    .participants li {{ border-left: 3px solid #8da19a; padding: 7px 10px; background: #f7f9f7; }}
    .participants strong {{ display: block; }}
    .participant-line {{ color: #4d5953; font-size: .9rem; }}
    details {{ margin-top: 6px; }}
    summary {{ cursor: pointer; color: #147d64; }}
    .timeline {{ padding-left: 1.45rem; }}
    .timeline li {{ padding: 2px 0; }}
    .round {{ color: #147d64; font-weight: 700; }}
    .event-detail {{ display: block; color: #6a746f; font-size: .84rem; }}
    .round-state {{ margin: 7px 0 10px; padding: 8px 10px; border-left: 3px solid #b58a26; background: #fbfaf4; color: #38413d; font-weight: 400; }}
    .round-state div + div {{ margin-top: 5px; }}
    .transition {{ margin: 10px 0; padding: 10px 12px; border-left: 3px solid #8da19a; background: #f7f9f7; }}
    .transition-title {{ font-weight: 700; }}
    .transition-meta {{ color: #65706a; font-size: .86rem; }}
    .event-chain {{ margin: 7px 0; padding-left: 1.35rem; }}
    .frame {{ margin-top: 8px; }}
    .frame > summary {{ font-weight: 600; }}
    .positive {{ color: #147d64; }}
    .negative {{ color: #a23e35; }}
    .expired {{ border-left: 4px solid #b58a26; }}
    @media (max-width: 520px) {{ main {{ padding: 12px 8px 32px; }} header, section {{ padding: 14px; }} }}
  </style>
</head>
<body>
<main>
  <header>
    <h1>{escape(summary.title)}</h1>
    <p class="outcome">{escape(summary.outcome)}</p>
    <ul>{lines}</ul>
    <p class="meta">{escape(_time(report.started_at))} 至 {escape(_time(report.finished_at))}</p>
  </header>
  {detail}
</main>
</body>
</html>"""


def _render_segment(segment: StoredBattleSegment, view) -> str:
    labels = _segment_labels(segment)
    initial = "".join(
        _participant_html(item, view, "初始战斗快照", "初始效果")
        for item in segment.participants
    )
    final = "".join(
        _participant_html(item, view, "结束战斗快照", "结束效果")
        for item in segment.final_participants
    )
    timeline = (
        "".join(
            _transition_html(transition, labels, view)
            for transition in segment.transitions
        )
        if segment.transitions
        else _legacy_timeline_html(segment, labels, view)
    )
    return f"""<section>
  <h2>{escape(segment.title)}</h2>
  <h3>战斗开始状态</h3>
  <ul class="participants">{initial}</ul>
  <h3>逐回合战斗记录</h3>
  <div class="timeline">{timeline}</div>
  <h3>战斗结束状态</h3>
  <ul class="participants">{final}</ul>
  <p class="outcome">{escape(segment.outcome)}</p>
</section>"""


def _segment_labels(segment: StoredBattleSegment) -> dict[str, str]:
    labels = {
        participant.key: participant.label
        for participant in (*segment.participants, *segment.final_participants)
    }
    for transition in segment.transitions:
        for frame in (transition.before, transition.after):
            if frame is None:
                continue
            labels.update(
                {participant.key: participant.label for participant in frame.participants}
            )
    return labels


def _transition_html(
    transition: StoredBattleTransition,
    labels: dict[str, str],
    view,
) -> str:
    title = _transition_title(transition, labels, view)
    facts = _transition_facts(transition, labels, view)
    event_items = []
    for event in transition.events:
        detail = _event_detail(event)
        extra = f'<span class="event-detail">{escape(detail)}</span>' if detail else ""
        event_items.append(f"<li>{escape(_event_text(event, labels, view))}{extra}</li>")
    events = "".join(event_items) or "<li>本次转场没有规则事件。</li>"
    before = (
        _frame_html(transition.before, labels, view, "动作前完整状态")
        if transition.before is not None
        else ""
    )
    after_title = "战斗建立状态" if transition.kind == "start" else "动作后完整状态"
    after = _frame_html(transition.after, labels, view, after_title)
    return (
        '<article class="transition">'
        f'<div class="transition-title">{escape(title)}</div>'
        f'<div class="transition-meta">{escape(facts)}</div>'
        f'<ol class="event-chain">{events}</ol>{before}{after}</article>'
    )


def _transition_title(transition, labels: dict[str, str], view) -> str:
    actor = labels.get(transition.actor_key or "", "战场")
    if transition.kind == "start":
        return "战斗建立"
    if transition.kind == "turn":
        ability = _content_name(view, transition.ability_id or "", "普通行动")
        targets = "、".join(
            labels.get(value, "未知目标") for value in transition.resolved_target_keys
        ) or "无目标"
        return f"第 {transition.after.turn_number} 次行动 · {actor} 使用 {ability} -> {targets}"
    names = {
        "join": "参与者加入",
        "withdraw": "参与者退出",
        "external": "外部战斗阶段",
    }
    subject = _content_name(view, transition.subject_id, names.get(transition.kind, "状态转移"))
    return f"{names.get(transition.kind, '状态转移')} · {subject}"


def _transition_facts(transition, labels: dict[str, str], view) -> str:
    parts = [
        f"序号 {transition.sequence}",
        f"回合 {transition.after.round_number}",
        f"行动 {transition.after.turn_number}",
    ]
    if transition.decision_rule_id:
        parts.append(
            "决策 " + _content_name(view, transition.decision_rule_id, "自动决策")
        )
    if transition.requested_selector_id:
        parts.append(
            "选取 " + _content_name(view, transition.requested_selector_id, "目标选择")
        )
    if transition.requested_target_keys:
        parts.append(
            "请求目标 "
            + "、".join(labels.get(value, "未知目标") for value in transition.requested_target_keys)
        )
    if transition.resolved_target_keys:
        parts.append(
            "实际目标 "
            + "、".join(labels.get(value, "未知目标") for value in transition.resolved_target_keys)
        )
    if transition.action_parameters:
        parts.append(
            "参数 "
            + "、".join(
                f"{key}={_number(value)}"
                for key, value in sorted(transition.action_parameters.items())
            )
        )
    if transition.action_context_tags:
        parts.append("上下文 " + "、".join(transition.action_context_tags))
    return " | ".join(parts)


def _legacy_timeline_html(segment, labels: dict[str, str], view) -> str:
    round_states = {state.round_number: state for state in segment.round_states}
    turn_states = {state.turn_number: state for state in segment.turn_states}
    entries = []
    for event in segment.events:
        detail = _event_detail(event)
        extra = f'<span class="event-detail">{escape(detail)}</span>' if detail else ""
        if event.kind == "combat.round.started":
            state = round_states.get(int(event.values.get("round", 0) or 0))
            if state is not None:
                extra += _round_state_html(state, view)
        elif event.kind == "combat.turn.started":
            state = turn_states.get(int(event.values.get("turn", 0) or 0))
            if state is not None:
                extra += _turn_state_html(state, view, labels)
        entries.append(f"<li>{escape(_event_text(event, labels, view))}{extra}</li>")
    return f'<ol class="event-chain">{"".join(entries) or "<li>本片段没有可展示的行动事实。</li>"}</ol>'


def _event_text(event: StoredBattleEvent, labels: dict[str, str], view) -> str:
    source = labels.get(event.source, "战场")
    target = labels.get(event.target, "战场")
    values = event.values
    subject = _content_name(view, event.subject, "效果")
    if event.kind == "combat.battle.started":
        return "战斗开始"
    if event.kind == "combat.round.started":
        return f"第 {_number(values.get('round', 0))} 回合"
    if event.kind == "combat.turn.started":
        return f"第 {_number(values.get('turn', 0))} 次行动，由 {source} 出手"
    if event.kind == "combat.turn.ended":
        return f"{source} 结束行动"
    if event.kind == "combat.turn.skipped":
        reasons = {
            "defeated": "已经倒下",
            "incapacitated": "无法行动",
            "passed": "放弃行动",
        }
        return f"{source}{reasons.get(str(values.get('reason')), '跳过行动')}"
    if event.kind == "ability.started":
        ability = _content_name(view, event.subject, "招式")
        return f"{source} 对 {target} 发动 {ability}"
    if event.kind == "ability.completed":
        ability = _content_name(view, event.subject, "招式")
        return f"{source} 完成 {ability}"
    if event.kind == "ability.cooldown_started":
        ability = _content_name(view, event.subject, "招式")
        return f"{ability} 进入 {_number(values.get('turns', 0))} 回合冷却"
    if event.kind == "ability.cooldown_changed":
        ability = _content_name(view, event.subject, "招式")
        return f"{ability} 的冷却调整为 {_number(values.get('after', values.get('turns', 0)))} 回合"
    if event.kind == "ability.ready":
        return f"{_content_name(view, event.subject, '招式')} 已可再次使用"
    if event.kind == "resource.changed":
        delta = float(values.get("delta", 0) or 0)
        amount = _number(abs(delta))
        if event.subject == str(HEALTH_CURRENT):
            if delta < 0:
                return f"{target} 受到 {amount} 点伤害"
            if delta > 0:
                return f"{target} 恢复 {amount} 点血气"
        if event.subject == str(SPIRIT_CURRENT) and delta:
            action = "恢复" if delta > 0 else "消耗"
            return f"{target} {action} {amount} 点灵力"
        return f"{target} 的战斗资源发生变化"
    if event.kind == "resource.transferred":
        return (
            f"{target} 被转移 {_number(values.get('drained', 0))} 点资源，"
            f"{source} 获得 {_number(values.get('received', 0))} 点"
        )
    if event.kind == "combat.attack.hit":
        return f"{source} 命中 {target}"
    if event.kind == "combat.attack.missed":
        return f"{target} 避开了 {source} 的攻击"
    if event.kind == "combat.attack.critical":
        multiplier = values.get("critical_multiplier")
        suffix = f"，倍率 {_number(multiplier)}" if multiplier is not None else ""
        return f"{source} 触发暴击{suffix}"
    if event.kind == "combat.attack.blocked":
        return f"{target} 格挡了 {source} 的攻击"
    if event.kind == "combat.damage.dealt":
        return (
            f"{source} 对 {target} 造成 {_number(values.get('effective_damage', 0))} 点有效伤害"
            f"（血气 {_number(values.get('health_damage', 0))}，护盾 {_number(values.get('shield_damage', 0))}）"
        )
    if event.kind == "combat.damage.prevented":
        return f"{target} 完全化解了 {source} 的伤害"
    if event.kind == "combat.damage.intercepted":
        return (
            f"{target} 的伤害被拦截："
            f"{_number(values.get('before_amount', 0))} -> {_number(values.get('after_amount', 0))}"
        )
    if event.kind == "combat.damage.redirected":
        return f"{source} 的 {_number(values.get('amount', 0))} 点伤害转移至 {target}"
    if event.kind == "combat.healing.resolved":
        return f"{source} 为 {target} 恢复 {_number(values.get('actual', 0))} 点血气"
    if event.kind == "combat.shield.granted":
        return f"{target} 获得 {_number(values.get('actual', 0))} 点护盾"
    if event.kind == "combat.shield.damaged":
        return f"{target} 的护盾承受 {_number(values.get('shield_damage', 0))} 点伤害"
    if event.kind == "combat.shield.broken":
        return f"{target} 的护盾破碎"
    if event.kind == "combat.control.resolved":
        result = "生效" if bool(values.get("applied")) else "被抵抗"
        return f"{source} 对 {target} 施加的 {subject}{result}"
    if event.kind == "combat.target.defeated":
        return f"{target} 被击败"
    if event.kind == "combat.action.interrupted":
        return f"{target} 的行动被打断"
    if event.kind == "combat.timeline.extra_turn_requested":
        return f"{source} 获得一次额外行动"
    if event.kind == "combat.timeline.delay_requested":
        return f"{target} 的行动顺序后移 {_number(values.get('positions', 1))} 位"
    if event.kind == "effect.applied":
        stacks = _number(values.get("stacks", 1))
        return f"{target} 获得 {subject}，当前 {stacks} 层"
    if event.kind == "effect.expired":
        return f"{target} 的 {subject} 结束"
    if event.kind == "effect.removed":
        return f"{target} 的 {subject} 被移除"
    if event.kind == "effect.stacks_changed":
        return f"{target} 的 {subject} 调整为 {_number(values.get('stacks', 0))} 层"
    if event.kind == "effect.duration_changed":
        return f"{target} 的 {subject} 剩余 {_number(values.get('remaining_turns', 0))} 回合"
    if event.kind == "effect.choice.selected":
        branch = int(values.get("branch", 0) or 0) + 1
        return f"{source} 的 {subject} 选择了第 {branch} 种效果"
    if event.kind == "trigger.activated":
        return f"{source} 的 {subject} 被触发"
    if event.kind == "combat.participant.joined":
        return f"{source} 加入战斗"
    if event.kind == "combat.phase.activated":
        return f"{source} 进入新的战斗阶段"
    if event.kind == "combat.participant.left":
        return f"{source} 退出战斗"
    if event.kind == "combat.battle.finished":
        return "战斗结束"
    return f"{source} 与 {target} 之间发生一项未命名战斗事件"


def _content_name(view, content_id: str, fallback: str) -> str:
    try:
        return view.projector.name(content_id)
    except KeyError:
        return fallback


def _resource_summary(participant) -> str:
    values = []
    if participant.health is not None and participant.health_maximum is not None:
        values.append(f"，血气 {_number(participant.health)}/{_number(participant.health_maximum)}")
    if participant.spirit is not None and participant.spirit_maximum is not None:
        values.append(f"，灵力 {_number(participant.spirit)}/{_number(participant.spirit_maximum)}")
    return "".join(values)


def _participant_html(participant, view, snapshot_title: str, effect_title: str) -> str:
    abilities = _content_names(view, participant.abilities, "未命名招式")
    effects = []
    for effect_id, stacks in participant.effects.items():
        name = _content_name(view, effect_id, "未命名效果")
        duration = _effect_duration(participant, effect_id)
        text = f"{name} x{stacks}" if stacks > 1 else name
        effects.append(f"{text} ({duration})")
    mechanisms = (
        len(participant.triggers)
        + len(participant.interceptors)
        + len(participant.target_constraints)
    )
    summary_lines = [escape(_resource_summary(participant).lstrip("，"))]
    summary_lines.append("招式: " + escape("、".join(abilities) or "无"))
    summary_lines.append(f"{effect_title}: " + escape("、".join(effects) or "无"))
    cooldowns = "、".join(
        f"{_content_name(view, ability_id, '未命名招式')} {turns}回合"
        for ability_id, turns in sorted(participant.cooldowns.items())
    )
    summary_lines.append("冷却: " + escape(cooldowns or "无"))
    summary_lines.append(f"被动机制: {mechanisms} 项")
    compact = "".join(
        f'<div class="participant-line">{line}</div>'
        for line in summary_lines
        if line
    )
    attributes = "、".join(
        f"{_content_name(view, key, '属性')} {_number(value)}"
        for key, value in sorted(participant.attributes.items())
    )
    resources = "、".join(
        f"{_content_name(view, key, '资源')} {_number(value)}"
        for key, value in sorted(participant.resources.items())
    )
    mechanism_lines = []
    for title, identifiers, fallback in (
        ("触发", participant.triggers, "未命名触发"),
        ("拦截", participant.interceptors, "未命名拦截"),
        ("限制", participant.target_constraints, "未命名限制"),
    ):
        names = _content_names(view, identifiers, fallback)
        if names:
            mechanism_lines.append(f"{title}: {'、'.join(names)}")
    details = "".join(
        f"<p>{escape(line)}</p>"
        for line in (
            f"属性: {attributes}" if attributes else "",
            f"资源: {resources}" if resources else "",
            *mechanism_lines,
        )
        if line
    )
    return (
        f"<li><strong>{escape(participant.label)}</strong>{compact}"
        f"<details><summary>{escape(snapshot_title)}</summary>{details}</details></li>"
    )


def _round_state_html(state, view) -> str:
    return _combat_state_html(state.participants, view, "本回合开始状态")


def _turn_state_html(state, view, labels: dict[str, str]) -> str:
    actor = labels.get(state.actor_key, "行动者")
    return _combat_state_html(
        state.participants,
        view,
        f"{actor} 行动前状态",
    )


def _frame_html(
    frame: StoredBattleFrame,
    labels: dict[str, str],
    view,
    title: str,
) -> str:
    current_actor = labels.get(frame.current_actor_key or "", "无")
    turn_order = " -> ".join(labels.get(value, "未知参与者") for value in frame.turn_order_keys)
    inactive = "、".join(labels.get(value, "未知参与者") for value in frame.inactive_keys) or "无"
    winners = "、".join(frame.winning_team_ids) or "未决"
    progress = "、".join(
        f"{labels.get(key, '未知参与者')}={_number(value)}"
        for key, value in sorted(frame.action_progress.items())
    ) or "无"
    metadata = (
        f"状态: {frame.status} | 当前行动者: {current_actor} | "
        f"行动顺序: {turn_order or '无'} | 失活: {inactive} | "
        f"胜方: {winners} | 行动进度: {progress} | 修订: {frame.revision}"
    )
    state = _combat_state_html(frame.participants, view, title)
    return (
        '<details class="frame">'
        f'<summary>{escape(title)} · 第 {frame.round_number} 回合 / 第 {frame.turn_number} 次行动</summary>'
        f'<p class="transition-meta">{escape(metadata)}</p>{state}</details>'
    )


def _combat_state_html(participant_states, view, title: str) -> str:
    participants = []
    for participant in participant_states:
        positive = []
        negative = []
        neutral = []
        for effect_id, stacks in sorted(participant.effects.items()):
            name = _content_name(view, effect_id, "未命名效果")
            text = f"{name} x{stacks} ({_effect_duration(participant, effect_id)})"
            bucket = _effect_polarity(view, effect_id)
            if bucket == "positive":
                positive.append(text)
            elif bucket == "negative":
                negative.append(text)
            else:
                neutral.append(text)
        cooldowns = "、".join(
            f"{_content_name(view, ability_id, '未命名招式')} {turns}回合"
            for ability_id, turns in sorted(participant.cooldowns.items())
        ) or "无"
        mechanisms = []
        for mechanism_title, identifiers, fallback in (
            ("触发", participant.triggers, "未命名触发"),
            ("拦截", participant.interceptors, "未命名拦截"),
            ("限制", participant.target_constraints, "未命名限制"),
        ):
            names = _content_names(view, identifiers, fallback)
            mechanisms.append(f"{mechanism_title}: {'、'.join(names) or '无'}")
        attributes = "、".join(
            f"{_content_name(view, key, '属性')} {_number(value)}"
            for key, value in sorted(participant.attributes.items())
        ) or "无"
        resources = "、".join(
            f"{_content_name(view, key, '资源')} {_number(value)}"
            for key, value in sorted(participant.resources.items())
        ) or "无"
        participants.append(
            f"<div><strong>{escape(participant.label)}</strong> "
            f"血气 {escape(_number(participant.health))}/{escape(_number(participant.health_maximum))}，"
            f"灵力 {escape(_number(participant.spirit))}/{escape(_number(participant.spirit_maximum))}<br>"
            f'<span class="positive">正面: {escape("、".join(positive) or "无")}</span>；'
            f'<span class="negative">负面: {escape("、".join(negative) or "无")}</span>；'
            f"其他: {escape('、'.join(neutral) or '无')}；冷却: {escape(cooldowns)}<br>"
            f"{escape('；'.join(mechanisms))}"
            f"<details><summary>完整属性与资源</summary>"
            f"<p>属性: {escape(attributes)}</p><p>资源: {escape(resources)}</p></details></div>"
        )
    return (
        f'<div class="round-state"><strong>{escape(title)}</strong>'
        f'{"".join(participants)}</div>'
    )


def _effect_polarity(view, effect_id: str) -> str:
    try:
        tags = view.catalog.effects.require(effect_id).tags
    except KeyError:
        # 武器、装备和敌人阶段以贡献快照进入战斗，不一定拥有 EffectDefinition。
        return "positive"
    if tags.has("status.negative"):
        return "negative"
    if tags.has("status.positive"):
        return "positive"
    return "neutral"


def _effect_duration(participant, effect_id: str) -> str:
    values = participant.effect_remaining_turns.get(effect_id, ())
    if not values or all(value is None for value in values):
        return "永久"
    finite = [value for value in values if value is not None]
    if not finite:
        return "永久"
    low, high = min(finite), max(finite)
    return f"剩余{low}回合" if low == high else f"剩余{low}-{high}回合"


def _event_detail(event: StoredBattleEvent) -> str:
    labels = {
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
        "stacks": "层数",
        "removed_stacks": "移除层数",
        "before": "变化前",
        "after": "变化后",
        "amount": "数值",
        "positions": "后移位数",
        "threshold": "阶段阈值",
        "health_ratio": "当前血气比例",
    }
    ignored = {
        "battle_id",
        "entity_ids",
        "target_ids",
        "turn_order",
        "use_id",
        "instance_id",
        "operation_id",
        "request_id",
        "owner_id",
        "grant_source_id",
    }
    parts = []
    for key, value in event.values.items():
        if key in ignored or key.endswith("_id") or isinstance(value, (dict, list, tuple)):
            continue
        if isinstance(value, bool):
            text = "是" if value else "否"
        elif isinstance(value, (int, float)):
            text = _number(value)
        else:
            text = str(value)
        parts.append(f"{labels.get(key, key)}: {text}")
    return " | ".join(parts)


def _content_names(view, identifiers, fallback: str) -> tuple[str, ...]:
    return tuple(_content_name(view, value, fallback) for value in identifiers)


def _number(value: object) -> str:
    number = float(value or 0)
    return str(round(number)) if number.is_integer() else f"{number:.2f}".rstrip("0").rstrip(".")


def _time(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


__all__ = ["KNOWN_BATTLE_EVENT_KINDS", "public_battle_report", "router"]
