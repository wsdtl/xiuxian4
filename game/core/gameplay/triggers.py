"""由结构化事件驱动的规则触发链。"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from .conditions import ConditionContext, ConditionReferences, RuleCondition
from .context import RuleContext
from .effects import EffectEngine, EffectSpec
from .entity import RuleEntity, TriggerBinding
from .events import RuleEvent
from .ids import StableId, stable_id
from .phases import ExecutionPhase
from .registry import DefinitionRegistry


class TriggerTarget(str, Enum):
    OWNER = "owner"
    EVENT_SOURCE = "event_source"
    EVENT_TARGET = "event_target"


class TriggerOwner(str, Enum):
    ANY = "any"
    EVENT_SOURCE = "event_source"
    EVENT_TARGET = "event_target"


class TriggerSource(str, Enum):
    OWNER = "owner"
    GRANT_SOURCE = "grant_source"
    EVENT_SOURCE = "event_source"
    EVENT_TARGET = "event_target"


@dataclass(frozen=True)
class TriggerDefinition:
    """监听一种事件，条件成立后施加一个 Effect。"""

    id: StableId
    event_kind: StableId
    effect_id: StableId
    target: TriggerTarget = TriggerTarget.EVENT_TARGET
    owner: TriggerOwner = TriggerOwner.EVENT_TARGET
    source: TriggerSource = TriggerSource.OWNER
    conditions: tuple[RuleCondition, ...] = ()
    phase: ExecutionPhase = ExecutionPhase.AFTER_APPLY
    chance: float = 1.0
    max_activations_per_execution: int = 64

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="trigger id"))
        object.__setattr__(self, "event_kind", stable_id(self.event_kind, field="event kind"))
        object.__setattr__(self, "effect_id", stable_id(self.effect_id, field="effect id"))
        if not 0 <= self.chance <= 1:
            raise ValueError("Trigger.chance 必须在 0 到 1 之间")
        if self.max_activations_per_execution < 1:
            raise ValueError("Trigger.max_activations_per_execution 必须大于 0")


@dataclass(frozen=True)
class TriggerResult:
    entities: Mapping[str, RuleEntity]
    events: tuple[RuleEvent, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "entities", MappingProxyType(dict(self.entities)))

    def entity(self, entity_id: str) -> RuleEntity:
        try:
            return self.entities[entity_id]
        except KeyError as exc:
            raise KeyError(f"触发结果中不存在实体：{entity_id}") from exc


class TriggerSession:
    """在一次规则动作中跨多个事件批次保留触发次数和序列。"""

    def __init__(
        self,
        engine: "TriggerEngine",
        context: RuleContext,
        disabled_owner_ids: frozenset[str] = frozenset(),
    ) -> None:
        self.engine = engine
        self.context = context
        self.disabled_owner_ids = disabled_owner_ids
        self.activations: dict[tuple[str, StableId, str], int] = {}
        self.sequence = 0

    def process(
        self,
        initial_events: tuple[RuleEvent, ...],
        entities: Mapping[str, RuleEntity],
    ) -> TriggerResult:
        return self.engine._process(initial_events, entities=entities, session=self)


class TriggerEngine:
    """消费规则事件并执行实体当前拥有的 Trigger。"""

    def __init__(
        self,
        definitions: DefinitionRegistry[TriggerDefinition],
        effects: EffectEngine,
    ) -> None:
        self.definitions = definitions
        self.effects = effects
        self._validate_and_freeze()

    def process(
        self,
        initial_events: tuple[RuleEvent, ...],
        *,
        entities: Mapping[str, RuleEntity],
        context: RuleContext,
    ) -> TriggerResult:
        """独立处理一个事件批次；Ability 编排使用 session() 保留全程状态。"""

        return self.session(context).process(initial_events, entities)

    def session(
        self,
        context: RuleContext,
        disabled_owner_ids: frozenset[str] = frozenset(),
    ) -> TriggerSession:
        return TriggerSession(self, context, disabled_owner_ids)

    def _process(
        self,
        initial_events: tuple[RuleEvent, ...],
        *,
        entities: Mapping[str, RuleEntity],
        session: TriggerSession,
    ) -> TriggerResult:
        context = session.context
        states = dict(entities)
        events = list(initial_events)
        queue = deque((event, context.trigger_depth) for event in initial_events)

        while queue:
            event, depth = queue.popleft()
            for owner_id in sorted(states):
                if owner_id in session.disabled_owner_ids:
                    continue
                for binding in states[owner_id].trigger_bindings:
                    owner = states[owner_id]
                    definition = self.definitions.require(binding.trigger_id)
                    if definition.event_kind != event.kind:
                        continue
                    if not self._owner_matches(definition.owner, owner, event):
                        continue
                    activation_key = (
                        owner.id,
                        definition.id,
                        binding.effect_instance_id,
                    )
                    count = session.activations.get(activation_key, 0)
                    if count >= definition.max_activations_per_execution:
                        continue
                    destination = self._target(definition.target, owner, event, states)
                    if destination is None:
                        continue
                    effect_source = self._source(
                        definition.source,
                        binding,
                        owner,
                        event,
                        states,
                    )
                    if effect_source is None:
                        continue
                    trigger_context = context.at_trigger_depth(depth).next_trigger().at_phase(
                        definition.phase
                    )
                    condition_context = ConditionContext(
                        owner,
                        destination,
                        self.effects.attributes,
                        trigger_context,
                        event,
                    )
                    if not self.effects.conditions.allows(definition.conditions, condition_context):
                        continue
                    chance_roll = None
                    if definition.chance < 1:
                        chance_roll = trigger_context.random.random()
                        if chance_roll >= definition.chance:
                            continue
                    session.activations[activation_key] = count + 1
                    session.sequence += 1
                    result = self.effects.apply_or_reject(
                        EffectSpec(
                            instance_id=f"{context.trace_id}:trigger:{session.sequence}",
                            definition_id=definition.effect_id,
                            source_id=effect_source.id,
                            parameters={
                                **binding.parameters,
                                "effect.stacks": float(binding.stacks),
                                **self._event_parameters(event),
                            },
                        ),
                        source=effect_source,
                        target=destination,
                        context=trigger_context,
                        event=event,
                    )
                    if result.source is not None:
                        states[result.source.id] = result.source
                    states[result.target.id] = result.target
                    generated = (
                        RuleEvent.from_context(
                            trigger_context,
                            kind="trigger.activated",
                            source_id=effect_source.id,
                            target_id=destination.id,
                            subject_id=definition.id,
                            values={
                                "event_kind": event.kind,
                                "owner_id": owner.id,
                                "grant_source_id": binding.source_id,
                                "depth": trigger_context.trigger_depth,
                                "chance": definition.chance,
                                "chance_roll": chance_roll,
                            },
                            phase=definition.phase,
                        ),
                        *result.events,
                    )
                    events.extend(generated)
                    queue.extend((generated_event, trigger_context.trigger_depth) for generated_event in generated)
        return TriggerResult(states, tuple(events))

    def _validate_and_freeze(self) -> None:
        references = ConditionReferences(
            attributes=frozenset(self.effects.attributes.definitions),
            resources=frozenset(self.effects.resources),
            effects=frozenset(self.effects.definitions.ids()),
        )
        for definition in self.definitions:
            if not self.effects.definitions.contains(definition.effect_id):
                raise KeyError(
                    f"Trigger {definition.id} 引用了未知 Effect：{definition.effect_id}"
                )
            self.effects.conditions.validate(definition.conditions, references)
        self.definitions.freeze()

    @staticmethod
    def _target(
        target: TriggerTarget,
        owner: RuleEntity,
        event: RuleEvent,
        states: Mapping[str, RuleEntity],
    ) -> RuleEntity | None:
        if target is TriggerTarget.OWNER:
            return owner
        entity_id = event.source_id if target is TriggerTarget.EVENT_SOURCE else event.target_id
        return states.get(entity_id)

    @staticmethod
    def _source(
        source: TriggerSource,
        binding: TriggerBinding,
        owner: RuleEntity,
        event: RuleEvent,
        states: Mapping[str, RuleEntity],
    ) -> RuleEntity | None:
        if source is TriggerSource.OWNER:
            return owner
        if source is TriggerSource.GRANT_SOURCE:
            return states.get(binding.source_id)
        entity_id = event.source_id if source is TriggerSource.EVENT_SOURCE else event.target_id
        return states.get(entity_id)

    @staticmethod
    def _owner_matches(owner_rule: TriggerOwner, owner: RuleEntity, event: RuleEvent) -> bool:
        if owner_rule is TriggerOwner.ANY:
            return True
        expected = event.source_id if owner_rule is TriggerOwner.EVENT_SOURCE else event.target_id
        return owner.id == expected

    @staticmethod
    def _event_parameters(event: RuleEvent) -> dict[str, float]:
        result: dict[str, float] = {}
        for key, value in event.values.items():
            if isinstance(value, int | float):
                result[f"event.{key}"] = float(value)
        return result


__all__ = [
    "TriggerDefinition",
    "TriggerEngine",
    "TriggerOwner",
    "TriggerResult",
    "TriggerSession",
    "TriggerSource",
    "TriggerTarget",
]
