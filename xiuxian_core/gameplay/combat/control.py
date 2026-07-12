"""控制命中、抵抗、韧性和持续时间协议。"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from ..attributes import AttributeResolver
from ..effects import (
    EffectContribution,
    EffectFact,
    EffectOperationContext,
    EffectOperationHandlers,
    RuleReferences,
)
from ..entity import RuleEntity
from ..ids import StableId, stable_id
from ..registry import DefinitionRegistry
from ..tags import Tag, TagSet


@dataclass(frozen=True)
class ControlDefinition:
    id: StableId
    tag: Tag
    base_chance: float
    base_duration_turns: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="control id"))
        if not isinstance(self.tag, Tag):
            object.__setattr__(self, "tag", Tag(str(self.tag)))
        if not 0 <= self.base_chance <= 1:
            raise ValueError("ControlDefinition.base_chance 必须在 0 到 1 之间")
        if self.base_duration_turns < 1:
            raise ValueError("ControlDefinition.base_duration_turns 必须大于 0")


@dataclass(frozen=True)
class ControlStats:
    source_control_chance_attribute: StableId | None = None
    target_control_resistance_attribute: StableId | None = None
    target_tenacity_attribute: StableId | None = None
    minimum_chance: float = 0.0
    maximum_chance: float = 1.0
    maximum_tenacity: float = 0.9

    def __post_init__(self) -> None:
        for field_name in (
            "source_control_chance_attribute",
            "target_control_resistance_attribute",
            "target_tenacity_attribute",
        ):
            value = getattr(self, field_name)
            if value:
                object.__setattr__(self, field_name, stable_id(value, field=field_name))
        if not 0 <= self.minimum_chance <= self.maximum_chance <= 1:
            raise ValueError("控制概率边界必须位于 0 到 1 之间")
        if not 0 <= self.maximum_tenacity < 1:
            raise ValueError("maximum_tenacity 必须在 0 到 1 之间")


@dataclass(frozen=True)
class ControlResolution:
    applied: bool
    chance: float
    roll: float
    duration_turns: int


class ControlEngine:
    def __init__(
        self,
        definitions: DefinitionRegistry[ControlDefinition],
        attributes: AttributeResolver,
        stats: ControlStats | None = None,
    ) -> None:
        self.definitions = definitions
        self.attributes = attributes
        self.stats = stats or ControlStats()
        self._validate_and_freeze()

    def resolve(
        self,
        control_id: StableId,
        *,
        source: RuleEntity,
        target: RuleEntity,
        random,
    ) -> ControlResolution:
        definition = self.definitions.require(control_id)
        source_snapshot = source.snapshot(self.attributes)
        target_snapshot = target.snapshot(self.attributes)
        chance = definition.base_chance
        if self.stats.source_control_chance_attribute:
            chance += source_snapshot.value(self.stats.source_control_chance_attribute)
        if self.stats.target_control_resistance_attribute:
            chance -= target_snapshot.value(self.stats.target_control_resistance_attribute)
        chance = min(self.stats.maximum_chance, max(self.stats.minimum_chance, chance))
        roll = random.random()
        tenacity = 0.0
        if self.stats.target_tenacity_attribute:
            tenacity = target_snapshot.value(self.stats.target_tenacity_attribute)
        tenacity = min(self.stats.maximum_tenacity, max(0.0, tenacity))
        duration = max(1, ceil(definition.base_duration_turns * (1.0 - tenacity)))
        return ControlResolution(roll < chance, chance, roll, duration)

    def _validate_and_freeze(self) -> None:
        attributes = set(self.attributes.definitions)
        unknown = {
            value
            for value in (
                self.stats.source_control_chance_attribute,
                self.stats.target_control_resistance_attribute,
                self.stats.target_tenacity_attribute,
            )
            if value and value not in attributes
        }
        if unknown:
            raise KeyError(f"控制协议引用未知属性：{', '.join(sorted(unknown))}")
        self.definitions.freeze()

    def ids(self) -> frozenset[StableId]:
        return frozenset(self.definitions.ids())


@dataclass(frozen=True)
class ApplyControl:
    id: StableId
    control_id: StableId

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="operation id"))
        object.__setattr__(self, "control_id", stable_id(self.control_id, field="control id"))


def register_control_operation(
    handlers: EffectOperationHandlers,
    engine: ControlEngine,
) -> None:
    def execute(operation: ApplyControl, context: EffectOperationContext) -> EffectContribution:
        definition = engine.definitions.require(operation.control_id)
        resolution = engine.resolve(
            operation.control_id,
            source=context.source,
            target=context.target,
            random=context.rule.random,
        )
        fact = EffectFact(
            "combat.control.resolved",
            operation.control_id,
            {
                "operation_id": operation.id,
                "applied": resolution.applied,
                "chance": resolution.chance,
                "roll": resolution.roll,
                "duration_turns": resolution.duration_turns,
            },
        )
        if not resolution.applied:
            return EffectContribution(facts=(fact,))
        return EffectContribution(
            granted_tags=TagSet.of(definition.tag),
            facts=(fact,),
            duration_override=resolution.duration_turns,
        )

    def validate(operation: ApplyControl, _references: RuleReferences) -> None:
        if not engine.definitions.contains(operation.control_id):
            raise KeyError(f"控制操作 {operation.id} 引用了未知控制：{operation.control_id}")

    handlers.register(ApplyControl, execute, validate)


__all__ = [
    "ApplyControl",
    "ControlDefinition",
    "ControlEngine",
    "ControlResolution",
    "ControlStats",
    "register_control_operation",
]
