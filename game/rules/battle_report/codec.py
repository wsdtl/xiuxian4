"""战报片段的紧凑 JSON 与 zlib 编解码。"""

from __future__ import annotations

from datetime import datetime
import json
import zlib

from .models import (
    BattleReportParticipantDraft,
    BattleReportSegmentDraft,
    StoredBattleEvent,
    StoredBattleFrame,
    StoredBattleParticipant,
    StoredBattleRoundState,
    StoredBattleSegment,
    StoredBattleTransition,
    StoredBattleTurnState,
)


BATTLE_REPORT_CODEC_VERSION = 3
COMPRESSION_LEVEL = 6


def encode_segment(draft: BattleReportSegmentDraft) -> tuple[bytes, int]:
    """移除公开身份关联后压缩一个战斗片段。"""

    entity_ids = []
    for participant in (
        *draft.participants,
        *draft.final_participants,
        *(
            participant
            for transition in draft.transitions
            for frame in (transition.before, transition.after)
            if frame is not None
            for participant in frame.participants
        ),
    ):
        if participant.entity_id not in entity_ids:
            entity_ids.append(participant.entity_id)
    aliases = {entity_id: f"p{index}" for index, entity_id in enumerate(entity_ids)}
    participants = [
        _participant_payload(participant, aliases[participant.entity_id])
        for participant in draft.participants
    ]
    # 新格式只在转场内保存事件；无转场的旧调用仍保留平铺事件兼容路径。
    events = (
        [_event_payload(event, aliases) for event in draft.events]
        if not draft.transitions
        else []
    )
    payload = {
        "v": BATTLE_REPORT_CODEC_VERSION,
        "id": draft.segment_id,
        "title": draft.title,
        "participants": participants,
        "final_participants": [
            _participant_payload(
                participant,
                aliases[participant.entity_id],
            )
            for participant in draft.final_participants
        ],
        "round_states": [
            {
                "round": state.round_number,
                "participants": [
                    _participant_payload(participant, aliases[participant.entity_id])
                    for participant in state.participants
                ],
            }
            for state in draft.round_states
        ],
        "turn_states": [
            {
                "turn": state.turn_number,
                "round": state.round_number,
                "actor": aliases[state.actor_entity_id],
                "participants": [
                    _participant_payload(participant, aliases[participant.entity_id])
                    for participant in state.participants
                ],
            }
            for state in draft.turn_states
        ],
        "transitions": [
            {
                "sequence": transition.sequence,
                "kind": transition.kind,
                "subject": transition.subject_id,
                "before": (
                    _frame_payload(transition.before, aliases)
                    if transition.before is not None
                    else None
                ),
                "after": _frame_payload(transition.after, aliases),
                "events": [_event_payload(event, aliases) for event in transition.events],
                "actor": (
                    aliases[transition.actor_entity_id]
                    if transition.actor_entity_id is not None
                    else None
                ),
                "action": transition.action_id,
                "ability": transition.ability_id,
                "decision": transition.decision_rule_id,
                "selector": transition.requested_selector_id,
                "requested": [
                    aliases.get(entity_id, entity_id)
                    for entity_id in transition.requested_target_ids
                ],
                "resolved": [
                    aliases.get(entity_id, entity_id)
                    for entity_id in transition.resolved_target_ids
                ],
                "parameters": dict(transition.action_parameters),
                "tags": transition.action_context_tags,
            }
            for transition in draft.transitions
        ],
        "events": events,
        "outcome": draft.outcome,
        "started_at": draft.started_at.isoformat(),
        "finished_at": draft.finished_at.isoformat(),
    }
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return zlib.compress(raw, level=COMPRESSION_LEVEL), len(raw)


def decode_segment(payload: bytes) -> StoredBattleSegment:
    raw = zlib.decompress(payload)
    value = json.loads(raw.decode("utf-8"))
    if value.get("v") != BATTLE_REPORT_CODEC_VERSION:
        raise ValueError("战报片段编码版本不受支持")
    transitions = tuple(
        _decode_transition(item) for item in value.get("transitions", ())
    )
    events = (
        tuple(_decode_event(item) for item in value["events"])
        if value.get("events")
        else tuple(event for transition in transitions for event in transition.events)
    )
    return StoredBattleSegment(
        segment_id=str(value["id"]),
        title=str(value["title"]),
        participants=tuple(_decode_participant(item) for item in value["participants"]),
        events=events,
        outcome=str(value["outcome"]),
        started_at=datetime.fromisoformat(value["started_at"]),
        finished_at=datetime.fromisoformat(value["finished_at"]),
        final_participants=tuple(
            _decode_participant(item)
            for item in value.get("final_participants", value["participants"])
        ),
        round_states=tuple(
            StoredBattleRoundState(
                round_number=int(state["round"]),
                participants=tuple(
                    _decode_participant(item) for item in state["participants"]
                ),
            )
            for state in value.get("round_states", ())
        ),
        turn_states=tuple(
            StoredBattleTurnState(
                turn_number=int(state["turn"]),
                round_number=int(state["round"]),
                actor_key=str(state["actor"]),
                participants=tuple(
                    _decode_participant(item) for item in state["participants"]
                ),
            )
            for state in value.get("turn_states", ())
        ),
        transitions=transitions,
    )


