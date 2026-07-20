"""当前角色阵容追猎一条固定伙伴踪迹的真实战斗。"""

from __future__ import annotations

from dataclasses import dataclass

from game.core.gameplay import (
    COMBAT_SPEED,
    HEALTH_CURRENT,
    SPIRIT_CURRENT,
    BattleEngine,
    BattleParticipant,
    BattleRules,
    BattleSession,
    BattleStatus,
    BattleTrace,
    GameplayExecutor,
    TagSet,
)
from game.rules.companion import CompanionRosterState, CompanionTrace


@dataclass(frozen=True)
class CompanionSanctuaryBattleOutcome:
    victory: bool
    draw: bool
    player_health_after: float
    player_spirit_after: float
    turns: int
    trace: BattleTrace
    player_companion_id: str | None
    target_id: str


class CompanionSanctuaryBattleSimulator:
    """只负责编排秘境追猎，伤害和特效全部走公共战斗核心。"""

    def __init__(self, content, lineup_projector, companion_projector) -> None:
        self.content = content
        self.lineup_projector = lineup_projector
        self.companion_projector = companion_projector
        self.engine = BattleEngine(
            GameplayExecutor(content.ability_engine, content.trigger_engine),
            BattleRules(
                HEALTH_CURRENT,
                COMBAT_SPEED,
                maximum_rounds=100,
                maximum_turns=400,
            ),
            content.battle_ability_targeting,
            content.target_selectors,
        )

    def simulate(
        self,
        sanctuary_session_id: str,
        target_trace: CompanionTrace,
        *,
        character,
        inventory,
        loadout,
        roster: CompanionRosterState,
        context,
    ) -> CompanionSanctuaryBattleOutcome:
        tags = TagSet.of("scene.companion_sanctuary")
        lineup = self.lineup_projector.project(
            character,
            inventory,
            loadout,
            roster,
            context_tags=tags,
        )
        target_id = f"wild:{sanctuary_session_id}:{target_trace.index}"
        target = self.companion_projector.project(
            target_trace,
            entity_id=target_id,
            context_tags=tags.merged(TagSet.of("entity.companion.wild")),
        )
        entities = lineup.entities
        entities[target_id] = target.entity
        participants = tuple(
            BattleParticipant(entity_id, "team.player", index)
            for index, entity_id in enumerate(lineup.participant_ids)
        ) + (BattleParticipant(target_id, "team.enemy", 0),)
        started = BattleSession.start(
            self.engine,
            f"battle:companion-sanctuary:{sanctuary_session_id}:{target_trace.index}",
            participants=participants,
            entities=entities,
            context=context,
        )
        if started.failure or started.value is None:
            raise RuntimeError(
                started.failure.message if started.failure else "伙伴秘境战斗启动失败"
            )
        session = started.value
        rules = self.lineup_projector.ai_rules(lineup)
        rules[target_id] = target.ai_rules
        while session.state.status is BattleStatus.ACTIVE:
            actor_id = session.state.current_actor_id
            if actor_id is None:
                raise RuntimeError("伙伴秘境战斗缺少当前行动者")
            action = self.content.battle_ai_engine.decide(
                rules[actor_id],
                session.state,
                actor_id,
                context=context,
            )
            if action is None:
                raise RuntimeError(f"伙伴秘境无法为 {actor_id} 选择行动")
            outcome = session.execute_turn(action, context=context)
            if outcome.failure or outcome.value is None:
                raise RuntimeError(
                    outcome.failure.message if outcome.failure else "伙伴秘境战斗执行失败"
                )
        state = session.state
        player = state.entities[character.id]
        return CompanionSanctuaryBattleOutcome(
            victory="team.player" in state.winning_teams,
            draw=state.status is BattleStatus.DRAW,
            player_health_after=float(player.resources[HEALTH_CURRENT]),
            player_spirit_after=float(player.resources[SPIRIT_CURRENT]),
            turns=state.turn_number,
            trace=session.trace,
            player_companion_id=(
                lineup.companion.companion_id
                if lineup.companion is not None
                else None
            ),
            target_id=target_id,
        )


__all__ = ["CompanionSanctuaryBattleOutcome", "CompanionSanctuaryBattleSimulator"]
