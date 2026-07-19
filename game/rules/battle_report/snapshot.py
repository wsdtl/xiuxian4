"""把规则实体投影成不含数据库身份的统一战报初始快照。"""

from __future__ import annotations

from game.core.gameplay import (
    HEALTH_CURRENT,
    HEALTH_MAXIMUM,
    SPIRIT_CURRENT,
    SPIRIT_MAXIMUM,
)

from .models import (
    BattleReportFrameDraft,
    BattleReportParticipantDraft,
    BattleReportRoundStateDraft,
    BattleReportTurnStateDraft,
    BattleReportTransitionDraft,
)


def capture_battle_participant(entity, label: str, team_id: str, attribute_resolver):
    snapshot = entity.snapshot(attribute_resolver)
    effects: dict[str, int] = {}
    remaining_turns: dict[str, list[int | None]] = {}
    for effect in entity.active_effects:
        key = str(effect.definition_id)
        effects[key] = effects.get(key, 0) + effect.stacks
        remaining_turns.setdefault(key, []).append(effect.remaining_turns)
    return BattleReportParticipantDraft(
        entity.id,
        label,
        team_id,
        float(entity.resources.get(HEALTH_CURRENT, 0)),
        float(snapshot.values.get(HEALTH_MAXIMUM, 0)),
        float(entity.resources.get(SPIRIT_CURRENT, 0)),
        float(snapshot.values.get(SPIRIT_MAXIMUM, 0)),
        attributes={str(key): value for key, value in snapshot.values.items()},
        resources={str(key): value for key, value in entity.resources.items()},
        abilities=tuple(sorted(str(value) for value in entity.abilities)),
        effects=effects,
        effect_remaining_turns={
            key: tuple(values) for key, values in remaining_turns.items()
        },
        cooldowns={str(key): value for key, value in entity.cooldowns.items()},
        triggers=tuple(sorted(str(value) for value in entity.triggers)),
        interceptors=tuple(
            sorted({str(value.interceptor_id) for value in entity.interceptor_bindings})
        ),
        target_constraints=tuple(
            sorted({str(value.constraint_id) for value in entity.target_constraint_bindings})
        ),
    )


def capture_battle_round_states(
    trace,
    participant_labels,
    attribute_resolver,
) -> tuple[BattleReportRoundStateDraft, ...]:
    """按回合保存真实实体状态，不依赖网页事后猜测状态变化。"""

    return tuple(
        BattleReportRoundStateDraft(
            round_number,
            tuple(
                capture_battle_participant(
                    entities[entity_id],
                    label,
                    team_id,
                    attribute_resolver,
                )
                for entity_id, (label, team_id) in participant_labels.items()
            ),
        )
        for frame in trace.round_frames
        for round_number, entities in ((frame.state.round_number, frame.state.entities),)
    )


def capture_battle_turn_states(
    trace,
    participant_labels,
    attribute_resolver,
) -> tuple[BattleReportTurnStateDraft, ...]:
    return tuple(
        BattleReportTurnStateDraft(
            turn_number,
            round_number,
            actor_id,
            tuple(
                capture_battle_participant(
                    entities[entity_id],
                    label,
                    team_id,
                    attribute_resolver,
                )
                for entity_id, (label, team_id) in participant_labels.items()
            ),
        )
        for transition in trace.turn_transitions
        if transition.before is not None
        for state in (transition.before.state,)
        for turn_number, round_number, actor_id, entities in (
            (
                state.turn_number + 1,
                state.round_number,
                state.current_actor_id,
                state.entities,
            ),
        )
    )


def capture_battle_transitions(
    trace,
    participant_labels,
    attribute_resolver,
) -> tuple[BattleReportTransitionDraft, ...]:
    """把核心轨迹逐项投影为战报转场，不通过事件顺序反推状态。"""

    result = []
    for transition in trace.transitions:
        before = transition.before
        after = transition.after
        before_frame = (
            _capture_battle_frame(before, participant_labels, attribute_resolver)
            if before is not None
            else None
        )
        after_frame = _capture_battle_frame(
            after,
            participant_labels,
            attribute_resolver,
        )
        action = transition.action
        result.append(
            BattleReportTransitionDraft(
                sequence=transition.sequence,
                kind=transition.kind.value,
                subject_id=str(transition.subject_id),
                before=before_frame,
                after=after_frame,
                events=transition.events,
                actor_entity_id=action.actor_id if action is not None else None,
                action_id=action.action_id if action is not None else None,
                ability_id=str(action.ability_id) if action is not None else None,
                decision_rule_id=(
                    str(action.decision_rule_id)
                    if action is not None and action.decision_rule_id is not None
                    else None
                ),
                requested_selector_id=(
                    str(action.targets.selector_id) if action is not None else None
                ),
                requested_target_ids=(
                    tuple(action.targets.explicit_ids) if action is not None else ()
                ),
                resolved_target_ids=tuple(transition.resolved_target_ids),
                action_parameters=(
                    dict(action.parameters) if action is not None else {}
                ),
                action_context_tags=(
                    action.context_tags.strings() if action is not None else ()
                ),
            )
        )
    return tuple(result)


def _capture_state_participants(state, participant_labels, attribute_resolver):
    return tuple(
        capture_battle_participant(
            entity,
            participant_labels.get(entity_id, (entity_id, "unknown"))[0],
            str(state.participants[entity_id].team_id),
            attribute_resolver,
        )
        for entity_id, entity in state.entities.items()
        if entity_id in state.participants
    )


def _capture_battle_frame(frame, participant_labels, attribute_resolver):
    state = frame.state
    return BattleReportFrameDraft(
        logical_time=frame.logical_time,
        round_number=state.round_number,
        turn_number=state.turn_number,
        status=state.status.value,
        revision=state.revision,
        current_actor_entity_id=state.current_actor_id,
        turn_order_entity_ids=tuple(state.turn_order),
        inactive_entity_ids=tuple(sorted(state.inactive_ids)),
        winning_team_ids=tuple(str(value) for value in state.winning_teams),
        action_progress={str(key): value for key, value in state.action_progress.items()},
        participants=_capture_state_participants(
            state,
            participant_labels,
            attribute_resolver,
        ),
    )


__all__ = [
    "capture_battle_participant",
    "capture_battle_round_states",
    "capture_battle_turn_states",
    "capture_battle_transitions",
]
