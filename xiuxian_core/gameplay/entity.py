"""参与规则计算的实体运行状态。"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Mapping

from .attributes import AttributeModifier, AttributeResolver, AttributeSnapshot
from .ids import StableId, stable_id
from .tags import EMPTY_TAGS, TagSet


@dataclass(frozen=True)
class ActiveEffect:
    """已经施加到实体上的 Effect 运行实例。"""

    instance_id: str
    definition_id: StableId
    source_id: str
    modifiers: tuple[AttributeModifier, ...] = ()
    granted_tags: TagSet = EMPTY_TAGS
    granted_abilities: frozenset[StableId] = frozenset()
    granted_triggers: frozenset[StableId] = frozenset()
    granted_interceptors: frozenset[StableId] = frozenset()
    granted_target_constraints: frozenset[StableId] = frozenset()
    remaining_turns: int | None = None
    stacks: int = 1
    modifier_counts: tuple[int, ...] = ()
    parameters: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.instance_id.strip():
            raise ValueError("ActiveEffect 缺少 instance_id")
        object.__setattr__(self, "definition_id", stable_id(self.definition_id, field="effect id"))
        abilities = frozenset(stable_id(value, field="ability id") for value in self.granted_abilities)
        object.__setattr__(self, "granted_abilities", abilities)
        triggers = frozenset(stable_id(value, field="trigger id") for value in self.granted_triggers)
        object.__setattr__(self, "granted_triggers", triggers)
        interceptors = frozenset(
            stable_id(value, field="interceptor id") for value in self.granted_interceptors
        )
        object.__setattr__(self, "granted_interceptors", interceptors)
        constraints = frozenset(
            stable_id(value, field="target constraint id")
            for value in self.granted_target_constraints
        )
        object.__setattr__(self, "granted_target_constraints", constraints)
        if self.remaining_turns is not None and self.remaining_turns < 1:
            raise ValueError("持续效果的 remaining_turns 必须大于 0")
        if self.stacks < 1:
            raise ValueError("效果层数必须大于 0")
        if self.modifier_counts:
            counts = self.modifier_counts
        elif len(self.modifiers) % self.stacks == 0:
            counts = (len(self.modifiers) // self.stacks,) * self.stacks
        else:
            raise ValueError("多层 ActiveEffect 必须提供 modifier_counts")
        if len(counts) != self.stacks or sum(counts) != len(self.modifiers):
            raise ValueError("ActiveEffect.modifier_counts 与层数或属性修改数量不一致")
        object.__setattr__(self, "modifier_counts", counts)
        object.__setattr__(
            self,
            "parameters",
            MappingProxyType({str(key): float(value) for key, value in self.parameters.items()}),
        )


@dataclass(frozen=True)
class TriggerBinding:
    """实体当前拥有的 Trigger 及其授予来源。"""

    trigger_id: StableId
    owner_id: str
    source_id: str
    effect_instance_id: str
    parameters: Mapping[str, float] = field(default_factory=dict)
    stacks: int = 1


@dataclass(frozen=True)
class InterceptorBinding:
    interceptor_id: StableId
    owner_id: str
    source_id: str
    effect_instance_id: str


@dataclass(frozen=True)
class TargetConstraintBinding:
    constraint_id: StableId
    owner_id: str
    source_id: str
    effect_instance_id: str


@dataclass(frozen=True)
class RuleEntity:
    """规则内核看到的实体，不包含数据库和展示字段。"""

    id: str
    base_attributes: Mapping[StableId, float] = field(default_factory=dict)
    resources: Mapping[StableId, float] = field(default_factory=dict)
    base_tags: TagSet = EMPTY_TAGS
    base_abilities: frozenset[StableId] = frozenset()
    active_effects: tuple[ActiveEffect, ...] = ()
    cooldowns: Mapping[StableId, int] = field(default_factory=dict)
    revision: int = 0

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("规则实体缺少 id")
        attributes = {stable_id(key, field="attribute id"): float(value) for key, value in self.base_attributes.items()}
        resources = {stable_id(key, field="resource id"): float(value) for key, value in self.resources.items()}
        abilities = frozenset(stable_id(value, field="ability id") for value in self.base_abilities)
        cooldowns = {stable_id(key, field="ability id"): int(value) for key, value in self.cooldowns.items() if int(value) > 0}
        object.__setattr__(self, "base_attributes", MappingProxyType(attributes))
        object.__setattr__(self, "resources", MappingProxyType(resources))
        object.__setattr__(self, "base_abilities", abilities)
        object.__setattr__(self, "cooldowns", MappingProxyType(cooldowns))

    @property
    def tags(self) -> TagSet:
        return self.base_tags.merged(*(effect.granted_tags for effect in self.active_effects))

    @property
    def abilities(self) -> frozenset[StableId]:
        values = set(self.base_abilities)
        for effect in self.active_effects:
            values.update(effect.granted_abilities)
        return frozenset(values)

    @property
    def modifiers(self) -> tuple[AttributeModifier, ...]:
        return tuple(modifier for effect in self.active_effects for modifier in effect.modifiers)

    @property
    def triggers(self) -> frozenset[StableId]:
        values: set[StableId] = set()
        for effect in self.active_effects:
            values.update(effect.granted_triggers)
        return frozenset(values)

    @property
    def trigger_bindings(self) -> tuple[TriggerBinding, ...]:
        values = []
        for effect in self.active_effects:
            values.extend(
                TriggerBinding(
                    trigger_id=trigger_id,
                    owner_id=self.id,
                    source_id=effect.source_id,
                    effect_instance_id=effect.instance_id,
                    parameters=effect.parameters,
                    stacks=effect.stacks,
                )
                for trigger_id in effect.granted_triggers
            )
        return tuple(
            sorted(
                values,
                key=lambda value: (
                    value.trigger_id,
                    value.source_id,
                    value.effect_instance_id,
                ),
            )
        )

    @property
    def interceptor_bindings(self) -> tuple[InterceptorBinding, ...]:
        values = []
        for effect in self.active_effects:
            values.extend(
                InterceptorBinding(
                    interceptor_id=interceptor_id,
                    owner_id=self.id,
                    source_id=effect.source_id,
                    effect_instance_id=effect.instance_id,
                )
                for interceptor_id in effect.granted_interceptors
            )
        return tuple(
            sorted(
                values,
                key=lambda value: (
                    value.interceptor_id,
                    value.source_id,
                    value.effect_instance_id,
                ),
            )
        )

    @property
    def target_constraint_bindings(self) -> tuple[TargetConstraintBinding, ...]:
        values = []
        for effect in self.active_effects:
            values.extend(
                TargetConstraintBinding(
                    constraint_id=constraint_id,
                    owner_id=self.id,
                    source_id=effect.source_id,
                    effect_instance_id=effect.instance_id,
                )
                for constraint_id in effect.granted_target_constraints
            )
        return tuple(
            sorted(
                values,
                key=lambda value: (
                    value.constraint_id,
                    value.source_id,
                    value.effect_instance_id,
                ),
            )
        )

    def snapshot(self, resolver: AttributeResolver) -> AttributeSnapshot:
        return resolver.resolve(self.base_attributes, self.modifiers, self.tags)

    def replace_resources(self, values: Mapping[StableId, float]) -> "RuleEntity":
        return replace(self, resources=values, revision=self.revision + 1)

    def replace_effects(self, values: tuple[ActiveEffect, ...]) -> "RuleEntity":
        return replace(self, active_effects=values, revision=self.revision + 1)

    def replace_cooldowns(self, values: Mapping[StableId, int]) -> "RuleEntity":
        return replace(self, cooldowns=values, revision=self.revision + 1)

    def advance_turn(self) -> "RuleEntity":
        """推进一回合，统一缩短效果持续时间和能力冷却。"""

        effects = tuple(
            replace(effect, remaining_turns=effect.remaining_turns - 1)
            for effect in self.active_effects
            if effect.remaining_turns is None or effect.remaining_turns > 1
        )
        cooldowns = {key: value - 1 for key, value in self.cooldowns.items() if value > 1}
        return replace(self, active_effects=effects, cooldowns=cooldowns, revision=self.revision + 1)


__all__ = [
    "ActiveEffect",
    "InterceptorBinding",
    "RuleEntity",
    "TargetConstraintBinding",
    "TriggerBinding",
]
