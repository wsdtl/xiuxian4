"""战斗核心原生的状态帧、状态转移与完整执行轨迹。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Mapping

from ..context import RuleContext
from ..entity import RuleEntity
from ..errors import RuleOutcome
from ..events import RuleEvent
from ..ids import StableId, stable_id
from .timeline import (
    BattleAction,
    BattleParticipant,
    BattleState,
    BattleStepResult,
)

if TYPE_CHECKING:
    from .timeline import BattleEngine


BATTLE_TRACE_VERSION = "battle-trace.v1"


class BattleTransitionKind(str, Enum):
    START = "start"
    TURN = "turn"
    JOIN = "join"
    WITHDRAW = "withdraw"
    EXTERNAL = "external"


@dataclass(frozen=True)
class BattleFrame:
    """某个确定时刻的完整战斗状态。"""

    state: BattleState
    logical_time: datetime

    def __post_init__(self) -> None:
        if self.logical_time.tzinfo is None or self.logical_time.utcoffset() is None:
            raise ValueError("BattleFrame.logical_time 必须包含时区")


@dataclass(frozen=True)
class BattleTransition:
    """一次由核心确认的完整状态转移。"""

    sequence: int
    kind: BattleTransitionKind
    subject_id: StableId
    before: BattleFrame | None
    after: BattleFrame
    events: tuple[RuleEvent, ...]
    action: BattleAction | None = None
    resolved_target_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("BattleTransition.sequence 不能小于 0")
        object.__setattr__(self, "kind", BattleTransitionKind(self.kind))
        object.__setattr__(
            self,
            "subject_id",
            stable_id(self.subject_id, field="battle transition subject id"),
        )
        battle_id = self.after.state.battle_id
        if self.before is not None and self.before.state.battle_id != battle_id:
            raise ValueError("BattleTransition 前后状态不属于同一场战斗")
        if self.kind is BattleTransitionKind.START and self.before is not None:
            raise ValueError("战斗开始转移不能包含 before")
        if self.kind is not BattleTransitionKind.START and self.before is None:
            raise ValueError("非开始转移必须包含 before")
        if self.action is not None and self.before is not None:
            if self.action.actor_id != self.before.state.current_actor_id:
                raise ValueError("BattleTransition.action 不是转移前的当前行动者")
        unknown_targets = set(self.resolved_target_ids) - set(self.after.state.entities)
        if unknown_targets:
            raise ValueError("BattleTransition 包含未知的实际目标")


@dataclass(frozen=True)
class BattleTrace:
    """一场战斗从开始到当前状态的唯一结构化事实来源。"""

    battle_id: str
    transitions: tuple[BattleTransition, ...]
    version: str = BATTLE_TRACE_VERSION

    def __post_init__(self) -> None:
        if not self.battle_id.strip() or not self.transitions:
            raise ValueError("BattleTrace 缺少战斗身份或状态转移")
        if self.transitions[0].kind is not BattleTransitionKind.START:
            raise ValueError("BattleTrace 第一项必须是战斗开始转移")
        previous = None
        for sequence, transition in enumerate(self.transitions):
            if transition.sequence != sequence:
                raise ValueError("BattleTrace 状态转移序号不连续")
            if transition.after.state.battle_id != self.battle_id:
                raise ValueError("BattleTrace 包含其他战斗的状态")
            if previous is not None:
                if transition.before is None or transition.before.state != previous.after.state:
                    raise ValueError("BattleTrace 相邻状态转移不连续")
            previous = transition

    @property
    def initial_frame(self) -> BattleFrame:
        return self.transitions[0].after

    @property
    def final_frame(self) -> BattleFrame:
        return self.transitions[-1].after

    @property
    def events(self) -> tuple[RuleEvent, ...]:
        return tuple(event for transition in self.transitions for event in transition.events)

    @property
    def turn_transitions(self) -> tuple[BattleTransition, ...]:
        return tuple(
            transition
            for transition in self.transitions
            if transition.kind is BattleTransitionKind.TURN
        )

    @property
    def round_frames(self) -> tuple[BattleFrame, ...]:
        """返回每轮第一次行动前的完整状态。"""

        frames = {self.initial_frame.state.round_number: self.initial_frame}
        for transition in self.transitions:
            for event in transition.events:
                if event.kind != "combat.round.started":
                    continue
                round_number = int(event.values.get("round", 0) or 0)
                if round_number > 0:
                    frames[round_number] = transition.after
        seen_turn_rounds: set[int] = set()
        for transition in self.turn_transitions:
            assert transition.before is not None
            round_number = transition.before.state.round_number
            if round_number not in seen_turn_rounds:
                frames[round_number] = transition.before
                seen_turn_rounds.add(round_number)
        return tuple(frames[key] for key in sorted(frames))

    @property
    def turn_frames(self) -> tuple[BattleFrame, ...]:
        return tuple(
            transition.before
            for transition in self.turn_transitions
            if transition.before is not None
        )


class BattleSession:
    """唯一允许玩法连续推进战斗并自动累积轨迹的核心会话。"""

    def __init__(
        self,
        engine: BattleEngine,
        initial_step: BattleStepResult,
        context: RuleContext,
    ) -> None:
        self._engine = engine
        self._state = initial_step.state
        self._transitions = [
            BattleTransition(
                0,
                BattleTransitionKind.START,
                "battle.transition.start",
                None,
                BattleFrame(initial_step.state, context.logical_time),
                tuple(initial_step.events),
                resolved_target_ids=initial_step.resolved_target_ids,
            )
        ]

    @classmethod
    def start(
        cls,
        engine: BattleEngine,
        battle_id: str,
        *,
        participants: tuple[BattleParticipant, ...],
        entities: Mapping[str, RuleEntity],
        context: RuleContext,
    ) -> RuleOutcome[BattleSession]:
        outcome = engine.start(
            battle_id,
            participants=participants,
            entities=entities,
            context=context,
        )
        if outcome.failure:
            return RuleOutcome.failed(outcome.failure)
        assert outcome.value is not None
        return RuleOutcome.success(cls(engine, outcome.value, context))

    @property
    def state(self) -> BattleState:
        return self._state

    @property
    def trace(self) -> BattleTrace:
        return BattleTrace(self._state.battle_id, tuple(self._transitions))

    def execute_turn(
        self,
        action: BattleAction | None,
        *,
        context: RuleContext,
    ) -> RuleOutcome[BattleTransition]:
        return self._advance(
            self._engine.execute_turn(self._state, action, context=context),
            BattleTransitionKind.TURN,
            "battle.transition.turn",
            context,
            action=action,
        )

    def join(
        self,
        participant: BattleParticipant,
        entity: RuleEntity,
        *,
        context: RuleContext,
    ) -> RuleOutcome[BattleTransition]:
        return self._advance(
            self._engine.join(
                self._state,
                participant,
                entity,
                context=context,
            ),
            BattleTransitionKind.JOIN,
            "battle.transition.join",
            context,
        )

    def withdraw(
        self,
        entity_id: str,
        *,
        context: RuleContext,
        reason: str = "withdrawn",
    ) -> RuleOutcome[BattleTransition]:
        return self._advance(
            self._engine.withdraw(
                self._state,
                entity_id,
                context=context,
                reason=reason,
            ),
            BattleTransitionKind.WITHDRAW,
            "battle.transition.withdraw",
            context,
        )

    def apply_external(
        self,
        entity_updates: Mapping[str, RuleEntity],
        events: tuple[RuleEvent, ...],
        *,
        subject_id: StableId,
        context: RuleContext,
    ) -> RuleOutcome[BattleTransition]:
        return self._advance(
            self._engine.apply_external(
                self._state,
                entity_updates,
                events,
                context=context,
            ),
            BattleTransitionKind.EXTERNAL,
            subject_id,
            context,
        )

    def _advance(
        self,
        outcome: RuleOutcome[BattleStepResult],
        kind: BattleTransitionKind,
        subject_id: StableId,
        context: RuleContext,
        *,
        action: BattleAction | None = None,
    ) -> RuleOutcome[BattleTransition]:
        if outcome.failure:
            return RuleOutcome.failed(outcome.failure)
        assert outcome.value is not None
        before = BattleFrame(self._state, context.logical_time)
        transition = BattleTransition(
            len(self._transitions),
            kind,
            subject_id,
            before,
            BattleFrame(outcome.value.state, context.logical_time),
            tuple(outcome.value.events),
            action=action,
            resolved_target_ids=outcome.value.resolved_target_ids,
        )
        self._state = outcome.value.state
        self._transitions.append(transition)
        return RuleOutcome.success(transition)


__all__ = [
    "BATTLE_TRACE_VERSION",
    "BattleFrame",
    "BattleSession",
    "BattleTrace",
    "BattleTransition",
    "BattleTransitionKind",
]
