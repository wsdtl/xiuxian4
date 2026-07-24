"""把 BattleTrace 无损投影成战报动态状态。"""

from __future__ import annotations

from collections.abc import Callable

from .models import (
    BattleReportEffectDraft,
    BattleReportFrameDraft,
    BattleReportParticipantDraft,
    BattleReportTransitionDraft,
)


class BattleSnapshotProjector:
    """统一捕获完整轨迹；玩法组件不得再手工拼装状态帧。"""

    def __init__(
        self,
        attribute_resolver,
        effect_polarity: Callable[[str], str],
    ) -> None:
        self.attribute_resolver = attribute_resolver
        self.effect_polarity = effect_polarity

    def participant(self, entity) -> BattleReportParticipantDraft:
        snapshot = entity.snapshot(self.attribute_resolver)
        return BattleReportParticipantDraft(
            entity_id=entity.id,
            attributes={str(key): value for key, value in snapshot.values.items()},
            resources={str(key): value for key, value in entity.resources.items()},
            abilities=tuple(sorted(str(value) for value in entity.abilities)),
            effects=tuple(
                BattleReportEffectDraft(
                    instance_id=effect.instance_id,
                    definition_id=str(effect.definition_id),
                    source_id=effect.source_id,
                    stacks=effect.stacks,
                    remaining_turns=effect.remaining_turns,
                    polarity=self.effect_polarity(str(effect.definition_id)),
                )
                for effect in entity.active_effects
            ),
            cooldowns={str(key): value for key, value in entity.cooldowns.items()},
            triggers=tuple(sorted(str(value) for value in entity.triggers)),
            interceptors=tuple(
                sorted({str(value.interceptor_id) for value in entity.interceptor_bindings})
            ),
            target_constraints=tuple(
                sorted({str(value.constraint_id) for value in entity.target_constraint_bindings})
            ),
        )

    def frame(self, frame, entity_order: tuple[str, ...]) -> BattleReportFrameDraft:
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
            participants=tuple(
                self.participant(state.entities[entity_id])
                for entity_id in entity_order
                if entity_id in state.entities and entity_id in state.participants
            ),
        )

    def transitions(
        self,
        trace,
        entity_order: tuple[str, ...],
    ) -> tuple[BattleReportTransitionDraft, ...]:
        values = []
        for transition in trace.transitions:
            action = transition.action
            values.append(
                BattleReportTransitionDraft(
                    sequence=transition.sequence,
                    kind=transition.kind.value,
                    subject_id=str(transition.subject_id),
                    before=(
                        self.frame(transition.before, entity_order)
                        if transition.before is not None
                        else None
                    ),
                    after=self.frame(transition.after, entity_order),
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
                    action_parameters=dict(action.parameters) if action is not None else {},
                    action_context_tags=(
                        action.context_tags.strings() if action is not None else ()
                    ),
                )
            )
        return tuple(values)


__all__ = ["BattleSnapshotProjector"]
