"""Project two current parties into one lossless automatic battle."""

from __future__ import annotations

from dataclasses import dataclass

from game.core.gameplay import (
    COMBAT_SPEED,
    HEALTH_CURRENT,
    BattleEngine,
    BattleParticipant,
    BattleRules,
    BattleSession,
    BattleStatus,
    BattleTrace,
    GameplayExecutor,
    RuleContext,
    TagSet,
)


@dataclass(frozen=True)
class PartySparringBattleOutcome:
    challenger_victory: bool
    draw: bool
    turns: int
    trace: BattleTrace
    challenger_lineups: dict[str, object]
    defender_lineups: dict[str, object]


class PartySparringBattleSimulator:
    """Read party lineups and run combat without persisting combat resources."""

    def __init__(self, content, player_lineup) -> None:
        self.content = content
        self.player_lineup = player_lineup
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
        challenger_members,
        challenger_bundles,
        defender_members,
        defender_bundles,
        *,
        battle_id: str,
        context: RuleContext,
    ) -> PartySparringBattleOutcome:
        entities = {}
        participants = []
        rules = {}
        challenger_lineups = self._project_side(
            challenger_members,
            challenger_bundles,
            "challenger",
            "team.challenger",
            entities,
            participants,
            rules,
        )
        defender_lineups = self._project_side(
            defender_members,
            defender_bundles,
            "defender",
            "team.defender",
            entities,
            participants,
            rules,
        )
        started = BattleSession.start(
            self.engine,
            battle_id,
            participants=tuple(participants),
            entities=entities,
            context=context,
        )
        if started.failure or started.value is None:
            raise RuntimeError(
                started.failure.message if started.failure else "组队切磋战斗启动失败"
            )
        session = started.value
        while session.state.status is BattleStatus.ACTIVE:
            actor_id = session.state.current_actor_id
            if actor_id is None:
                raise RuntimeError("组队切磋缺少当前行动者")
            action = self.content.battle_ai_engine.decide(
                rules[actor_id],
                session.state,
                actor_id,
                context=context,
            )
            if action is None:
                raise RuntimeError(f"组队切磋无法为 {actor_id} 选择行动")
            outcome = session.execute_turn(action, context=context)
            if outcome.failure or outcome.value is None:
                raise RuntimeError(
                    outcome.failure.message if outcome.failure else "组队切磋战斗执行失败"
                )
        return PartySparringBattleOutcome(
            challenger_victory="team.challenger" in session.state.winning_teams,
            draw=session.state.status is BattleStatus.DRAW,
            turns=session.state.turn_number,
            trace=session.trace,
            challenger_lineups=challenger_lineups,
            defender_lineups=defender_lineups,
        )

    def _project_side(
        self,
        members,
        bundles,
        side: str,
        team_id: str,
        entities,
        participants,
        rules,
    ):
        lineups = {}
        for member, (character, inventory, loadout, roster) in zip(members, bundles):
            lineup = self.player_lineup.project(
                character,
                inventory,
                loadout,
                roster,
                context_tags=TagSet.of("scene.party_sparring", f"side.{side}"),
            )
            lineups[character.id] = lineup
            entities.update(lineup.entities)
            rules.update(self.player_lineup.ai_rules(lineup))
            for offset, entity_id in enumerate(lineup.participant_ids):
                participants.append(
                    BattleParticipant(entity_id, team_id, member.slot * 2 + offset)
                )
        return lineups


__all__ = ["PartySparringBattleOutcome", "PartySparringBattleSimulator"]
