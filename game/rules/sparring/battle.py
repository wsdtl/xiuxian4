"""把两个真实角色的当前配装接入公共自动战斗核心。"""

from __future__ import annotations

from dataclasses import dataclass

from game.content.catalog.combat import BASIC_ATTACK_ABILITY_ID
from game.core.gameplay import (
    COMBAT_SPEED,
    HEALTH_CURRENT,
    SPIRIT_CURRENT,
    BattleAiRule,
    BattleEngine,
    BattleParticipant,
    BattleRules,
    BattleSession,
    BattleStatus,
    BattleTrace,
    GameplayExecutor,
    InventoryState,
    LoadoutState,
    RuleContext,
    TagSet,
)
from game.core.gameplay.character import CharacterState
from game.rules.combat import PlayerCombatProjector


@dataclass(frozen=True)
class SparringBattleOutcome:
    challenger_victory: bool
    draw: bool
    challenger_health_after: float
    challenger_spirit_after: float
    defender_health_after: float
    defender_spirit_after: float
    turns: int
    trace: BattleTrace


class SparringBattleSimulator:
    """切磋只读取双方快照，不修改角色血气、灵力、装备或背包。"""

    def __init__(self, content, player_combat: PlayerCombatProjector) -> None:
        self.content = content
        self.player_combat = player_combat
        self.engine = BattleEngine(
            GameplayExecutor(content.ability_engine, content.trigger_engine),
            BattleRules(
                HEALTH_CURRENT,
                COMBAT_SPEED,
                maximum_rounds=100,
                maximum_turns=1000,
            ),
            content.battle_ability_targeting,
            content.target_selectors,
        )

    def simulate(
        self,
        challenger: CharacterState,
        challenger_inventory: InventoryState,
        challenger_loadout: LoadoutState,
        defender: CharacterState,
        defender_inventory: InventoryState,
        defender_loadout: LoadoutState,
        *,
        battle_id: str,
        context: RuleContext,
    ) -> SparringBattleOutcome:
        challenger_projection = self.player_combat.project(
            challenger,
            challenger_inventory,
            challenger_loadout,
            context_tags=TagSet.of("scene.sparring", "side.challenger"),
        )
        defender_projection = self.player_combat.project(
            defender,
            defender_inventory,
            defender_loadout,
            context_tags=TagSet.of("scene.sparring", "side.defender"),
        )
        entities = {
            challenger.id: challenger_projection.entity,
            defender.id: defender_projection.entity,
        }
        started = BattleSession.start(
            self.engine,
            battle_id,
            participants=(
                BattleParticipant(challenger.id, "team.challenger", 0),
                BattleParticipant(defender.id, "team.defender", 0),
            ),
            entities=entities,
            context=context,
        )
        if started.failure or started.value is None:
            raise RuntimeError(started.failure.message if started.failure else "切磋战斗启动失败")
        session = started.value
        rules = {
            challenger.id: self._auto_rules(challenger_projection.entity, "challenger"),
            defender.id: self._auto_rules(defender_projection.entity, "defender"),
        }
        while session.state.status is BattleStatus.ACTIVE:
            actor_id = session.state.current_actor_id
            if actor_id is None:
                raise RuntimeError("切磋战斗缺少当前行动者")
            action = self.content.battle_ai_engine.decide(
                rules[actor_id],
                session.state,
                actor_id,
                context=context,
            )
            if action is None:
                raise RuntimeError(f"切磋自动战斗无法为 {actor_id} 选择行动")
            outcome = session.execute_turn(action, context=context)
            if outcome.failure or outcome.value is None:
                raise RuntimeError(
                    outcome.failure.message if outcome.failure else "切磋战斗执行失败"
                )
        state = session.state
        challenger_after = state.entities[challenger.id]
        defender_after = state.entities[defender.id]
        return SparringBattleOutcome(
            challenger_victory="team.challenger" in state.winning_teams,
            draw=state.status is BattleStatus.DRAW,
            challenger_health_after=float(challenger_after.resources[HEALTH_CURRENT]),
            challenger_spirit_after=float(challenger_after.resources[SPIRIT_CURRENT]),
            defender_health_after=float(defender_after.resources[HEALTH_CURRENT]),
            defender_spirit_after=float(defender_after.resources[SPIRIT_CURRENT]),
            turns=state.turn_number,
            trace=session.trace,
        )

    def _auto_rules(self, entity, side: str) -> tuple[BattleAiRule, ...]:
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
                    f"ai.sparring.{side}.{ability_id}",
                    ability_id,
                    selector,
                    priority=0 if ability_id == BASIC_ATTACK_ABILITY_ID else 10,
                    maximum_targets=targeting.maximum_targets,
                )
            )
        if not rules:
            raise ValueError("角色当前没有可用于切磋的战斗能力")
        return tuple(rules)


__all__ = ["SparringBattleOutcome", "SparringBattleSimulator"]
