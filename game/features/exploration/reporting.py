"""把探险战斗轨迹交给统一战报装配器。"""

from __future__ import annotations

from game.rules.battle_report import (
    BattleReportDraft,
    BattleReportSummary,
)

from .models import exploration_battle_report_id


def build_exploration_battle_report(
    content,
    builder,
    state,
    next_state,
    character,
    character_world,
    inventory,
    loadout,
    inscription_preference,
    roster,
    battle,
    segment_id: str,
    view,
) -> BattleReportDraft:
    plan = next_state.last_result.plan
    assert plan.encounter is not None
    enemies = tuple(plan.encounter.enemies)
    combatants = [
        builder.character(
            character,
            character_world,
            inventory,
            loadout,
            team_id="player",
            team_label="行者一方",
            inscription_preference=inscription_preference,
        )
    ]
    if battle.player_companion_id is not None:
        companion = roster.instances[battle.player_companion_id]
        combatants.append(
            builder.companion(
                companion,
                team_id="player",
                team_label="行者一方",
            )
        )
    enemy_names = []
    for enemy in enemies:
        name = view.enemy_projector.enemy(enemy).name
        enemy_names.append(name)
        combatants.append(
            builder.enemy(
                enemy,
                character_world.world_id,
                name,
                team_id="enemy",
                team_label="遭遇一方",
            )
        )
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
            "victory" if battle.victory else "neutral" if battle.draw else "defeat",
        ),
        segment=builder.segment(
            segment_id=segment_id,
            title=f"第 {plan.batch_index} 批·{', '.join(enemy_names)}",
            trace=battle.trace,
            combatants=combatants,
            outcome=outcome,
            started_at=next_state.last_result.resolved_at,
            finished_at=next_state.last_result.resolved_at,
        ),
    )


__all__ = ["build_exploration_battle_report"]
