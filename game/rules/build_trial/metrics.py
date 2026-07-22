"""从战斗核心轨迹计算试炼摘要，不重新推演任何战斗公式。"""

from __future__ import annotations

from game.core.gameplay import (
    HEALTH_CURRENT,
    HEALTH_MAXIMUM,
    SPIRIT_CURRENT,
    SPIRIT_MAXIMUM,
    BattleTransitionKind,
)

from .models import BuildTrialMetrics


def summarize_build_trial(
    trace,
    *,
    character_id: str,
    player_entity_ids: tuple[str, ...],
    enemy_entity_ids: tuple[str, ...],
    attribute_resolver,
) -> BuildTrialMetrics:
    """只汇总核心已经确认的事件和最终状态。"""

    players = frozenset(player_entity_ids)
    enemies = frozenset(enemy_entity_ids)
    total_damage = 0.0
    damage_taken = 0.0
    healing = 0.0
    shield = 0.0
    critical_hits = 0
    trigger_activations = 0
    defeated_enemy_ids: set[str] = set()
    for event in trace.events:
        if event.kind == "combat.damage.dealt":
            amount = float(event.values.get("effective_damage", 0) or 0)
            if event.source_id in players and event.target_id in enemies:
                total_damage += amount
            if event.target_id in players:
                damage_taken += amount
        elif event.kind == "combat.healing.resolved" and event.target_id in players:
            healing += float(event.values.get("actual", 0) or 0)
        elif event.kind == "combat.shield.granted" and event.target_id in players:
            shield += float(event.values.get("actual", 0) or 0)
        elif event.kind == "combat.attack.critical" and event.source_id in players:
            critical_hits += 1
        elif event.kind == "trigger.activated":
            if str(event.values.get("owner_id", "")) in players:
                trigger_activations += 1
        elif event.kind == "combat.target.defeated" and event.target_id in enemies:
            defeated_enemy_ids.add(event.target_id)

    final = trace.final_frame.state
    character = final.entities[character_id]
    snapshot = character.snapshot(attribute_resolver)
    player_actions = sum(
        1
        for transition in trace.transitions
        if transition.kind is BattleTransitionKind.TURN
        and transition.action is not None
        and transition.action.actor_id in players
    )
    return BuildTrialMetrics(
        player_actions=player_actions,
        total_damage=total_damage,
        damage_taken=damage_taken,
        healing=healing,
        shield=shield,
        critical_hits=critical_hits,
        trigger_activations=trigger_activations,
        enemies_defeated=len(defeated_enemy_ids),
        health_after=float(character.resources[HEALTH_CURRENT]),
        health_maximum=float(snapshot.value(HEALTH_MAXIMUM)),
        spirit_after=float(character.resources[SPIRIT_CURRENT]),
        spirit_maximum=float(snapshot.value(SPIRIT_MAXIMUM)),
    )


__all__ = ["summarize_build_trial"]
