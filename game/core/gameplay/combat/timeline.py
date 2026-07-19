"""多实体战斗的回合、目标、状态和胜负编排。"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from math import floor, isfinite
from types import MappingProxyType
from typing import Mapping

from ..abilities import AbilityUse
from ..context import RuleContext
from ..entity import RuleEntity
from ..errors import RuleOutcome, RuleViolation
from ..events import RuleEvent
from ..ids import StableId, stable_id
from ..phases import ExecutionPhase
from ..runtime import GameplayExecutor
from ..tags import EMPTY_TAGS, TagSet
from .targeting import TargetRequest, TargetSelectorRegistry, TargetingContext


class BattleStatus(str, Enum):
    ACTIVE = "active"
    FINISHED = "finished"
    DRAW = "draw"


@dataclass(frozen=True)
class BattleParticipant:
    """实体在一场战斗中的阵营和站位。"""

    entity_id: str
    team_id: StableId
    slot: int

    def __post_init__(self) -> None:
        if not self.entity_id.strip():
            raise ValueError("BattleParticipant 缺少 entity_id")
        object.__setattr__(self, "team_id", stable_id(self.team_id, field="team id"))
        if self.slot < 0:
            raise ValueError("BattleParticipant.slot 不能小于 0")


@dataclass(frozen=True)
class BattleRules:
    """战斗编排边界；具体玩法可以创建不同 Ruleset。"""

    health_resource: StableId
    speed_attribute: StableId | None = None
    incapacitating_tags: TagSet = field(
        default_factory=lambda: TagSet.of(
            "state.control.stunned",
            "state.control.frozen",
            "state.control.sleep",
        )
    )
    maximum_rounds: int = 100
    maximum_turns: int = 1000
    maximum_extra_turns_per_action: int = 8
    baseline_speed: float = 100.0
    minimum_effective_speed: float = 25.0
    maximum_action_efficiency: float = 2.0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "health_resource",
            stable_id(self.health_resource, field="health resource id"),
        )
        if self.speed_attribute:
            object.__setattr__(
                self,
                "speed_attribute",
                stable_id(self.speed_attribute, field="speed attribute id"),
            )
        if self.maximum_rounds < 1:
            raise ValueError("BattleRules.maximum_rounds 必须大于 0")
        if self.maximum_turns < 1:
            raise ValueError("BattleRules.maximum_turns 必须大于 0")
        if self.maximum_extra_turns_per_action < 0:
            raise ValueError("maximum_extra_turns_per_action 不能小于 0")
        if not isfinite(self.baseline_speed) or self.baseline_speed <= 0:
            raise ValueError("baseline_speed 必须大于 0")
        if not isfinite(self.minimum_effective_speed) or self.minimum_effective_speed <= 0:
            raise ValueError("minimum_effective_speed 必须大于 0")
        if self.minimum_effective_speed > self.baseline_speed:
            raise ValueError("minimum_effective_speed 不能大于 baseline_speed")
        if not isfinite(self.maximum_action_efficiency) or self.maximum_action_efficiency <= 1:
            raise ValueError("maximum_action_efficiency 必须大于 1")

    def action_efficiency(self, speed: float) -> float:
        """把面板速度映射为每个标准时间轮获得的行动进度。"""

        if not self.speed_attribute:
            return 1.0
        value = float(speed)
        if not isfinite(value):
            raise ValueError("面板速度必须是有限值")
        effective_speed = max(self.minimum_effective_speed, value)
        limit = self.maximum_action_efficiency
        return limit * effective_speed / (
            effective_speed + (limit - 1.0) * self.baseline_speed
        )


@dataclass(frozen=True)
class BattleAction:
    """当前行动者提交的一次能力与目标请求。"""

    action_id: str
    actor_id: str
    ability_id: StableId
    targets: TargetRequest
    parameters: Mapping[str, float] = field(default_factory=dict)
    context_tags: TagSet = EMPTY_TAGS
    decision_rule_id: StableId | None = None

    def __post_init__(self) -> None:
        if not self.action_id.strip():
            raise ValueError("BattleAction 缺少 action_id")
        if not self.actor_id.strip():
            raise ValueError("BattleAction 缺少 actor_id")
        object.__setattr__(self, "ability_id", stable_id(self.ability_id, field="ability id"))
        object.__setattr__(
            self,
            "parameters",
            MappingProxyType({str(key): float(value) for key, value in self.parameters.items()}),
        )
        if self.decision_rule_id is not None:
            object.__setattr__(
                self,
                "decision_rule_id",
                stable_id(self.decision_rule_id, field="battle decision rule id"),
            )


@dataclass(frozen=True)
class BattleAbilityTargeting:
    """一个战斗 Ability 允许使用的目标模式和目标数量上限。"""

    ability_id: StableId
    allowed_selectors: frozenset[StableId]
    maximum_targets: int | None = None
    bypass_target_constraints: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "ability_id", stable_id(self.ability_id, field="ability id"))
        selectors = frozenset(
            stable_id(value, field="selector id") for value in self.allowed_selectors
        )
        if not selectors:
            raise ValueError("BattleAbilityTargeting.allowed_selectors 不能为空")
        object.__setattr__(self, "allowed_selectors", selectors)
        if self.maximum_targets is not None and self.maximum_targets < 1:
            raise ValueError("BattleAbilityTargeting.maximum_targets 必须大于 0")


@dataclass(frozen=True)
class BattleState:
    """可持久化、可重放的一场战斗状态。"""

    battle_id: str
    participants: Mapping[str, BattleParticipant]
    entities: Mapping[str, RuleEntity]
    round_number: int
    turn_number: int
    turn_order: tuple[str, ...]
    turn_index: int
    action_progress: Mapping[str, float] = field(default_factory=dict)
    inactive_ids: frozenset[str] = frozenset()
    status: BattleStatus = BattleStatus.ACTIVE
    winning_teams: tuple[StableId, ...] = ()
    revision: int = 0

    def __post_init__(self) -> None:
        if not self.battle_id.strip():
            raise ValueError("BattleState 缺少 battle_id")
        object.__setattr__(self, "participants", MappingProxyType(dict(self.participants)))
        object.__setattr__(self, "entities", MappingProxyType(dict(self.entities)))
        progress = {str(key): float(value) for key, value in self.action_progress.items()}
        if set(progress) - set(self.entities):
            raise ValueError("BattleState.action_progress 包含未知实体")
        if any(not isfinite(value) or not 0 <= value < 1 for value in progress.values()):
            raise ValueError("BattleState.action_progress 必须位于 0 到 1 之间")
        object.__setattr__(self, "action_progress", MappingProxyType(progress))
        unknown_inactive = set(self.inactive_ids) - set(self.entities)
        if unknown_inactive:
            raise ValueError("BattleState.inactive_ids 包含未知实体")
        if set(self.participants) != set(self.entities):
            raise ValueError("BattleState.participants 与 entities 必须包含相同实体")
        if self.round_number < 1 or self.turn_number < 0:
            raise ValueError("BattleState 回合编号无效")
        if self.status is BattleStatus.ACTIVE:
            if not self.turn_order or not 0 <= self.turn_index < len(self.turn_order):
                raise ValueError("进行中的 BattleState 缺少当前行动者")

    @property
    def current_actor_id(self) -> str | None:
        if self.status is not BattleStatus.ACTIVE:
            return None
        return self.turn_order[self.turn_index]

    def entity(self, entity_id: str) -> RuleEntity:
        return self.entities[entity_id]


@dataclass(frozen=True)
class BattleStepResult:
    state: BattleState
    events: tuple[RuleEvent, ...]
    resolved_target_ids: tuple[str, ...] = ()


class BattleEngine:
    """编排回合和多目标 Ability，不复制 Effect 或伤害公式。"""

    def __init__(
        self,
        executor: GameplayExecutor,
        rules: BattleRules,
        ability_targeting: Mapping[StableId, BattleAbilityTargeting],
        selectors: TargetSelectorRegistry | None = None,
    ) -> None:
        self.executor = executor
        self.rules = rules
        self.selectors = selectors or TargetSelectorRegistry.with_defaults()
        self.ability_targeting = MappingProxyType(dict(ability_targeting))
        self.effects = executor.abilities.effects
        try:
            self.health = self.effects.resources[rules.health_resource]
        except KeyError as exc:
            raise KeyError(f"战斗编排缺少血气资源：{rules.health_resource}") from exc
        if rules.speed_attribute and rules.speed_attribute not in self.effects.attributes.definitions:
            raise KeyError(f"战斗编排缺少速度属性：{rules.speed_attribute}")
        known_abilities = set(executor.abilities.definitions.ids())
        known_selectors = set(self.selectors.ids())
        for key, targeting in self.ability_targeting.items():
            if key != targeting.ability_id:
                raise ValueError(f"战斗目标规则映射键与 ability_id 不一致：{key}")
            if key not in known_abilities:
                raise KeyError(f"战斗目标规则引用未知 Ability：{key}")
            unknown_selectors = set(targeting.allowed_selectors) - known_selectors
            if unknown_selectors:
                raise KeyError(
                    f"Ability {key} 引用未知目标选择器："
                    f"{', '.join(sorted(unknown_selectors))}"
                )
        self.selectors.freeze()

    def start(
        self,
        battle_id: str,
        *,
        participants: tuple[BattleParticipant, ...],
        entities: Mapping[str, RuleEntity],
        context: RuleContext,
    ) -> RuleOutcome[BattleStepResult]:
        checkpoint = context.random.checkpoint()
        try:
            return RuleOutcome.success(
                self._start(
                    battle_id,
                    participants=participants,
                    entities=entities,
                    context=context,
                )
            )
        except RuleViolation as exc:
            context.random.restore(checkpoint)
            return RuleOutcome.failed(exc.failure)

    def execute_turn(
        self,
        state: BattleState,
        action: BattleAction | None,
        *,
        context: RuleContext,
    ) -> RuleOutcome[BattleStepResult]:
        checkpoint = context.random.checkpoint()
        try:
            return RuleOutcome.success(self._execute_turn(state, action, context=context))
        except RuleViolation as exc:
            context.random.restore(checkpoint)
            return RuleOutcome.failed(exc.failure)

    def join(
        self,
        state: BattleState,
        participant: BattleParticipant,
        entity: RuleEntity,
        *,
        context: RuleContext,
    ) -> RuleOutcome[BattleStepResult]:
        checkpoint = context.random.checkpoint()
        try:
            return RuleOutcome.success(
                self._join(state, participant, entity, context=context)
            )
        except RuleViolation as exc:
            context.random.restore(checkpoint)
            return RuleOutcome.failed(exc.failure)

    def withdraw(
        self,
        state: BattleState,
        entity_id: str,
        *,
        context: RuleContext,
        reason: str = "withdrawn",
    ) -> RuleOutcome[BattleStepResult]:
        checkpoint = context.random.checkpoint()
        try:
            return RuleOutcome.success(
                self._withdraw(state, entity_id, context=context, reason=reason)
            )
        except RuleViolation as exc:
            context.random.restore(checkpoint)
            return RuleOutcome.failed(exc.failure)

    def apply_external(
        self,
        state: BattleState,
        entity_updates: Mapping[str, RuleEntity],
        events: tuple[RuleEvent, ...],
        *,
        context: RuleContext,
    ) -> RuleOutcome[BattleStepResult]:
        """通过核心受控入口应用阶段等外部实体变化。"""

        checkpoint = context.random.checkpoint()
        try:
            return RuleOutcome.success(
                self._apply_external(
                    state,
                    entity_updates,
                    events,
                    context=context,
                )
            )
        except RuleViolation as exc:
            context.random.restore(checkpoint)
            return RuleOutcome.failed(exc.failure)

    def _apply_external(
        self,
        state: BattleState,
        entity_updates: Mapping[str, RuleEntity],
        events: tuple[RuleEvent, ...],
        *,
        context: RuleContext,
    ) -> BattleStepResult:
        if state.status is not BattleStatus.ACTIVE:
            raise RuleViolation("battle.not_active", "已经结束的战斗不能应用外部变化")
        unknown = set(entity_updates) - set(state.entities)
        if unknown:
            raise RuleViolation(
                "battle.external_entity_unknown",
                "外部变化包含不在战斗中的实体",
                {"entity_ids": tuple(sorted(unknown))},
            )
        for entity_id, entity in entity_updates.items():
            if entity.id != entity_id:
                raise ValueError("外部变化的实体键与 RuleEntity.id 不一致")
        entities = dict(state.entities)
        entities.update(entity_updates)
        entities, processed_events = self._process_external_events(
            tuple(events),
            entities,
            context,
            state.inactive_ids,
        )
        next_state = replace(
            state,
            entities=entities,
            revision=state.revision + 1,
        )
        alive_teams = self._alive_teams(
            next_state.participants,
            next_state.entities,
            next_state.inactive_ids,
        )
        if len(alive_teams) > 1:
            return BattleStepResult(next_state, processed_events)
        status = BattleStatus.FINISHED if alive_teams else BattleStatus.DRAW
        next_state = replace(
            next_state,
            status=status,
            winning_teams=tuple(sorted(alive_teams)),
        )
        finished = self._finished_event(next_state, context, "external_transition")
        final_entities, final_events = self._process_external_events(
            (finished,),
            next_state.entities,
            context,
            next_state.inactive_ids,
        )
        next_state = replace(next_state, entities=final_entities)
        return BattleStepResult(next_state, (*processed_events, *final_events))

    def _join(
        self,
        state: BattleState,
        participant: BattleParticipant,
        entity: RuleEntity,
        *,
        context: RuleContext,
    ) -> BattleStepResult:
        if state.status is not BattleStatus.ACTIVE:
            raise RuleViolation("battle.not_active", "已经结束的战斗不能加入实体")
        if participant.entity_id != entity.id:
            raise ValueError("加入战斗的 participant.entity_id 与 entity.id 不一致")
        if entity.id in state.entities:
            raise RuleViolation(
                "battle.participant_exists",
                f"实体 {entity.id} 已经在战斗中",
                {"entity_id": entity.id},
            )
        if any(
            value.team_id == participant.team_id
            and value.slot == participant.slot
            and value.entity_id not in state.inactive_ids
            for value in state.participants.values()
        ):
            raise RuleViolation(
                "battle.slot_occupied",
                "加入战斗的阵营站位已经被占用",
                {"team_id": participant.team_id, "slot": participant.slot},
            )
        participants = dict(state.participants)
        entities = dict(state.entities)
        action_progress = dict(state.action_progress)
        participants[entity.id] = participant
        entities[entity.id] = entity
        action_progress[entity.id] = 0.0
        event = RuleEvent.from_context(
            context,
            kind="combat.participant.joined",
            source_id=entity.id,
            target_id=entity.id,
            subject_id="combat.participant",
            values={
                "battle_id": state.battle_id,
                "team_id": participant.team_id,
                "slot": participant.slot,
            },
            phase=ExecutionPhase.AFTER_APPLY,
        )
        entities, events = self._process_external_events(
            (event,),
            entities,
            context,
            state.inactive_ids,
        )
        # 中途加入者从下一轮开始行动，避免插入当前行动造成顺序歧义。
        joined = replace(
            state,
            participants=participants,
            entities=entities,
            action_progress=action_progress,
            revision=state.revision + 1,
        )
        return BattleStepResult(joined, events)

    def _withdraw(
        self,
        state: BattleState,
        entity_id: str,
        *,
        context: RuleContext,
        reason: str,
    ) -> BattleStepResult:
        if state.status is not BattleStatus.ACTIVE:
            raise RuleViolation("battle.not_active", "已经结束的战斗不能退出实体")
        if entity_id not in state.entities or entity_id in state.inactive_ids:
            raise RuleViolation(
                "battle.participant_missing",
                f"实体 {entity_id} 不在战斗中",
                {"entity_id": entity_id},
            )
        participant = state.participants[entity_id]
        event = RuleEvent.from_context(
            context,
            kind="combat.participant.left",
            source_id=entity_id,
            target_id=entity_id,
            subject_id="combat.participant",
            values={
                "battle_id": state.battle_id,
                "team_id": participant.team_id,
                "slot": participant.slot,
                "reason": reason,
            },
            phase=ExecutionPhase.AFTER_APPLY,
        )
        processed_entities, events = self._process_external_events(
            (event,),
            state.entities,
            context,
            state.inactive_ids,
        )
        participants = dict(state.participants)
        entities = dict(processed_entities)
        inactive_ids = state.inactive_ids | {entity_id}
        action_progress = dict(state.action_progress)
        action_progress.pop(entity_id, None)
        order = list(state.turn_order)
        removed_indices = [index for index, value in enumerate(order) if value == entity_id]
        order = [value for value in order if value != entity_id]
        turn_index = state.turn_index
        round_number = state.round_number
        if removed_indices:
            turn_index -= sum(index < state.turn_index for index in removed_indices)
        if turn_index >= len(order):
            order = []
            turn_index = 0
        alive_teams = self._alive_teams(participants, entities, inactive_ids)
        status = BattleStatus.ACTIVE
        winners: tuple[StableId, ...] = ()
        extra_events: list[RuleEvent] = []
        finish_reason = reason
        if len(alive_teams) <= 1:
            status = BattleStatus.FINISHED if alive_teams else BattleStatus.DRAW
            winners = tuple(sorted(alive_teams))
        elif not order:
            scheduled_round, scheduled_order, action_progress = self._next_action_window(
                participants,
                entities,
                inactive_ids,
                action_progress,
                round_number,
            )
            if scheduled_round is None:
                status = BattleStatus.DRAW
                finish_reason = "maximum_rounds"
            else:
                round_number = scheduled_round
                order = list(scheduled_order)
                turn_index = 0
        withdrawn = replace(
            state,
            participants=participants,
            entities=entities,
            inactive_ids=inactive_ids,
            turn_order=tuple(order),
            turn_index=turn_index,
            round_number=round_number,
            action_progress=action_progress,
            status=status,
            winning_teams=winners,
            revision=state.revision + 1,
        )
        if status is not BattleStatus.ACTIVE:
            extra_events.append(self._finished_event(withdrawn, context, finish_reason))
        return BattleStepResult(withdrawn, (*events, *extra_events))

    def _start(
        self,
        battle_id: str,
        *,
        participants: tuple[BattleParticipant, ...],
        entities: Mapping[str, RuleEntity],
        context: RuleContext,
    ) -> BattleStepResult:
        if not battle_id.strip():
            raise ValueError("battle_id 不能为空")
        participant_map = {participant.entity_id: participant for participant in participants}
        if len(participant_map) != len(participants):
            raise ValueError("战斗参与者 entity_id 不能重复")
        if set(participant_map) != set(entities):
            raise ValueError("战斗参与者与实体集合不一致")
        occupied = {(value.team_id, value.slot) for value in participants}
        if len(occupied) != len(participants):
            raise ValueError("同一阵营不能有重复站位")
        if len({value.team_id for value in participants}) < 2:
            raise ValueError("战斗至少需要两个阵营")
        alive_teams = self._alive_teams(participant_map, entities)
        if len(alive_teams) < 2:
            raise ValueError("战斗开始时至少需要两个仍存活的阵营")

        event = RuleEvent.from_context(
            context,
            kind="combat.battle.started",
            source_id=battle_id,
            target_id=battle_id,
            subject_id="combat.battle",
            values={
                "battle_id": battle_id,
                "entity_ids": tuple(sorted(entities)),
                "team_ids": tuple(sorted(alive_teams)),
            },
            phase=ExecutionPhase.PREPARE,
        )
        states, events = self._process_external_events((event,), entities, context)
        alive_after_start = self._alive_teams(participant_map, states)
        order = self._turn_order(participant_map, states)
        action_progress = {entity_id: 0.0 for entity_id in states}
        if len(alive_after_start) <= 1:
            status = BattleStatus.FINISHED if alive_after_start else BattleStatus.DRAW
            state = BattleState(
                battle_id=battle_id,
                participants=participant_map,
                entities=states,
                round_number=1,
                turn_number=0,
                turn_order=order,
                turn_index=0,
                action_progress=action_progress,
                status=status,
                winning_teams=tuple(sorted(alive_after_start)),
            )
            return BattleStepResult(
                state,
                (*events, self._finished_event(state, context, "battle_start_effect")),
            )
        round_event = RuleEvent.from_context(
            context,
            kind="combat.round.started",
            source_id=battle_id,
            target_id=order[0],
            subject_id="combat.round",
            values={"battle_id": battle_id, "round": 1, "turn_order": order},
            phase=ExecutionPhase.PREPARE,
        )
        states, round_events = self._process_external_events((round_event,), states, context)
        order = self._turn_order(participant_map, states)
        alive_teams = self._alive_teams(participant_map, states)
        status = BattleStatus.ACTIVE
        winners: tuple[StableId, ...] = ()
        if len(alive_teams) <= 1:
            status = BattleStatus.FINISHED if alive_teams else BattleStatus.DRAW
            winners = tuple(sorted(alive_teams))
        state = BattleState(
            battle_id=battle_id,
            participants=participant_map,
            entities=states,
            round_number=1,
            turn_number=0,
            turn_order=order,
            turn_index=0,
            action_progress=action_progress,
            status=status,
            winning_teams=winners,
        )
        all_events = [*events, *round_events]
        if status is not BattleStatus.ACTIVE:
            all_events.append(self._finished_event(state, context, "battle_start_effect"))
        return BattleStepResult(state, tuple(all_events))

    def _execute_turn(
        self,
        state: BattleState,
        action: BattleAction | None,
        *,
        context: RuleContext,
    ) -> BattleStepResult:
        if state.status is not BattleStatus.ACTIVE:
            raise RuleViolation(
                "battle.not_active",
                f"战斗 {state.battle_id} 已经结束",
                {"battle_id": state.battle_id, "status": state.status.value},
            )
        actor_id = state.current_actor_id
        assert actor_id is not None
        if action is not None and action.actor_id != actor_id:
            raise RuleViolation(
                "battle.not_current_actor",
                f"当前行动者是 {actor_id}，不是 {action.actor_id}",
                {"current_actor_id": actor_id, "actor_id": action.actor_id},
            )

        trigger_session = (
            self.executor.triggers.session(context, state.inactive_ids)
            if self.executor.triggers
            else None
        )
        entities = dict(state.entities)
        events: list[RuleEvent] = []
        target_ids: tuple[str, ...] = ()

        def process(batch, current_entities):
            if trigger_session is None:
                return dict(current_entities), batch
            result = trigger_session.process(batch, current_entities)
            return dict(result.entities), result.events

        started = RuleEvent.from_context(
            context,
            kind="combat.turn.started",
            source_id=actor_id,
            target_id=actor_id,
            subject_id="combat.turn",
            values={
                "battle_id": state.battle_id,
                "round": state.round_number,
                "turn": state.turn_number + 1,
            },
            phase=ExecutionPhase.PREPARE,
        )
        entities, generated = process((started,), entities)
        events.extend(generated)
        actor = entities[actor_id]

        skip_reason = None
        if not self._alive(actor):
            skip_reason = "defeated"
        elif not actor.tags.allows(blocked=self.rules.incapacitating_tags):
            skip_reason = "incapacitated"
        elif action is None:
            skip_reason = "passed"

        if skip_reason:
            skipped = RuleEvent.from_context(
                context,
                kind="combat.turn.skipped",
                source_id=actor_id,
                target_id=actor_id,
                subject_id="combat.turn",
                values={"battle_id": state.battle_id, "reason": skip_reason},
                phase=ExecutionPhase.RESOLVE,
            )
            entities, generated = process((skipped,), entities)
            events.extend(generated)
        else:
            assert action is not None
            target_rule = self._ability_target_rule(action)
            requested_maximum = action.targets.maximum_targets
            if target_rule.maximum_targets is not None:
                requested_maximum = (
                    target_rule.maximum_targets
                    if requested_maximum is None
                    else min(requested_maximum, target_rule.maximum_targets)
                )
            target_request = replace(action.targets, maximum_targets=requested_maximum)
            target_ids = self.selectors.select(
                target_request,
                self._targeting_context(
                    actor_id,
                    state.participants,
                    entities,
                    context,
                    state.inactive_ids,
                ),
                bypass_constraints=target_rule.bypass_target_constraints,
            )
            ability_result = self.executor.abilities.execute_many(
                AbilityUse(
                    action.action_id,
                    action.ability_id,
                    action.parameters,
                    action.context_tags,
                ),
                actor_id=actor_id,
                target_ids=target_ids,
                entities=entities,
                context=context,
                event_processor=process,
            )
            entities = dict(ability_result.entities)
            events.extend(ability_result.events)

        ended = RuleEvent.from_context(
            context,
            kind="combat.turn.ended",
            source_id=actor_id,
            target_id=actor_id,
            subject_id="combat.turn",
            values={
                "battle_id": state.battle_id,
                "round": state.round_number,
                "turn": state.turn_number + 1,
                "skipped": skip_reason is not None,
            },
            phase=ExecutionPhase.TURN_END,
        )
        entities, generated = process((ended,), entities)
        events.extend(generated)

        advanced = self.effects.advance_turn(
            entities[actor_id],
            context.at_phase(ExecutionPhase.TURN_END),
        )
        entities[actor_id] = advanced.target
        entities, generated = process(advanced.events, entities)
        events.extend(generated)

        directed_state = self._apply_timeline_directives(state, events, entities)
        next_state, transition_events = self._advance_state(
            directed_state,
            entities,
            context,
        )
        transitioned_entities, generated = process(transition_events, next_state.entities)
        next_state = replace(next_state, entities=transitioned_entities)
        events.extend(generated)
        if (
            next_state.status is BattleStatus.ACTIVE
            and any(event.kind == "combat.round.started" for event in transition_events)
        ):
            alive_teams = self._alive_teams(
                next_state.participants,
                next_state.entities,
                next_state.inactive_ids,
            )
            if len(alive_teams) <= 1:
                status = BattleStatus.FINISHED if alive_teams else BattleStatus.DRAW
                next_state = replace(
                    next_state,
                    status=status,
                    winning_teams=tuple(sorted(alive_teams)),
                )
                finished = self._finished_event(next_state, context, "round_start_effect")
                transitioned_entities, generated = process((finished,), next_state.entities)
                next_state = replace(next_state, entities=transitioned_entities)
                events.extend(generated)
            else:
                remaining_order = tuple(
                    entity_id
                    for entity_id in next_state.turn_order
                    if entity_id not in next_state.inactive_ids
                    and self._alive(next_state.entities[entity_id])
                )
                if remaining_order:
                    next_state = replace(
                        next_state,
                        turn_order=remaining_order,
                        turn_index=0,
                    )
        return BattleStepResult(next_state, tuple(events), target_ids)

    def _apply_timeline_directives(
        self,
        state: BattleState,
        events: list[RuleEvent],
        entities: Mapping[str, RuleEntity],
    ) -> BattleState:
        order = list(state.turn_order)
        extra_events = [
            event
            for event in events
            if event.kind == "combat.timeline.extra_turn_requested"
        ]
        if len(extra_events) > self.rules.maximum_extra_turns_per_action:
            raise RuleViolation(
                "battle.extra_turn_limit",
                "一次行动请求的额外行动次数超过战斗规则上限",
                {
                    "requested": len(extra_events),
                    "maximum": self.rules.maximum_extra_turns_per_action,
                },
            )
        insert_index = state.turn_index + 1
        for event in extra_events:
            entity_id = event.target_id
            if entity_id in entities and self._alive(entities[entity_id]):
                order.insert(insert_index, entity_id)
                insert_index += 1

        for event in events:
            if event.kind != "combat.timeline.delay_requested":
                continue
            entity_id = event.target_id
            positions = max(1, int(event.values.get("positions", 1)))
            candidates = [
                index
                for index in range(state.turn_index + 1, len(order))
                if order[index] == entity_id
            ]
            if not candidates:
                continue
            current_index = candidates[0]
            value = order.pop(current_index)
            order.insert(min(len(order), current_index + positions), value)
        return replace(state, turn_order=tuple(order))

    def _ability_target_rule(self, action: BattleAction) -> BattleAbilityTargeting:
        try:
            rule = self.ability_targeting[action.ability_id]
        except KeyError as exc:
            raise RuleViolation(
                "battle.ability_targeting_missing",
                f"Ability {action.ability_id} 未登记战斗目标规则",
                {"ability_id": action.ability_id},
            ) from exc
        if action.targets.selector_id not in rule.allowed_selectors:
            raise RuleViolation(
                "battle.target_selector_forbidden",
                f"Ability {action.ability_id} 不允许目标模式 {action.targets.selector_id}",
                {
                    "ability_id": action.ability_id,
                    "selector_id": action.targets.selector_id,
                    "allowed_selectors": tuple(sorted(rule.allowed_selectors)),
                },
            )
        return rule

    def _advance_state(
        self,
        state: BattleState,
        entities: Mapping[str, RuleEntity],
        context: RuleContext,
    ) -> tuple[BattleState, tuple[RuleEvent, ...]]:
        alive_teams = self._alive_teams(
            state.participants,
            entities,
            state.inactive_ids,
        )
        next_turn_number = state.turn_number + 1
        if len(alive_teams) <= 1:
            status = BattleStatus.FINISHED if alive_teams else BattleStatus.DRAW
            winners = tuple(sorted(alive_teams))
            finished = replace(
                state,
                entities=entities,
                turn_number=next_turn_number,
                status=status,
                winning_teams=winners,
                revision=state.revision + 1,
            )
            event = self._finished_event(finished, context, "defeated")
            return finished, (event,)

        if next_turn_number >= self.rules.maximum_turns:
            draw = replace(
                state,
                entities=entities,
                turn_number=next_turn_number,
                status=BattleStatus.DRAW,
                winning_teams=(),
                revision=state.revision + 1,
            )
            return draw, (self._finished_event(draw, context, "maximum_turns"),)

        for index in range(state.turn_index + 1, len(state.turn_order)):
            entity_id = state.turn_order[index]
            if self._alive(entities[entity_id]):
                return (
                    replace(
                        state,
                        entities=entities,
                        turn_number=next_turn_number,
                        turn_index=index,
                        revision=state.revision + 1,
                    ),
                    (),
                )

        next_round, order, action_progress = self._next_action_window(
            state.participants,
            entities,
            state.inactive_ids,
            state.action_progress,
            state.round_number,
        )
        if next_round is None:
            draw = replace(
                state,
                entities=entities,
                turn_number=next_turn_number,
                action_progress=action_progress,
                status=BattleStatus.DRAW,
                winning_teams=(),
                revision=state.revision + 1,
            )
            return draw, (self._finished_event(draw, context, "maximum_rounds"),)

        advanced = replace(
            state,
            entities=entities,
            round_number=next_round,
            turn_number=next_turn_number,
            turn_order=order,
            turn_index=0,
            action_progress=action_progress,
            revision=state.revision + 1,
        )
        event = RuleEvent.from_context(
            context,
            kind="combat.round.started",
            source_id=state.battle_id,
            target_id=order[0],
            subject_id="combat.round",
            values={
                "battle_id": state.battle_id,
                "round": next_round,
                "turn_order": order,
            },
            phase=ExecutionPhase.TURN_END,
        )
        return advanced, (event,)

    def _finished_event(
        self,
        state: BattleState,
        context: RuleContext,
        reason: str,
    ) -> RuleEvent:
        return RuleEvent.from_context(
            context,
            kind="combat.battle.finished",
            source_id=state.battle_id,
            target_id=state.battle_id,
            subject_id="combat.battle",
            values={
                "battle_id": state.battle_id,
                "status": state.status.value,
                "winning_teams": state.winning_teams,
                "rounds": state.round_number,
                "turns": state.turn_number,
                "reason": reason,
            },
            phase=ExecutionPhase.TURN_END,
        )

    def _turn_order(
        self,
        participants: Mapping[str, BattleParticipant],
        entities: Mapping[str, RuleEntity],
        inactive_ids: frozenset[str] = frozenset(),
    ) -> tuple[str, ...]:
        return tuple(
            sorted(
                (
                    entity_id
                    for entity_id in entities
                    if entity_id not in inactive_ids and self._alive(entities[entity_id])
                ),
                key=lambda entity_id: (
                    -self._speed(entities[entity_id]),
                    participants[entity_id].team_id,
                    participants[entity_id].slot,
                    entity_id,
                ),
            )
        )

    def _next_action_window(
        self,
        participants: Mapping[str, BattleParticipant],
        entities: Mapping[str, RuleEntity],
        inactive_ids: frozenset[str],
        action_progress: Mapping[str, float],
        current_round: int,
    ) -> tuple[int | None, tuple[str, ...], Mapping[str, float]]:
        """推进标准时间轮，直到至少有一个实体积满一次普通行动。"""

        progress: Mapping[str, float] = action_progress
        round_number = current_round + 1
        while round_number <= self.rules.maximum_rounds:
            order, progress = self._action_window(
                participants,
                entities,
                inactive_ids,
                progress,
            )
            if order:
                return round_number, order, progress
            round_number += 1
        return None, (), progress

    def _action_window(
        self,
        participants: Mapping[str, BattleParticipant],
        entities: Mapping[str, RuleEntity],
        inactive_ids: frozenset[str],
        action_progress: Mapping[str, float],
    ) -> tuple[tuple[str, ...], Mapping[str, float]]:
        progress = dict(action_progress)
        occurrences: list[tuple[float, float, StableId, int, str, int]] = []
        for entity_id, entity in entities.items():
            if entity_id in inactive_ids or not self._alive(entity):
                continue
            speed = self._speed(entity)
            efficiency = self.rules.action_efficiency(speed)
            before = progress.get(entity_id, 0.0)
            total = before + efficiency
            action_count = floor(total + 1e-9)
            remainder = total - action_count
            if remainder < 0 and remainder > -1e-8:
                remainder = 0.0
            progress[entity_id] = min(max(remainder, 0.0), 1.0 - 1e-12)
            participant = participants[entity_id]
            for ordinal in range(action_count):
                ready_at = (ordinal + 1.0 - before) / efficiency
                occurrences.append(
                    (
                        ready_at,
                        -speed,
                        participant.team_id,
                        participant.slot,
                        entity_id,
                        ordinal,
                    )
                )
        occurrences.sort()
        return tuple(value[4] for value in occurrences), MappingProxyType(progress)

    def _speed(self, entity: RuleEntity) -> float:
        if not self.rules.speed_attribute:
            return self.rules.baseline_speed
        return entity.snapshot(self.effects.attributes).value(self.rules.speed_attribute)

    def _alive_teams(
        self,
        participants: Mapping[str, BattleParticipant],
        entities: Mapping[str, RuleEntity],
        inactive_ids: frozenset[str] = frozenset(),
    ) -> set[StableId]:
        return {
            participants[entity_id].team_id
            for entity_id, entity in entities.items()
            if entity_id not in inactive_ids and self._alive(entity)
        }

    def _alive(self, entity: RuleEntity) -> bool:
        return entity.resources.get(self.health.id, self.health.minimum) > self.health.minimum

    def _targeting_context(
        self,
        actor_id: str,
        participants: Mapping[str, BattleParticipant],
        entities: Mapping[str, RuleEntity],
        context: RuleContext,
        inactive_ids: frozenset[str],
    ) -> TargetingContext:
        return TargetingContext(
            actor_id=actor_id,
            entities=entities,
            teams={key: value.team_id for key, value in participants.items()},
            slots={key: value.slot for key, value in participants.items()},
            attributes=self.effects.attributes,
            health=self.health,
            random=context.random,
            inactive_ids=inactive_ids,
        )

    def _process_external_events(
        self,
        events: tuple[RuleEvent, ...],
        entities: Mapping[str, RuleEntity],
        context: RuleContext,
        inactive_ids: frozenset[str] = frozenset(),
    ) -> tuple[dict[str, RuleEntity], tuple[RuleEvent, ...]]:
        if self.executor.triggers is None:
            return dict(entities), events
        result = self.executor.triggers.session(context, inactive_ids).process(events, entities)
        return dict(result.entities), result.events


__all__ = [
    "BattleAction",
    "BattleAbilityTargeting",
    "BattleEngine",
    "BattleParticipant",
    "BattleRules",
    "BattleState",
    "BattleStatus",
    "BattleStepResult",
]