def _decode_transition(item: dict[str, object]) -> StoredBattleTransition:
    before = item.get("before")
    return StoredBattleTransition(
        sequence=int(item["sequence"]),
        kind=str(item["kind"]),
        subject_id=str(item["subject"]),
        before=(
            _decode_frame(before)
            if before is not None
            else None
        ),
        after=_decode_frame(item["after"]),
        events=tuple(_decode_event(value) for value in item.get("events", ())),
        actor_key=str(item["actor"]) if item.get("actor") is not None else None,
        action_id=str(item["action"]) if item.get("action") is not None else None,
        ability_id=str(item["ability"]) if item.get("ability") is not None else None,
        decision_rule_id=(
            str(item["decision"]) if item.get("decision") is not None else None
        ),
        requested_selector_id=(
            str(item["selector"]) if item.get("selector") is not None else None
        ),
        requested_target_keys=tuple(str(value) for value in item.get("requested", ())),
        resolved_target_keys=tuple(str(value) for value in item.get("resolved", ())),
        action_parameters={
            str(key): float(number)
            for key, number in item.get("parameters", {}).items()
        },
        action_context_tags=tuple(str(value) for value in item.get("tags", ())),
    )


def _decode_frame(item: dict[str, object]) -> StoredBattleFrame:
    return StoredBattleFrame(
        logical_time=datetime.fromisoformat(str(item["at"])),
        round_number=int(item["round"]),
        turn_number=int(item["turn"]),
        status=str(item["status"]),
        revision=int(item["revision"]),
        current_actor_key=(
            str(item["current_actor"])
            if item.get("current_actor") is not None
            else None
        ),
        turn_order_keys=tuple(str(value) for value in item.get("turn_order", ())),
        inactive_keys=tuple(str(value) for value in item.get("inactive", ())),
        winning_team_ids=tuple(str(value) for value in item.get("winners", ())),
        action_progress={
            str(key): float(number)
            for key, number in item.get("progress", {}).items()
        },
        participants=tuple(
            _decode_participant(value) for value in item.get("participants", ())
        ),
    )


def _decode_event(item: dict[str, object]) -> StoredBattleEvent:
    return StoredBattleEvent(
        kind=str(item["k"]),
        source=str(item["s"]),
        target=str(item["t"]),
        subject=str(item["u"]),
        logical_time=datetime.fromisoformat(str(item["at"])),
        values=dict(item.get("v", {})),
        phase=str(item.get("p", "resolve")),
    )


def _event_payload(event, aliases: dict[str, str]) -> dict[str, object]:
    return {
        "k": str(event.kind),
        "s": aliases.get(event.source_id, "system"),
        "t": aliases.get(event.target_id, "system"),
        "u": aliases.get(str(event.subject_id), str(event.subject_id)),
        "at": event.logical_time.isoformat(),
        "v": _json_value(dict(event.values), aliases),
        "p": event.phase.value,
    }


def _frame_payload(frame, aliases: dict[str, str]) -> dict[str, object]:
    return {
        "at": frame.logical_time.isoformat(),
        "round": frame.round_number,
        "turn": frame.turn_number,
        "status": frame.status,
        "revision": frame.revision,
        "current_actor": (
            aliases.get(frame.current_actor_entity_id, frame.current_actor_entity_id)
            if frame.current_actor_entity_id is not None
            else None
        ),
        "turn_order": [aliases.get(value, value) for value in frame.turn_order_entity_ids],
        "inactive": [aliases.get(value, value) for value in frame.inactive_entity_ids],
        "winners": list(frame.winning_team_ids),
        "progress": dict(frame.action_progress),
        "participants": [
            _participant_payload(participant, aliases[participant.entity_id])
            for participant in frame.participants
        ],
    }


def _decode_participant(item: dict[str, object]) -> StoredBattleParticipant:
    return StoredBattleParticipant(
        key=str(item["key"]),
        label=str(item["label"]),
        team_id=str(item["team"]),
        health=_optional_number(item.get("health")),
        health_maximum=_optional_number(item.get("health_maximum")),
        spirit=_optional_number(item.get("spirit")),
        spirit_maximum=_optional_number(item.get("spirit_maximum")),
        attributes={str(key): float(number) for key, number in item.get("attributes", {}).items()},
        resources={str(key): float(number) for key, number in item.get("resources", {}).items()},
        abilities=tuple(str(value) for value in item.get("abilities", ())),
        effects={str(key): int(number) for key, number in item.get("effects", {}).items()},
        effect_remaining_turns={
            str(key): tuple(None if number is None else int(number) for number in values)
            for key, values in item.get("effect_remaining_turns", {}).items()
        },
        cooldowns={str(key): int(number) for key, number in item.get("cooldowns", {}).items()},
        triggers=tuple(str(value) for value in item.get("triggers", ())),
        interceptors=tuple(str(value) for value in item.get("interceptors", ())),
        target_constraints=tuple(str(value) for value in item.get("target_constraints", ())),
    )


def _participant_payload(
    participant: BattleReportParticipantDraft,
    key: str,
) -> dict[str, object]:
    return {
        "key": key,
        "label": participant.label,
        "team": participant.team_id,
        "health": participant.health,
        "health_maximum": participant.health_maximum,
        "spirit": participant.spirit,
        "spirit_maximum": participant.spirit_maximum,
        "attributes": dict(participant.attributes),
        "resources": dict(participant.resources),
        "abilities": participant.abilities,
        "effects": dict(participant.effects),
        "effect_remaining_turns": {
            key: list(values)
            for key, values in participant.effect_remaining_turns.items()
        },
        "cooldowns": dict(participant.cooldowns),
        "triggers": participant.triggers,
        "interceptors": participant.interceptors,
        "target_constraints": participant.target_constraints,
    }


def _json_value(value: object, aliases: dict[str, str]) -> object:
    if isinstance(value, dict):
        return {str(key): _json_value(item, aliases) for key, item in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_json_value(item, aliases) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return aliases.get(value, value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)


def _optional_number(value: object) -> float | None:
    return None if value is None else float(value)


__all__ = [
    "BATTLE_REPORT_CODEC_VERSION",
    "COMPRESSION_LEVEL",
    "decode_segment",
    "encode_segment",
]
