"""统一 Ability 条件、消耗和 Effect 编排。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Callable, Mapping

from .conditions import ConditionContext, ConditionReferences, RuleCondition
from .context import RuleContext
from .attributes import Magnitude, MagnitudeContext
from .effects import EffectEngine, EffectSpec
from .entity import RuleEntity
from .events import RuleEvent
from .errors import RuleOutcome, RuleViolation
from .ids import StableId, stable_id
from .registry import DefinitionRegistry
from .phases import ExecutionPhase
from .tags import EMPTY_TAGS, TagSet


class EffectTarget(str, Enum):
    SELF = "self"
    TARGET = "target"


@dataclass(frozen=True)
class ResourceCost:
    """Ability 执行前需要支付的资源。"""

    resource_id: StableId
    magnitude: Magnitude

    def __post_init__(self) -> None:
        object.__setattr__(self, "resource_id", stable_id(self.resource_id, field="resource id"))


@dataclass(frozen=True)
class EffectReference:
    """Ability 要施加的 Effect 及其目标。"""

    effect_id: StableId
    target: EffectTarget = EffectTarget.TARGET
    phase: ExecutionPhase = ExecutionPhase.RESOLVE

    def __post_init__(self) -> None:
        object.__setattr__(self, "effect_id", stable_id(self.effect_id, field="effect id"))


@dataclass(frozen=True)
class AbilityDefinition:
    """一个可执行行为的静态定义。"""

    id: StableId
    tags: TagSet = EMPTY_TAGS
    required_owner_tags: TagSet = EMPTY_TAGS
    blocked_owner_tags: TagSet = EMPTY_TAGS
    required_target_tags: TagSet = EMPTY_TAGS
    blocked_target_tags: TagSet = EMPTY_TAGS
    conditions: tuple[RuleCondition, ...] = ()
    target_conditions: tuple[RuleCondition, ...] = ()
    costs: tuple[ResourceCost, ...] = ()
    effects: tuple[EffectReference, ...] = ()
    cooldown_turns: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="ability id"))
        if self.cooldown_turns < 0:
            raise ValueError(f"Ability {self.id} 的 cooldown_turns 不能小于 0")


@dataclass(frozen=True)
class AbilityUse:
    """一次 Ability 执行请求。"""

    use_id: str
    ability_id: StableId
    parameters: Mapping[str, float] = field(default_factory=dict)
    context_tags: TagSet = EMPTY_TAGS

    def __post_init__(self) -> None:
        if not self.use_id.strip():
            raise ValueError("AbilityUse 缺少 use_id")
        object.__setattr__(self, "ability_id", stable_id(self.ability_id, field="ability id"))
        object.__setattr__(
            self,
            "parameters",
            MappingProxyType({str(key): float(value) for key, value in self.parameters.items()}),
        )


@dataclass(frozen=True)
class AbilityResult:
    actor: RuleEntity
    target: RuleEntity
    events: tuple[RuleEvent, ...]


@dataclass(frozen=True)
class AbilityManyResult:
    """一次 Ability 对完整实体集合执行后的结果。"""

    actor_id: str
    target_ids: tuple[str, ...]
    entities: Mapping[str, RuleEntity]
    events: tuple[RuleEvent, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "entities", MappingProxyType(dict(self.entities)))

    @property
    def actor(self) -> RuleEntity:
        return self.entities[self.actor_id]

    def entity(self, entity_id: str) -> RuleEntity:
        return self.entities[entity_id]


AbilityEventProcessor = Callable[
    [tuple[RuleEvent, ...], Mapping[str, RuleEntity]],
    tuple[Mapping[str, RuleEntity], tuple[RuleEvent, ...]],
]


class AbilityEngine:
    """执行 Ability，但不决定玩家何时可以发起玩法命令。"""

    def __init__(
        self,
        definitions: DefinitionRegistry[AbilityDefinition],
        effects: EffectEngine,
        *,
        trigger_ids: frozenset[StableId] = frozenset(),
        interceptor_ids: frozenset[StableId] = frozenset(),
        target_constraint_ids: frozenset[StableId] = frozenset(),
    ) -> None:
        self.definitions = definitions
        self.effects = effects
        self._finalize_definitions(
            trigger_ids,
            interceptor_ids,
            target_constraint_ids,
        )

    def execute(
        self,
        use: AbilityUse,
        *,
        actor: RuleEntity,
        target: RuleEntity,
        context: RuleContext,
        event_processor: AbilityEventProcessor | None = None,
    ) -> AbilityResult:
        entities = {actor.id: actor}
        if target.id != actor.id:
            entities[target.id] = target
        result = self.execute_many(
            use,
            actor_id=actor.id,
            target_ids=(target.id,),
            entities=entities,
            context=context,
            event_processor=event_processor,
        )
        return AbilityResult(result.actor, result.entity(target.id), result.events)

    def execute_many(
        self,
        use: AbilityUse,
        *,
        actor_id: str,
        target_ids: tuple[str, ...],
        entities: Mapping[str, RuleEntity],
        context: RuleContext,
        event_processor: AbilityEventProcessor | None = None,
    ) -> AbilityManyResult:
        """一次支付消耗，并按目标顺序逐段结算同一个 Ability。"""

        if not target_ids:
            raise RuleViolation(
                "ability.no_valid_target",
                f"Ability {use.ability_id} 没有有效目标",
                {"ability_id": use.ability_id, "actor_id": actor_id},
            )
        if len(set(target_ids)) != len(target_ids):
            raise ValueError("Ability.execute_many 的 target_ids 不能重复")
        states = dict(entities)
        try:
            actor = states[actor_id]
            targets = tuple(states[target_id] for target_id in target_ids)
        except KeyError as exc:
            raise KeyError(f"Ability 执行缺少规则实体：{exc.args[0]}") from exc
        primary_target = targets[0]
        definition = self.definitions.require(use.ability_id)
        if definition.id not in actor.abilities:
            raise RuleViolation(
                "ability.not_owned",
                f"实体 {actor.id} 没有 Ability：{definition.id}",
                {"ability_id": definition.id, "actor_id": actor.id},
            )
        if actor.cooldowns.get(definition.id, 0) > 0:
            raise RuleViolation(
                "ability.cooldown_active",
                f"Ability {definition.id} 仍在冷却中",
                {"ability_id": definition.id, "turns": actor.cooldowns[definition.id]},
            )

        execution_context = context.with_tags(use.context_tags).at_phase(ExecutionPhase.SELECT_TARGET)
        actor_tags = actor.tags.merged(use.context_tags, context.effective_tags)
        if not actor_tags.allows(
            required=definition.required_owner_tags,
            blocked=definition.blocked_owner_tags,
        ):
            raise RuleViolation(
                "ability.owner_condition_failed",
                f"实体 {actor.id} 不满足 Ability {definition.id} 的使用条件",
                {"ability_id": definition.id, "actor_id": actor.id},
            )
        condition_context = ConditionContext(
            actor,
            primary_target,
            self.effects.attributes,
            execution_context,
        )
        failed_owner = self.effects.conditions.failed(definition.conditions, condition_context)
        if failed_owner:
            raise RuleViolation(
                "ability.owner_condition_failed",
                f"实体 {actor.id} 不满足 Ability {definition.id} 的使用条件",
                {"ability_id": definition.id, "conditions": failed_owner},
            )
        for target in targets:
            target_tags = target.tags.merged(use.context_tags, context.effective_tags)
            if not target_tags.allows(
                required=definition.required_target_tags,
                blocked=definition.blocked_target_tags,
            ):
                raise RuleViolation(
                    "ability.target_condition_failed",
                    f"目标 {target.id} 不满足 Ability {definition.id} 的目标条件",
                    {"ability_id": definition.id, "target_id": target.id},
                )
            target_context = ConditionContext(
                actor,
                target,
                self.effects.attributes,
                execution_context,
            )
            failed_target = self.effects.conditions.failed(
                definition.target_conditions,
                target_context,
            )
            if failed_target:
                raise RuleViolation(
                    "ability.target_condition_failed",
                    f"目标 {target.id} 不满足 Ability {definition.id} 的目标条件",
                    {
                        "ability_id": definition.id,
                        "target_id": target.id,
                        "conditions": failed_target,
                    },
                )

        actor_state, paid_costs = self._pay_costs(use, definition, actor, primary_target)
        states[actor_id] = actor_state
        initial_events = (
            RuleEvent.from_context(
                context,
                kind="ability.started",
                source_id=actor.id,
                target_id=primary_target.id,
                subject_id=definition.id,
                values={"use_id": use.use_id, "target_ids": target_ids},
                phase=ExecutionPhase.PREPARE,
            ),
            *(
                RuleEvent.from_context(
                    context,
                    kind="resource.changed",
                    source_id=actor.id,
                    target_id=actor.id,
                    subject_id=resource_id,
                    values={
                        "delta": -value,
                        "current": actor_state.resources[resource_id],
                        "reason": definition.id,
                    },
                    phase=ExecutionPhase.PAY_COST,
                )
                for resource_id, value in sorted(paid_costs.items())
                if value
            ),
        )
        states, processed = self._process_event_batch(
            event_processor,
            initial_events,
            states,
        )
        events: list[RuleEvent] = list(processed)
        interrupted = self._interrupted(processed, actor_id)
        for index, reference in enumerate(definition.effects, start=1):
            if interrupted:
                break
            destinations = (actor_id,) if reference.target is EffectTarget.SELF else target_ids
            for target_index, destination_id in enumerate(destinations, start=1):
                actor_state = states[actor_id]
                destination = states[destination_id]
                result = self.effects.apply_or_reject(
                    EffectSpec(
                        instance_id=f"{use.use_id}:effect:{index}:target:{target_index}",
                        definition_id=reference.effect_id,
                        source_id=actor_state.id,
                        parameters=use.parameters,
                    ),
                    source=actor_state,
                    target=destination,
                    context=context.with_tags(use.context_tags).at_phase(reference.phase),
                )
                if result.source is not None:
                    states[result.source.id] = result.source
                states[result.target.id] = result.target
                states, processed = self._process_event_batch(
                    event_processor,
                    result.events,
                    states,
                )
                events.extend(processed)
                if self._interrupted(processed, actor_id):
                    interrupted = True
                    break

        if definition.cooldown_turns:
            actor_state = states[actor_id]
            cooldowns = dict(actor_state.cooldowns)
            cooldowns[definition.id] = definition.cooldown_turns
            actor_state = actor_state.replace_cooldowns(cooldowns)
            states[actor_id] = actor_state
            cooldown_event = RuleEvent.from_context(
                context,
                kind="ability.cooldown_started",
                source_id=actor.id,
                target_id=actor.id,
                subject_id=definition.id,
                values={"turns": definition.cooldown_turns},
                phase=ExecutionPhase.AFTER_APPLY,
            )
            states, processed = self._process_event_batch(
                event_processor,
                (cooldown_event,),
                states,
            )
            events.extend(processed)

        completed_event = RuleEvent.from_context(
            context,
            kind="ability.completed",
            source_id=actor.id,
            target_id=primary_target.id,
            subject_id=definition.id,
            values={
                "use_id": use.use_id,
                "target_ids": target_ids,
                "interrupted": interrupted,
            },
            phase=ExecutionPhase.AFTER_APPLY,
        )
        states, processed = self._process_event_batch(
            event_processor,
            (completed_event,),
            states,
        )
        events.extend(processed)
        return AbilityManyResult(actor_id, target_ids, states, tuple(events))

    @staticmethod
    def _interrupted(events: tuple[RuleEvent, ...], actor_id: str) -> bool:
        return any(
            event.kind == "combat.action.interrupted" and event.target_id == actor_id
            for event in events
        )

    @staticmethod
    def _process_event_batch(
        processor: AbilityEventProcessor | None,
        batch: tuple[RuleEvent, ...],
        states: Mapping[str, RuleEntity],
    ) -> tuple[dict[str, RuleEntity], tuple[RuleEvent, ...]]:
        if processor is None:
            return dict(states), batch
        processed_states, events = processor(batch, states)
        missing = set(states) - set(processed_states)
        if missing:
            raise KeyError(f"事件处理器丢失规则实体：{', '.join(sorted(missing))}")
        return dict(processed_states), events

    def try_execute(
        self,
        use: AbilityUse,
        *,
        actor: RuleEntity,
        target: RuleEntity,
        context: RuleContext,
    ) -> RuleOutcome[AbilityResult]:
        """把预期规则失败转换为稳定 RuleOutcome。"""

        checkpoint = context.random.checkpoint()
        try:
            return RuleOutcome.success(
                self.execute(use, actor=actor, target=target, context=context)
            )
        except RuleViolation as exc:
            context.random.restore(checkpoint)
            return RuleOutcome.failed(exc.failure)

    def _pay_costs(
        self,
        use: AbilityUse,
        definition: AbilityDefinition,
        actor: RuleEntity,
        target: RuleEntity,
    ) -> tuple[RuleEntity, Mapping[StableId, float]]:
        if not definition.costs:
            return actor, {}
        source_snapshot = actor.snapshot(self.effects.attributes)
        target_snapshot = target.snapshot(self.effects.attributes)
        context = MagnitudeContext(
            source_snapshot,
            target_snapshot,
            use.parameters,
            actor.resources,
            target.resources,
        )
        resources = dict(actor.resources)
        costs: dict[StableId, float] = {}
        for cost in definition.costs:
            if cost.resource_id not in self.effects.resources:
                raise KeyError(f"Ability {definition.id} 引用了未知资源：{cost.resource_id}")
            value = max(0.0, self.effects.magnitudes.evaluate(cost.magnitude, context))
            costs[cost.resource_id] = costs.get(cost.resource_id, 0.0) + value
        for key, value in costs.items():
            if resources.get(key, 0.0) < value:
                raise RuleViolation(
                    "resource.insufficient",
                    f"实体 {actor.id} 的资源 {key} 不足",
                    {
                        "ability_id": definition.id,
                        "resource_id": key,
                        "required": value,
                        "current": resources.get(key, 0.0),
                    },
                )
        for key, value in costs.items():
            resources[key] = resources.get(key, 0.0) - value
        return actor.replace_resources(resources), MappingProxyType(costs)

    def _finalize_definitions(
        self,
        trigger_ids: frozenset[StableId],
        interceptor_ids: frozenset[StableId],
        target_constraint_ids: frozenset[StableId],
    ) -> None:
        """在运行前检查 Ability、Effect、资源之间的全部静态引用。"""

        ability_ids = frozenset(self.definitions.ids())
        condition_references = ConditionReferences(
            attributes=frozenset(self.effects.attributes.definitions),
            resources=frozenset(self.effects.resources),
            effects=frozenset(self.effects.definitions.ids()),
        )
        for definition in self.definitions:
            self.effects.conditions.validate(definition.conditions, condition_references)
            self.effects.conditions.validate(definition.target_conditions, condition_references)
            for cost in definition.costs:
                self.effects.magnitudes.validate(
                    cost.magnitude,
                    condition_references.attributes,
                    condition_references.resources,
                )
                if cost.resource_id not in self.effects.resources:
                    raise KeyError(
                        f"Ability {definition.id} 引用了未知资源：{cost.resource_id}"
                    )
            for reference in definition.effects:
                if not self.effects.definitions.contains(reference.effect_id):
                    raise KeyError(
                        f"Ability {definition.id} 引用了未知 Effect：{reference.effect_id}"
                    )
        self.effects.finalize(
            ability_ids,
            trigger_ids,
            interceptor_ids,
            target_constraint_ids,
        )
        self.definitions.freeze()


__all__ = [
    "AbilityDefinition",
    "AbilityEngine",
    "AbilityEventProcessor",
    "AbilityManyResult",
    "AbilityResult",
    "AbilityUse",
    "EffectReference",
    "EffectTarget",
    "ResourceCost",
]
