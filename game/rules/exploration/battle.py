"""把真实角色配装与区域敌人接入同一条自动战斗时间线。"""

from __future__ import annotations

from dataclasses import dataclass

from game.content.catalog.combat import BASIC_ATTACK_ABILITY_ID
from game.core.gameplay import (
    COMBAT_SPEED,
    HEALTH_CURRENT,
    HEALTH_MAXIMUM,
    SPIRIT_CURRENT,
    SPIRIT_MAXIMUM,
    BattleAiRule,
    BattleEngine,
    BattleParticipant,
    BattleRules,
    BattleSession,
    BattleStatus,
    BattleTrace,
    CharacterState,
    GameplayExecutor,
    InventoryState,
    LoadoutState,
    RuleContext,
    RuleEvent,
    TagSet,
)
from game.rules.combat import PlayerCombatProjector

from .models import ExplorationBatchPlan


@dataclass(frozen=True)
class ExplorationBattleOutcome:
    victory: bool
    draw: bool
    health_after: float
    spirit_after: float
    health_maximum: float
    spirit_maximum: float
    turns: int
    trace: BattleTrace


class ExplorationBattleSimulator:
    def __init__(self, content, player_combat: PlayerCombatProjector) -> None:
        self.content = content
        self.player_combat = player_combat
        self.engine = BattleEngine(
            GameplayExecutor(content.ability_engine, content.trigger_engine),
            BattleRules(HEALTH_CURRENT, COMBAT_SPEED),
            content.battle_ability_targeting,
            content.target_selectors,
        )

    def simulate(
        self,
        plan: ExplorationBatchPlan,
        *,
        character: CharacterState,
        inventory: InventoryState,
        loadout: LoadoutState,
        context: RuleContext,
    ) -> ExplorationBattleOutcome:
        if plan.encounter is None:
            raise ValueError("空探险批次不能进入战斗")
        player = self._player(character, inventory, loadout)
        enemy_projections = tuple(
            self.content.enemy_projector.project(instance)
            for instance in plan.encounter.enemies
        )
        entities = {character.id: player.entity}
        entities.update(
            {projection.instance.id: projection.entity for projection in enemy_projections}
        )
        participants = [BattleParticipant(character.id, "team.player", 0)]
        participants.extend(
            BattleParticipant(projection.instance.id, "team.enemy", index)
            for index, projection in enumerate(enemy_projections)
        )
        started = BattleSession.start(
            self.engine,
            f"battle:{plan.session_id}:{plan.batch_index}",
            participants=tuple(participants),
            entities=entities,
            context=context,
        )
        if started.failure or started.value is None:
            raise RuntimeError(started.failure.message if started.failure else "探险战斗启动失败")
        session = started.value
        rules = {character.id: self._player_ai(player.entity)}
        rules.update(
            {
                projection.instance.id: projection.ai_rules
                for projection in enemy_projections
            }
        )
        enemy_instances = {value.id: value for value in plan.encounter.enemies}
        active_phases: dict[str, frozenset[str]] = {
            enemy_id: frozenset() for enemy_id in enemy_instances
        }
        while session.state.status is BattleStatus.ACTIVE:
            state = session.state
            actor_id = state.current_actor_id
            if actor_id is None:
                raise RuntimeError("探险战斗没有当前行动者")
            action = self.content.battle_ai_engine.decide(
                rules[actor_id],
                state,
                actor_id,
                context=context,
            )
            if action is None:
                raise RuntimeError(f"探险自动战斗无法为 {actor_id} 选择行动")
            outcome = session.execute_turn(action, context=context)
            if outcome.failure or outcome.value is None:
                message = outcome.failure.message if outcome.failure else "探险战斗执行失败"
                raise RuntimeError(
                    f"{message}: actor={actor_id}, ability={action.ability_id}, "
                    f"selector={action.targets.selector_id}"
                )
            entity_updates, rules, active_phases, phase_events = self._enemy_phase_updates(
                session.state,
                rules,
                enemy_instances,
                active_phases,
                context,
            )
            if entity_updates or phase_events:
                phase_outcome = session.apply_external(
                    entity_updates,
                    phase_events,
                    subject_id="battle.transition.enemy_phase",
                    context=context,
                )
                if phase_outcome.failure:
                    raise RuntimeError(phase_outcome.failure.message)
        state = session.state
        player_after = state.entities[character.id]
        return ExplorationBattleOutcome(
            victory="team.player" in state.winning_teams,
            draw=state.status is BattleStatus.DRAW,
            health_after=float(player_after.resources[HEALTH_CURRENT]),
            spirit_after=float(player_after.resources[SPIRIT_CURRENT]),
            health_maximum=float(
                player_after.snapshot(self.content.enemy_projector.attributes).value(
                    HEALTH_MAXIMUM
                )
            ),
            spirit_maximum=float(
                player_after.snapshot(self.content.enemy_projector.attributes).value(
                    SPIRIT_MAXIMUM
                )
            ),
            turns=state.turn_number,
            trace=session.trace,
        )

    def _player(self, character, inventory, loadout):
        return self.player_combat.project(
            character,
            inventory,
            loadout,
            context_tags=TagSet.of("scene.exploration"),
        )

    def _player_ai(self, entity) -> tuple[BattleAiRule, ...]:
        rules = []
        for ability_id in sorted(entity.abilities):
            targeting = self.content.battle_ability_targeting.get(ability_id)
            if targeting is None:
                continue
            selectors = tuple(
                value
                for value in sorted(targeting.allowed_selectors)
                if value != "target.enemy.explicit"
            )
            if not selectors:
                continue
            selector = (
                "target.enemy.first"
                if "target.enemy.first" in selectors
                else selectors[0]
            )
            rules.append(
                BattleAiRule(
                    f"ai.exploration.player.{ability_id}",
                    ability_id,
                    selector,
                    priority=0 if ability_id == BASIC_ATTACK_ABILITY_ID else 10,
                    maximum_targets=targeting.maximum_targets,
                )
            )
        if not rules:
            raise ValueError("角色当前没有可用于探险的战斗能力")
        return tuple(rules)

    def _enemy_phase_updates(self, state, rules, enemy_instances, active_phases, context):
        if state.status is not BattleStatus.ACTIVE:
            return {}, rules, active_phases, ()
        updates = {}
        next_rules = dict(rules)
        next_active = dict(active_phases)
        changed = False
        phase_events = []
        for enemy_id, instance in enemy_instances.items():
            if enemy_id in state.inactive_ids:
                continue
            entity = state.entities[enemy_id]
            maximum = entity.snapshot(self.content.enemy_projector.attributes).value(
                HEALTH_MAXIMUM
            )
            ratio = entity.resources[HEALTH_CURRENT] / maximum if maximum > 0 else 0.0
            definition = self.content.enemies.require(instance.definition_id)
            pending = self.content.enemy_projector.pending_phases(
                definition,
                ratio,
                next_active[enemy_id],
            )
            for phase in pending:
                entity, phase_rules = self.content.enemy_projector.apply_phase(
                    entity,
                    instance,
                    phase,
                )
                next_rules[enemy_id] = (*next_rules[enemy_id], *phase_rules)
                next_active[enemy_id] = next_active[enemy_id] | {phase.id}
                changed = True
                phase_events.append(
                    RuleEvent.from_context(
                        context,
                        kind="combat.phase.activated",
                        source_id=enemy_id,
                        target_id=enemy_id,
                        subject_id=phase.id,
                        values={
                            "health_ratio": ratio,
                            "threshold": phase.health_ratio,
                            "behavior_count": len(phase.behavior_ids),
                        },
                    )
                )
            if pending:
                updates[enemy_id] = entity
        return updates if changed else {}, next_rules, next_active, tuple(phase_events)


__all__ = ["ExplorationBattleOutcome", "ExplorationBattleSimulator"]
