"""把探险战斗轨迹投影为统一战报草稿。"""

from __future__ import annotations

from game.core.gameplay import CharacterState
from game.rules.battle_report import (
    BattleReportDraft,
    BattleReportSegmentDraft,
    BattleReportSummary,
    capture_battle_participant,
    capture_battle_round_states,
    capture_battle_transitions,
    capture_battle_turn_states,
)
from game.rules.companion import CompanionRosterState
from game.rules.exploration import ExplorationState

from .models import exploration_battle_report_id


def build_exploration_battle_report(
    content,
    state: ExplorationState,
    next_state: ExplorationState,
    character: CharacterState,
    roster: CompanionRosterState,
    battle,
    segment_id: str,
    view,
) -> BattleReportDraft:
    plan = next_state.last_result.plan
    assert plan.encounter is not None
    enemies = tuple(plan.encounter.enemies)
    labels = {character.id: (character.name, "player")}
    participants = [
        capture_battle_participant(
            battle.trace.initial_frame.state.entities[character.id],
            character.name,
            "player",
            content.catalog.enemy_projector.attributes,
        )
    ]
    if battle.player_companion_id is not None:
        companion = roster.instances[battle.player_companion_id]
        companion_name = content.companions.require_definition(
            companion.definition_id
        ).name
        participants.append(
            capture_battle_participant(
                battle.trace.initial_frame.state.entities[companion.id],
                companion_name,
                "companion",
                content.catalog.enemy_projector.attributes,
            )
        )
        labels[companion.id] = (companion_name, "companion")

    enemy_names = []
    for enemy in enemies:
        display = view.enemy_projector.enemy(enemy)
        participants.append(
            capture_battle_participant(
                battle.trace.initial_frame.state.entities[enemy.id],
                display.name,
                "enemy",
                content.catalog.enemy_projector.attributes,
            )
        )
        enemy_names.append(display.name)

    final_participants = [
        capture_battle_participant(
            battle.trace.final_frame.state.entities[character.id],
            character.name,
            "player",
            content.catalog.enemy_projector.attributes,
        )
    ]
    if battle.player_companion_id is not None:
        companion = roster.instances[battle.player_companion_id]
        companion_name = content.companions.require_definition(
            companion.definition_id
        ).name
        final_participants.append(
            capture_battle_participant(
                battle.trace.final_frame.state.entities[companion.id],
                companion_name,
                "companion",
                content.catalog.enemy_projector.attributes,
            )
        )
    final_participants.extend(
        capture_battle_participant(
            battle.trace.final_frame.state.entities[enemy.id],
            view.enemy_projector.enemy(enemy).name,
            "enemy",
            content.catalog.enemy_projector.attributes,
        )
        for enemy in enemies
    )

    enemy_labels = {
        enemy.id: (view.enemy_projector.enemy(enemy).name, "enemy")
        for enemy in enemies
    }
    trace_labels = {**labels, **enemy_labels}
    outcome = (
        "探险胜利"
        if battle.victory
        else "战斗平局"
        if battle.draw
        else "探险战败"
    )
    return BattleReportDraft(
        report_id=exploration_battle_report_id(state.session_id),
        mode_id="battle.mode.exploration",
        presentation_skin_id=str(view.skin.id),
        presentation_skin_version=view.skin.version,
        content_fingerprint=content.catalog.report.content_fingerprint,
        summary=BattleReportSummary(
            f"探险战报·{view.projector.name(state.location_id)}",
            f"{next_state.victories}胜 {next_state.defeats}负",
            (
                f"完成批次: {next_state.completed_batches}",
                f"累计经验: +{next_state.character_experience}",
                f"伙伴经验: +{next_state.companion_experience}",
                f"累计掉落: 武器 {next_state.weapon_drops}, 装备 {next_state.equipment_drops}",
            ),
        ),
        segment=BattleReportSegmentDraft(
            segment_id=segment_id,
            title=f"第 {plan.batch_index} 批·{', '.join(enemy_names)}",
            participants=tuple(participants),
            events=battle.trace.events,
            outcome=outcome,
            started_at=next_state.last_result.resolved_at,
            finished_at=next_state.last_result.resolved_at,
            final_participants=tuple(final_participants),
            round_states=capture_battle_round_states(
                battle.trace,
                trace_labels,
                content.catalog.enemy_projector.attributes,
            ),
            turn_states=capture_battle_turn_states(
                battle.trace,
                trace_labels,
                content.catalog.enemy_projector.attributes,
            ),
            transitions=capture_battle_transitions(
                battle.trace,
                trace_labels,
                content.catalog.enemy_projector.attributes,
            ),
        ),
    )


__all__ = ["build_exploration_battle_report"]
