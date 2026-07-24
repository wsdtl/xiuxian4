"""可组合 Effect 定义与执行器。"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from types import MappingProxyType
from typing import Callable, Mapping, Protocol, TypeVar

from .conditions import ConditionContext, ConditionEngine, ConditionReferences, RuleCondition
from .context import RuleContext
from .attributes import (
    AttributeModifier,
    AttributeResolver,
    Magnitude,
    MagnitudeContext,
    MagnitudeEvaluators,
    ModifierLayer,
    ResourceDefinition,
)
from .entity import ActiveEffect, RuleEntity
from .events import RuleEvent
from .errors import RuleViolation
from .ids import StableId, stable_id
from .phases import ExecutionPhase
from .registry import DefinitionRegistry
from .tags import EMPTY_TAGS, Tag, TagSet


_APPLICATION_REJECTION_REASONS = {
    "effect.target_blocked": "target_blocked",
    "effect.condition_failed": "condition_failed",
}


class StackingPolicy(str, Enum):
    """同一 Effect 再次施加时的处理方式。"""

    REPLACE = "replace"
    REFRESH = "refresh"
    STACK = "stack"
    INDEPENDENT = "independent"


@dataclass(frozen=True)
class ModifyAttribute:
    """在 Effect 有效期间提供一条属性修改。"""

    id: StableId
    attribute_id: StableId
    layer: ModifierLayer
    magnitude: Magnitude
    required_tags: TagSet = EMPTY_TAGS
    blocked_tags: TagSet = EMPTY_TAGS
    priority: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="operation id"))
        object.__setattr__(self, "attribute_id", stable_id(self.attribute_id, field="attribute id"))


@dataclass(frozen=True)
class ChangeResource:
    """立即改变目标当前资源；正数恢复，负数消耗。"""

    id: StableId
    resource_id: StableId
    magnitude: Magnitude

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="operation id"))
        object.__setattr__(self, "resource_id", stable_id(self.resource_id, field="resource id"))


@dataclass(frozen=True)
class TransferResource:
    """从 Effect 目标抽取资源并按效率交给来源。"""

    id: StableId
    resource_id: StableId
    magnitude: Magnitude
    efficiency: float = 1.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="operation id"))
        object.__setattr__(self, "resource_id", stable_id(self.resource_id, field="resource id"))
        if self.efficiency < 0:
            raise ValueError("TransferResource.efficiency 不能小于 0")


@dataclass(frozen=True)
class DispelEffects:
    """按定义、标签和来源移除目标身上的完整 Effect 实例。"""

    id: StableId
    effect_id: StableId | None = None
    required_tags: TagSet = EMPTY_TAGS
    blocked_tags: TagSet = EMPTY_TAGS
    maximum: int | None = None
    source_only: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="operation id"))
        if self.effect_id:
            object.__setattr__(self, "effect_id", stable_id(self.effect_id, field="effect id"))
        if self.maximum is not None and self.maximum < 1:
            raise ValueError("DispelEffects.maximum 必须大于 0")


@dataclass(frozen=True)
class ConsumeEffectStacks:
    """消耗指定 Effect 层数，层数归零时移除整个实例。"""

    id: StableId
    effect_id: StableId
    stacks: int = 1
    source_only: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="operation id"))
        object.__setattr__(self, "effect_id", stable_id(self.effect_id, field="effect id"))
        if self.stacks < 1:
            raise ValueError("ConsumeEffectStacks.stacks 必须大于 0")


@dataclass(frozen=True)
class ModifyEffectDuration:
    """增加或缩短指定 Effect 的剩余回合，永久效果不受影响。"""

    id: StableId
    effect_id: StableId
    turns: int
    source_only: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="operation id"))
        object.__setattr__(self, "effect_id", stable_id(self.effect_id, field="effect id"))
        if self.turns == 0:
            raise ValueError("ModifyEffectDuration.turns 不能为 0")


@dataclass(frozen=True)
class ModifyCooldown:
    """调整目标 Ability 冷却；set_to 优先于 turns。"""

    id: StableId
    ability_id: StableId
    turns: int = 0
    set_to: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="operation id"))
        object.__setattr__(self, "ability_id", stable_id(self.ability_id, field="ability id"))
        if self.set_to is not None and self.set_to < 0:
            raise ValueError("ModifyCooldown.set_to 不能小于 0")
        if self.set_to is None and self.turns == 0:
            raise ValueError("ModifyCooldown 必须设置 turns 或 set_to")


@dataclass(frozen=True)
class ModifyCurrentCooldowns:
    """调整目标当前已有冷却，避免内容提前知道对方 Ability ID。"""

    id: StableId
    turns: int
    selection: str = "longest"

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="operation id"))
        if self.turns == 0:
            raise ValueError("ModifyCurrentCooldowns.turns 不能为 0")
        if self.selection not in {"longest", "all"}:
            raise ValueError("ModifyCurrentCooldowns.selection 只能是 longest 或 all")


@dataclass(frozen=True)
class GrantTag:
    """在 Effect 有效期间授予规则标签。"""

    id: StableId
    tag: Tag

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="operation id"))
        if not isinstance(self.tag, Tag):
            object.__setattr__(self, "tag", Tag(str(self.tag)))


@dataclass(frozen=True)
class GrantAbility:
    """在 Effect 有效期间授予一个 Ability。"""

    id: StableId
    ability_id: StableId

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="operation id"))
        object.__setattr__(self, "ability_id", stable_id(self.ability_id, field="ability id"))


@dataclass(frozen=True)
class GrantTrigger:
    """在 Effect 有效期间授予一个 Trigger。"""

    id: StableId
    trigger_id: StableId

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="operation id"))
        object.__setattr__(self, "trigger_id", stable_id(self.trigger_id, field="trigger id"))


@dataclass(frozen=True)
class GrantInterceptor:
    """在 Effect 有效期间授予一个伤害干预器。"""

    id: StableId
    interceptor_id: StableId

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="operation id"))
        object.__setattr__(
            self,
            "interceptor_id",
            stable_id(self.interceptor_id, field="interceptor id"),
        )


@dataclass(frozen=True)
class GrantTargetConstraint:
    """在 Effect 有效期间授予一个目标约束。"""

    id: StableId
    constraint_id: StableId

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="operation id"))
        object.__setattr__(
            self,
            "constraint_id",
            stable_id(self.constraint_id, field="target constraint id"),
        )


class EffectOperation(Protocol):
    """自定义 Effect 原子操作必须携带稳定 id。"""

    id: StableId


@dataclass(frozen=True)
class ChooseOne:
    """按确定性随机源从多个操作分支中选择一个执行。"""

    id: StableId
    branches: tuple[tuple[EffectOperation, ...], ...]
    weights: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="operation id"))
        if len(self.branches) < 2 or any(not branch for branch in self.branches):
            raise ValueError("ChooseOne 至少需要两个非空分支")
        weights = self.weights or tuple(1 for _ in self.branches)
        if len(weights) != len(self.branches) or any(value < 1 for value in weights):
            raise ValueError("ChooseOne.weights 必须与分支数量一致且全部大于 0")
        object.__setattr__(self, "weights", tuple(int(value) for value in weights))


@dataclass(frozen=True)
class EffectDefinition:
    """Effect 的静态定义。

    ``duration_turns=0`` 表示瞬时，``None`` 表示永久，大于零表示持续回合。
    """

    id: StableId
    tags: TagSet = EMPTY_TAGS
    required_target_tags: TagSet = EMPTY_TAGS
    blocked_target_tags: TagSet = EMPTY_TAGS
    conditions: tuple[RuleCondition, ...] = ()
    operations: tuple[EffectOperation, ...] = ()
    duration_turns: int | None = 0
    stacking: StackingPolicy = StackingPolicy.REPLACE
    max_stacks: int = 1
    stack_by_source: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="effect id"))
        if self.duration_turns is not None and self.duration_turns < 0:
            raise ValueError(f"Effect {self.id} 的 duration_turns 不能小于 0")
        if self.max_stacks < 1:
            raise ValueError(f"Effect {self.id} 的 max_stacks 必须大于 0")
        if self.stacking is not StackingPolicy.STACK and self.max_stacks != 1:
            raise ValueError(f"Effect {self.id} 只有 STACK 策略可以设置多层")


@dataclass(frozen=True)
class EffectSpec:
    """一次 Effect 施加请求。"""

    instance_id: str
    definition_id: StableId
    source_id: str
    parameters: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.instance_id.strip():
            raise ValueError("EffectSpec 缺少 instance_id")
        if not self.source_id.strip():
            raise ValueError("EffectSpec 缺少 source_id")
        object.__setattr__(self, "definition_id", stable_id(self.definition_id, field="effect id"))
        object.__setattr__(
            self,
            "parameters",
            MappingProxyType({str(key): float(value) for key, value in self.parameters.items()}),
        )


@dataclass(frozen=True)
class EffectContribution:
    """一个原子操作对本次 Effect 的贡献。"""

    modifiers: tuple[AttributeModifier, ...] = ()
    resource_deltas: Mapping[StableId, float] = field(default_factory=dict)
    source_resource_deltas: Mapping[StableId, float] = field(default_factory=dict)
    granted_tags: TagSet = EMPTY_TAGS
    granted_abilities: frozenset[StableId] = frozenset()
    granted_triggers: frozenset[StableId] = frozenset()
    granted_interceptors: frozenset[StableId] = frozenset()
    granted_target_constraints: frozenset[StableId] = frozenset()
    facts: tuple["EffectFact", ...] = ()
    mutations: tuple["EffectMutation", ...] = ()
    cooldown_mutations: tuple["CooldownMutation", ...] = ()
    duration_override: int = 0


@dataclass(frozen=True)
class EffectMutation:
    operation_id: StableId
    kind: str
    effect_id: StableId | None = None
    required_tags: TagSet = EMPTY_TAGS
    blocked_tags: TagSet = EMPTY_TAGS
    maximum: int | None = None
    stacks: int = 0
    turns: int = 0
    source_only: bool = False


@dataclass(frozen=True)
class CooldownMutation:
    operation_id: StableId
    ability_id: StableId
    turns: int = 0
    set_to: int | None = None


@dataclass(frozen=True)
class EffectFact:
    """原子操作产生的结构化事实，由 EffectEngine 补齐审计上下文。"""

    kind: StableId
    subject_id: StableId
    values: Mapping[str, object] = field(default_factory=dict)
    source_id: str | None = None
    target_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", stable_id(self.kind, field="event kind"))
        object.__setattr__(self, "subject_id", stable_id(self.subject_id, field="event subject id"))
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))
        if self.source_id is not None and not self.source_id.strip():
            raise ValueError("EffectFact.source_id 不能为空字符串")
        if self.target_id is not None and not self.target_id.strip():
            raise ValueError("EffectFact.target_id 不能为空字符串")


@dataclass(frozen=True)
class EffectOperationContext:
    spec: EffectSpec
    source: RuleEntity
    target: RuleEntity
    magnitude_context: MagnitudeContext
    magnitudes: MagnitudeEvaluators
    resources: Mapping[StableId, ResourceDefinition]
    rule: RuleContext


OperationT = TypeVar("OperationT")
OperationHandler = Callable[[object, EffectOperationContext], EffectContribution]
OperationValidator = Callable[[object, "RuleReferences"], None]


@dataclass(frozen=True)
class RuleReferences:
    """启动校验时允许原子操作引用的规则键集合。"""

    attributes: frozenset[StableId]
    resources: frozenset[StableId]
    abilities: frozenset[StableId]
    triggers: frozenset[StableId]
    effects: frozenset[StableId] = frozenset()
    interceptors: frozenset[StableId] = frozenset()
    target_constraints: frozenset[StableId] = frozenset()


class EffectOperationHandlers:
    """Effect 原子操作处理器注册表。"""

    def __init__(self) -> None:
        self._handlers: dict[type, OperationHandler] = {}
        self._validators: dict[type, OperationValidator] = {}

    def register(
        self,
        operation_type: type[OperationT],
        handler: Callable[[OperationT, EffectOperationContext], EffectContribution],
        validator: Callable[[OperationT, RuleReferences], None] | None = None,
    ) -> None:
        if operation_type in self._handlers:
            raise ValueError(f"Effect 操作处理器重复：{operation_type.__name__}")
        self._handlers[operation_type] = handler  # type: ignore[assignment]
        if validator:
            self._validators[operation_type] = validator  # type: ignore[assignment]

    def execute(self, operation: object, context: EffectOperationContext) -> EffectContribution:
        try:
            handler = self._handlers[type(operation)]
        except KeyError as exc:
            raise TypeError(f"未注册 Effect 操作处理器：{type(operation).__name__}") from exc
        return handler(operation, context)

    def validate(self, operation: object, references: RuleReferences) -> None:
        stable_id(getattr(operation, "id", ""), field="operation id")
        if type(operation) not in self._handlers:
            raise TypeError(f"未注册 Effect 操作处理器：{type(operation).__name__}")
        validator = self._validators.get(type(operation))
        if validator:
            validator(operation, references)

    @classmethod
    def with_defaults(cls) -> "EffectOperationHandlers":
        result = cls()
        result.register(ModifyAttribute, _modify_attribute, _validate_attribute_operation)
        result.register(ChangeResource, _change_resource, _validate_resource_operation)
        result.register(TransferResource, _transfer_resource, _validate_resource_operation)
        result.register(DispelEffects, _dispel_effects, _validate_effect_selector_operation)
        result.register(
            ConsumeEffectStacks,
            _consume_effect_stacks,
            _validate_effect_selector_operation,
        )
        result.register(
            ModifyEffectDuration,
            _modify_effect_duration,
            _validate_effect_selector_operation,
        )
        result.register(ModifyCooldown, _modify_cooldown, _validate_cooldown_operation)
        result.register(ModifyCurrentCooldowns, _modify_current_cooldowns)
        result.register(GrantTag, _grant_tag)
        result.register(GrantAbility, _grant_ability, _validate_ability_operation)
        result.register(GrantTrigger, _grant_trigger, _validate_trigger_operation)
        result.register(GrantInterceptor, _grant_interceptor, _validate_interceptor_operation)
        result.register(
            GrantTargetConstraint,
            _grant_target_constraint,
            _validate_target_constraint_operation,
        )
        result.register(
            ChooseOne,
            lambda operation, context: _choose_one(operation, context, result),
        )
        return result


@dataclass(frozen=True)
class EffectResult:
    target: RuleEntity
    events: tuple[RuleEvent, ...]
    source: RuleEntity | None = None


class EffectEngine:
    """把 EffectDefinition 应用到规则实体。"""

    def __init__(
        self,
        definitions: DefinitionRegistry[EffectDefinition],
        attributes: AttributeResolver,
        resources: Mapping[StableId, ResourceDefinition],
        *,
        magnitudes: MagnitudeEvaluators | None = None,
        operations: EffectOperationHandlers | None = None,
        conditions: ConditionEngine | None = None,
    ) -> None:
        self.definitions = definitions
        self.attributes = attributes
        self.resources = dict(resources)
        self.magnitudes = magnitudes or MagnitudeEvaluators.with_defaults()
        self.operations = operations or EffectOperationHandlers.with_defaults()
        self.conditions = conditions or ConditionEngine()
        for key, definition in self.resources.items():
            if key != definition.id:
                raise ValueError(f"资源定义映射键与 id 不一致：{key} != {definition.id}")

    def finalize(
        self,
        ability_ids: frozenset[StableId] = frozenset(),
        trigger_ids: frozenset[StableId] = frozenset(),
        interceptor_ids: frozenset[StableId] = frozenset(),
        target_constraint_ids: frozenset[StableId] = frozenset(),
    ) -> None:
        """校验所有定义引用并冻结 Effect 注册表。"""

        references = RuleReferences(
            attributes=frozenset(self.attributes.definitions),
            resources=frozenset(self.resources),
            abilities=ability_ids,
            triggers=trigger_ids,
            effects=frozenset(self.definitions.ids()),
            interceptors=interceptor_ids,
            target_constraints=target_constraint_ids,
        )
        condition_references = ConditionReferences(
            attributes=references.attributes,
            resources=references.resources,
            effects=frozenset(self.definitions.ids()),
        )
        for resource in self.resources.values():
            if resource.maximum_attribute and resource.maximum_attribute not in references.attributes:
                raise KeyError(
                    f"资源 {resource.id} 引用了未知上限属性：{resource.maximum_attribute}"
                )
        for definition in self.definitions:
            self.conditions.validate(definition.conditions, condition_references)
            for operation in definition.operations:
                for nested in _walk_operations(operation):
                    self.operations.validate(nested, references)
                    magnitude = getattr(nested, "magnitude", None)
                    if magnitude is not None:
                        self.magnitudes.validate(
                            magnitude,
                            references.attributes,
                            references.resources,
                        )
                    if definition.duration_turns == 0 and isinstance(
                        nested,
                        (
                            ModifyAttribute,
                            GrantTag,
                            GrantAbility,
                            GrantTrigger,
                            GrantInterceptor,
                            GrantTargetConstraint,
                        ),
                    ):
                        raise ValueError(
                            f"瞬时 Effect {definition.id} 不能包含持续型操作：{nested.id}"
                        )
        self.definitions.freeze()

    def apply(
        self,
        spec: EffectSpec,
        *,
        source: RuleEntity,
        target: RuleEntity,
        context: RuleContext,
        event: RuleEvent | None = None,
    ) -> EffectResult:
        definition = self.definitions.require(spec.definition_id)
        target_tags = target.tags.merged(context.effective_tags)
        if not target_tags.allows(
            required=definition.required_target_tags,
            blocked=definition.blocked_target_tags,
        ):
            raise RuleViolation(
                "effect.target_blocked",
                f"目标 {target.id} 不满足 Effect {definition.id} 的标签条件",
                {"effect_id": definition.id, "target_id": target.id},
            )
        condition_context = ConditionContext(source, target, self.attributes, context, event)
        failed_conditions = self.conditions.failed(definition.conditions, condition_context)
        if failed_conditions:
            raise RuleViolation(
                "effect.condition_failed",
                f"目标 {target.id} 不满足 Effect {definition.id} 的执行条件",
                {"effect_id": definition.id, "conditions": failed_conditions},
            )

        source_snapshot = source.snapshot(self.attributes)
        target_snapshot = target.snapshot(self.attributes)
        operation_context = EffectOperationContext(
            spec=spec,
            source=source,
            target=target,
            magnitude_context=MagnitudeContext(
                source_snapshot,
                target_snapshot,
                spec.parameters,
                source.resources,
                target.resources,
                _effect_stacks(source),
                _effect_stacks(target),
            ),
            magnitudes=self.magnitudes,
            resources=self.resources,
            rule=context,
        )
        contributions = tuple(
            self.operations.execute(operation, operation_context) for operation in definition.operations
        )
        modifiers = tuple(modifier for contribution in contributions for modifier in contribution.modifiers)
        tags = EMPTY_TAGS.merged(*(contribution.granted_tags for contribution in contributions))
        abilities = frozenset(
            ability for contribution in contributions for ability in contribution.granted_abilities
        )
        triggers = frozenset(
            trigger for contribution in contributions for trigger in contribution.granted_triggers
        )
        interceptors = frozenset(
            interceptor
            for contribution in contributions
            for interceptor in contribution.granted_interceptors
        )
        target_constraints = frozenset(
            constraint
            for contribution in contributions
            for constraint in contribution.granted_target_constraints
        )
        facts = tuple(fact for contribution in contributions for fact in contribution.facts)
        mutations = tuple(
            mutation for contribution in contributions for mutation in contribution.mutations
        )
        cooldown_mutations = tuple(
            mutation
            for contribution in contributions
            for mutation in contribution.cooldown_mutations
        )
        duration_overrides = {
            contribution.duration_override
            for contribution in contributions
            if contribution.duration_override
        }
        if len(duration_overrides) > 1:
            raise ValueError(f"Effect {definition.id} 的持续时间覆盖发生冲突")
        duration_turns = (
            next(iter(duration_overrides))
            if duration_overrides
            else definition.duration_turns
        )
        deltas: dict[StableId, float] = {}
        source_deltas: dict[StableId, float] = {}
        for contribution in contributions:
            for key, value in contribution.resource_deltas.items():
                deltas[key] = deltas.get(key, 0.0) + float(value)
            for key, value in contribution.source_resource_deltas.items():
                source_deltas[key] = source_deltas.get(key, 0.0) + float(value)

        updated = target
        updated, mutation_events = self._apply_effect_mutations(
            updated,
            mutations,
            spec,
            context,
        )
        has_persistent = bool(
            duration_turns != 0
            or modifiers
            or tags.values
            or abilities
            or triggers
            or interceptors
            or target_constraints
        )
        if duration_turns == 0 and has_persistent:
            raise ValueError(f"瞬时 Effect {definition.id} 不能包含持续型属性、标签或能力操作")
        if duration_turns != 0 and has_persistent:
            active = ActiveEffect(
                instance_id=spec.instance_id,
                definition_id=definition.id,
                source_id=spec.source_id,
                modifiers=modifiers,
                granted_tags=tags,
                granted_abilities=abilities,
                granted_triggers=triggers,
                granted_interceptors=interceptors,
                granted_target_constraints=target_constraints,
                remaining_turns=duration_turns,
                parameters=spec.parameters,
            )
            updated = self._merge_active_effect(updated, active, definition)
        updated, cooldown_events = self._apply_cooldown_mutations(
            updated,
            cooldown_mutations,
            spec,
            context,
        )
        updated_snapshot = updated.snapshot(self.attributes)
        if source.id == target.id:
            combined = dict(deltas)
            for key, value in source_deltas.items():
                combined[key] = combined.get(key, 0.0) + value
            updated, applied_deltas = self._apply_resource_deltas(
                updated,
                combined,
                updated_snapshot,
            )
            updated_source = updated
            applied_source_deltas: Mapping[StableId, float] = MappingProxyType({})
            source_deltas = {}
            deltas = combined
        else:
            updated, applied_deltas = self._apply_resource_deltas(
                updated,
                deltas,
                updated_snapshot,
            )
            source_snapshot_after = source.snapshot(self.attributes)
            updated_source, applied_source_deltas = self._apply_resource_deltas(
                source,
                source_deltas,
                source_snapshot_after,
            )

        events = [
            RuleEvent.from_context(
                context,
                kind="effect.applied",
                source_id=spec.source_id,
                target_id=target.id,
                subject_id=definition.id,
                values={"instance_id": spec.instance_id, "stacks": self._effect_stacks(updated, definition.id)},
                phase=context.phase,
            )
        ]
        events.extend(mutation_events)
        events.extend(cooldown_events)
        for key, delta in sorted(applied_deltas.items()):
            events.append(
                RuleEvent.from_context(
                    context,
                    kind="resource.changed",
                    source_id=spec.source_id,
                    target_id=target.id,
                    subject_id=key,
                    values={
                        "delta": delta,
                        "requested_delta": deltas[key],
                        "current": updated.resources[key],
                    },
                    phase=context.phase,
                )
            )
        for key, delta in sorted(applied_source_deltas.items()):
            events.append(
                RuleEvent.from_context(
                    context,
                    kind="resource.changed",
                    source_id=spec.source_id,
                    target_id=source.id,
                    subject_id=key,
                    values={
                        "delta": delta,
                        "requested_delta": source_deltas[key],
                        "current": updated_source.resources[key],
                    },
                    phase=context.phase,
                )
            )
        events.extend(
            RuleEvent.from_context(
                context,
                kind=fact.kind,
                source_id=fact.source_id or spec.source_id,
                target_id=fact.target_id or target.id,
                subject_id=fact.subject_id,
                values=fact.values,
                phase=context.phase,
            )
            for fact in facts
        )
        return EffectResult(updated, tuple(events), updated_source)

    def apply_or_reject(
        self,
        spec: EffectSpec,
        *,
        source: RuleEntity,
        target: RuleEntity,
        context: RuleContext,
        event: RuleEvent | None = None,
    ) -> EffectResult:
        """在战斗流水中把动态目标拒绝转换为结构化事实。"""

        try:
            return self.apply(
                spec,
                source=source,
                target=target,
                context=context,
                event=event,
            )
        except RuleViolation as exc:
            reason = _APPLICATION_REJECTION_REASONS.get(str(exc.failure.code))
            if reason is None:
                raise
            values: dict[str, object] = {
                "reason": reason,
                "failure_code": str(exc.failure.code),
            }
            conditions = exc.failure.details.get("conditions")
            if conditions:
                values["conditions"] = tuple(str(value) for value in conditions)
            rejected = RuleEvent.from_context(
                context,
                kind="effect.application.rejected",
                source_id=spec.source_id,
                target_id=target.id,
                subject_id=spec.definition_id,
                values=values,
                phase=context.phase,
            )
            return EffectResult(target, (rejected,), source)

    def advance_turn(self, target: RuleEntity, context: RuleContext) -> EffectResult:
        """推进实体一回合，并为到期效果和冷却结束产生事实。"""

        expiring = tuple(
            effect for effect in target.active_effects if effect.remaining_turns == 1
        )
        ready = tuple(key for key, value in target.cooldowns.items() if value == 1)
        updated = target.advance_turn()
        events = [
            RuleEvent.from_context(
                context,
                kind="effect.expired",
                source_id=effect.source_id,
                target_id=target.id,
                subject_id=effect.definition_id,
                values={"instance_id": effect.instance_id},
                phase=ExecutionPhase.TURN_END,
            )
            for effect in expiring
        ]
        events.extend(
            RuleEvent.from_context(
                context,
                kind="ability.ready",
                source_id=target.id,
                target_id=target.id,
                subject_id=ability_id,
                phase=ExecutionPhase.TURN_END,
            )
            for ability_id in ready
        )
        return EffectResult(updated, tuple(events))

    def _apply_resource_deltas(
        self,
        target: RuleEntity,
        deltas: Mapping[StableId, float],
        attributes,
    ) -> tuple[RuleEntity, Mapping[StableId, float]]:
        if not deltas:
            return target, MappingProxyType({})
        resources = dict(target.resources)
        applied: dict[StableId, float] = {}
        for key, delta in deltas.items():
            try:
                definition = self.resources[key]
            except KeyError as exc:
                raise KeyError(f"Effect 修改了未知资源：{key}") from exc
            current = resources.get(key, definition.minimum)
            resources[key] = definition.clamp(current + delta, attributes)
            applied[key] = resources[key] - current
        return target.replace_resources(resources), MappingProxyType(applied)

    def _apply_effect_mutations(
        self,
        target: RuleEntity,
        mutations: tuple[EffectMutation, ...],
        spec: EffectSpec,
        context: RuleContext,
    ) -> tuple[RuleEntity, tuple[RuleEvent, ...]]:
        if not mutations:
            return target, ()
        effects = list(target.active_effects)
        events: list[RuleEvent] = []
        for mutation in mutations:
            matched = [
                effect
                for effect in effects
                if self._matches_effect_mutation(effect, mutation, spec.source_id)
            ]
            if mutation.maximum is not None:
                matched = matched[: mutation.maximum]
            if mutation.kind == "remove":
                for effect in matched:
                    effects.remove(effect)
                    events.append(
                        self._effect_mutation_event(
                            context,
                            spec,
                            target,
                            effect,
                            "effect.removed",
                            mutation,
                            {"removed_stacks": effect.stacks},
                        )
                    )
            elif mutation.kind == "consume_stacks":
                remaining = mutation.stacks
                for effect in matched:
                    if remaining <= 0:
                        break
                    consumed = min(remaining, effect.stacks)
                    remaining -= consumed
                    if consumed == effect.stacks:
                        effects.remove(effect)
                        events.append(
                            self._effect_mutation_event(
                                context,
                                spec,
                                target,
                                effect,
                                "effect.removed",
                                mutation,
                                {"removed_stacks": consumed},
                            )
                        )
                        continue
                    removed_modifiers = sum(effect.modifier_counts[-consumed:])
                    modifiers = (
                        effect.modifiers[:-removed_modifiers]
                        if removed_modifiers
                        else effect.modifiers
                    )
                    changed = replace(
                        effect,
                        modifiers=modifiers,
                        stacks=effect.stacks - consumed,
                        modifier_counts=effect.modifier_counts[:-consumed],
                    )
                    effects[effects.index(effect)] = changed
                    events.append(
                        self._effect_mutation_event(
                            context,
                            spec,
                            target,
                            changed,
                            "effect.stacks_changed",
                            mutation,
                            {"delta": -consumed, "stacks": changed.stacks},
                        )
                    )
            elif mutation.kind == "duration":
                for effect in matched:
                    if effect.remaining_turns is None:
                        continue
                    remaining_turns = effect.remaining_turns + mutation.turns
                    if remaining_turns <= 0:
                        effects.remove(effect)
                        events.append(
                            self._effect_mutation_event(
                                context,
                                spec,
                                target,
                                effect,
                                "effect.removed",
                                mutation,
                                {"reason": "duration_reduced"},
                            )
                        )
                        continue
                    changed = replace(effect, remaining_turns=remaining_turns)
                    effects[effects.index(effect)] = changed
                    events.append(
                        self._effect_mutation_event(
                            context,
                            spec,
                            target,
                            changed,
                            "effect.duration_changed",
                            mutation,
                            {"delta": mutation.turns, "remaining_turns": remaining_turns},
                        )
                    )
            else:
                raise ValueError(f"未知 EffectMutation.kind：{mutation.kind}")
        if tuple(effects) == target.active_effects:
            return target, tuple(events)
        return target.replace_effects(tuple(effects)), tuple(events)

    def _matches_effect_mutation(
        self,
        effect: ActiveEffect,
        mutation: EffectMutation,
        source_id: str,
    ) -> bool:
        if mutation.effect_id and effect.definition_id != mutation.effect_id:
            return False
        if mutation.source_only and effect.source_id != source_id:
            return False
        definition = self.definitions.require(effect.definition_id)
        return definition.tags.allows(
            required=mutation.required_tags,
            blocked=mutation.blocked_tags,
        )

    @staticmethod
    def _effect_mutation_event(
        context: RuleContext,
        spec: EffectSpec,
        target: RuleEntity,
        effect: ActiveEffect,
        kind: StableId,
        mutation: EffectMutation,
        values: Mapping[str, object],
    ) -> RuleEvent:
        return RuleEvent.from_context(
            context,
            kind=kind,
            source_id=spec.source_id,
            target_id=target.id,
            subject_id=effect.definition_id,
            values={
                "instance_id": effect.instance_id,
                "operation_id": mutation.operation_id,
                **values,
            },
            phase=context.phase,
        )

    @staticmethod
    def _apply_cooldown_mutations(
        target: RuleEntity,
        mutations: tuple[CooldownMutation, ...],
        spec: EffectSpec,
        context: RuleContext,
    ) -> tuple[RuleEntity, tuple[RuleEvent, ...]]:
        if not mutations:
            return target, ()
        cooldowns = dict(target.cooldowns)
        events: list[RuleEvent] = []
        for mutation in mutations:
            before = cooldowns.get(mutation.ability_id, 0)
            after = mutation.set_to if mutation.set_to is not None else before + mutation.turns
            after = max(0, after)
            if after:
                cooldowns[mutation.ability_id] = after
            else:
                cooldowns.pop(mutation.ability_id, None)
            if after == before:
                continue
            events.append(
                RuleEvent.from_context(
                    context,
                    kind="ability.cooldown_changed",
                    source_id=spec.source_id,
                    target_id=target.id,
                    subject_id=mutation.ability_id,
                    values={
                        "operation_id": mutation.operation_id,
                        "before": before,
                        "after": after,
                        "delta": after - before,
                    },
                    phase=context.phase,
                )
            )
        if cooldowns == dict(target.cooldowns):
            return target, tuple(events)
        return target.replace_cooldowns(cooldowns), tuple(events)

    @staticmethod
    def _merge_active_effect(
        target: RuleEntity,
        incoming: ActiveEffect,
        definition: EffectDefinition,
    ) -> RuleEntity:
        def matches(effect: ActiveEffect) -> bool:
            if effect.definition_id != definition.id:
                return False
            return not definition.stack_by_source or effect.source_id == incoming.source_id

        existing = [effect for effect in target.active_effects if matches(effect)]
        other = [effect for effect in target.active_effects if not matches(effect)]
        if definition.stacking is StackingPolicy.INDEPENDENT or not existing:
            return target.replace_effects(tuple((*target.active_effects, incoming)))

        current = existing[0]
        if definition.stacking is StackingPolicy.REPLACE:
            merged = incoming
        elif definition.stacking is StackingPolicy.REFRESH:
            merged = replace(incoming, stacks=current.stacks)
        else:
            if current.stacks >= definition.max_stacks:
                merged = replace(current, remaining_turns=incoming.remaining_turns)
            else:
                merged = ActiveEffect(
                    instance_id=current.instance_id,
                    definition_id=current.definition_id,
                    source_id=current.source_id,
                    modifiers=current.modifiers + incoming.modifiers,
                    granted_tags=current.granted_tags.merged(incoming.granted_tags),
                    granted_abilities=current.granted_abilities | incoming.granted_abilities,
                    granted_triggers=current.granted_triggers | incoming.granted_triggers,
                    granted_interceptors=(
                        current.granted_interceptors | incoming.granted_interceptors
                    ),
                    granted_target_constraints=(
                        current.granted_target_constraints
                        | incoming.granted_target_constraints
                    ),
                    remaining_turns=incoming.remaining_turns,
                    stacks=current.stacks + 1,
                    modifier_counts=current.modifier_counts + incoming.modifier_counts,
                    parameters=incoming.parameters,
                )
        return target.replace_effects(tuple((*other, merged)))

    @staticmethod
    def _effect_stacks(target: RuleEntity, definition_id: StableId) -> int:
        return sum(effect.stacks for effect in target.active_effects if effect.definition_id == definition_id)


def _modify_attribute(operation: ModifyAttribute, context: EffectOperationContext) -> EffectContribution:
    value = context.magnitudes.evaluate(operation.magnitude, context.magnitude_context)
    modifier = AttributeModifier(
        id=f"{context.spec.instance_id}:{operation.id}",
        attribute_id=operation.attribute_id,
        layer=operation.layer,
        value=value,
        source_id=context.spec.source_id,
        required_tags=operation.required_tags,
        blocked_tags=operation.blocked_tags,
        priority=operation.priority,
    )
    return EffectContribution(modifiers=(modifier,))


def _change_resource(operation: ChangeResource, context: EffectOperationContext) -> EffectContribution:
    value = context.magnitudes.evaluate(operation.magnitude, context.magnitude_context)
    return EffectContribution(resource_deltas={operation.resource_id: value})


def _transfer_resource(
    operation: TransferResource,
    context: EffectOperationContext,
) -> EffectContribution:
    requested = max(0.0, context.magnitudes.evaluate(operation.magnitude, context.magnitude_context))
    definition = context.resources[operation.resource_id]
    current = context.target.resources.get(operation.resource_id, definition.minimum)
    transferred = min(requested, max(0.0, current - definition.minimum))
    source_current = context.source.resources.get(operation.resource_id, definition.minimum)
    source_maximum = definition.fixed_maximum
    if definition.maximum_attribute:
        source_maximum = context.magnitude_context.source_attributes.value(
            definition.maximum_attribute
        )
    source_capacity = (
        transferred * operation.efficiency
        if source_maximum is None
        else max(0.0, source_maximum - source_current)
    )
    received = min(transferred * operation.efficiency, source_capacity)
    return EffectContribution(
        resource_deltas={operation.resource_id: -transferred},
        source_resource_deltas={operation.resource_id: received},
        facts=(
            EffectFact(
                "resource.transferred",
                operation.resource_id,
                {
                    "operation_id": operation.id,
                    "requested": requested,
                    "drained": transferred,
                    "received": received,
                    "overflow": transferred * operation.efficiency - received,
                    "efficiency": operation.efficiency,
                },
            ),
        ),
    )


def _effect_stacks(entity: RuleEntity) -> Mapping[StableId, int]:
    totals: dict[StableId, int] = {}
    for effect in entity.active_effects:
        totals[effect.definition_id] = totals.get(effect.definition_id, 0) + effect.stacks
    return totals


def _dispel_effects(
    operation: DispelEffects,
    _context: EffectOperationContext,
) -> EffectContribution:
    return EffectContribution(
        mutations=(
            EffectMutation(
                operation.id,
                "remove",
                operation.effect_id,
                operation.required_tags,
                operation.blocked_tags,
                operation.maximum,
                source_only=operation.source_only,
            ),
        )
    )


def _consume_effect_stacks(
    operation: ConsumeEffectStacks,
    _context: EffectOperationContext,
) -> EffectContribution:
    return EffectContribution(
        mutations=(
            EffectMutation(
                operation.id,
                "consume_stacks",
                operation.effect_id,
                stacks=operation.stacks,
                source_only=operation.source_only,
            ),
        )
    )


def _modify_effect_duration(
    operation: ModifyEffectDuration,
    _context: EffectOperationContext,
) -> EffectContribution:
    return EffectContribution(
        mutations=(
            EffectMutation(
                operation.id,
                "duration",
                operation.effect_id,
                turns=operation.turns,
                source_only=operation.source_only,
            ),
        )
    )


def _modify_cooldown(
    operation: ModifyCooldown,
    _context: EffectOperationContext,
) -> EffectContribution:
    return EffectContribution(
        cooldown_mutations=(
            CooldownMutation(
                operation.id,
                operation.ability_id,
                operation.turns,
                operation.set_to,
            ),
        )
    )


def _modify_current_cooldowns(
    operation: ModifyCurrentCooldowns,
    context: EffectOperationContext,
) -> EffectContribution:
    cooldowns = context.target.cooldowns
    if not cooldowns:
        return EffectContribution()
    ability_ids = tuple(sorted(cooldowns))
    if operation.selection == "longest":
        longest = max(cooldowns.values())
        ability_ids = (next(value for value in ability_ids if cooldowns[value] == longest),)
    return EffectContribution(
        cooldown_mutations=tuple(
            CooldownMutation(operation.id, ability_id, turns=operation.turns)
            for ability_id in ability_ids
        )
    )


def _grant_tag(operation: GrantTag, _context: EffectOperationContext) -> EffectContribution:
    return EffectContribution(granted_tags=TagSet.of(operation.tag))


def _grant_ability(operation: GrantAbility, _context: EffectOperationContext) -> EffectContribution:
    return EffectContribution(granted_abilities=frozenset({operation.ability_id}))


def _grant_trigger(operation: GrantTrigger, _context: EffectOperationContext) -> EffectContribution:
    return EffectContribution(granted_triggers=frozenset({operation.trigger_id}))


def _grant_interceptor(
    operation: GrantInterceptor,
    _context: EffectOperationContext,
) -> EffectContribution:
    return EffectContribution(granted_interceptors=frozenset({operation.interceptor_id}))


def _grant_target_constraint(
    operation: GrantTargetConstraint,
    _context: EffectOperationContext,
) -> EffectContribution:
    return EffectContribution(
        granted_target_constraints=frozenset({operation.constraint_id})
    )


def _choose_one(
    operation: ChooseOne,
    context: EffectOperationContext,
    handlers: EffectOperationHandlers,
) -> EffectContribution:
    ticket = context.rule.random.randint(1, sum(operation.weights))
    selected = 0
    boundary = 0
    for index, weight in enumerate(operation.weights):
        boundary += weight
        if ticket <= boundary:
            selected = index
            break
    contributions = tuple(
        handlers.execute(nested, context)
        for nested in operation.branches[selected]
    )
    return _merge_contributions(
        contributions,
        extra_facts=(
            EffectFact(
                "effect.choice.selected",
                operation.id,
                {"branch": selected, "branches": len(operation.branches)},
            ),
        ),
    )


def _walk_operations(operation: object):
    yield operation
    if isinstance(operation, ChooseOne):
        for branch in operation.branches:
            for nested in branch:
                yield from _walk_operations(nested)


def _merge_contributions(
    contributions: tuple[EffectContribution, ...],
    *,
    extra_facts: tuple[EffectFact, ...] = (),
) -> EffectContribution:
    resource_deltas: dict[StableId, float] = {}
    source_resource_deltas: dict[StableId, float] = {}
    for contribution in contributions:
        for key, value in contribution.resource_deltas.items():
            resource_deltas[key] = resource_deltas.get(key, 0.0) + value
        for key, value in contribution.source_resource_deltas.items():
            source_resource_deltas[key] = source_resource_deltas.get(key, 0.0) + value
    duration_overrides = {
        contribution.duration_override
        for contribution in contributions
        if contribution.duration_override
    }
    if len(duration_overrides) > 1:
        raise ValueError("随机分支内的持续时间覆盖发生冲突")
    return EffectContribution(
        modifiers=tuple(value for item in contributions for value in item.modifiers),
        resource_deltas=resource_deltas,
        source_resource_deltas=source_resource_deltas,
        granted_tags=EMPTY_TAGS.merged(*(item.granted_tags for item in contributions)),
        granted_abilities=frozenset(value for item in contributions for value in item.granted_abilities),
        granted_triggers=frozenset(value for item in contributions for value in item.granted_triggers),
        granted_interceptors=frozenset(value for item in contributions for value in item.granted_interceptors),
        granted_target_constraints=frozenset(
            value for item in contributions for value in item.granted_target_constraints
        ),
        facts=tuple(value for item in contributions for value in item.facts) + extra_facts,
        mutations=tuple(value for item in contributions for value in item.mutations),
        cooldown_mutations=tuple(
            value for item in contributions for value in item.cooldown_mutations
        ),
        duration_override=next(iter(duration_overrides), 0),
    )


def _validate_attribute_operation(operation: ModifyAttribute, references: RuleReferences) -> None:
    if operation.attribute_id not in references.attributes:
        raise KeyError(f"Effect 操作 {operation.id} 引用了未知属性：{operation.attribute_id}")


def _validate_resource_operation(
    operation: ChangeResource | TransferResource,
    references: RuleReferences,
) -> None:
    if operation.resource_id not in references.resources:
        raise KeyError(f"Effect 操作 {operation.id} 引用了未知资源：{operation.resource_id}")


def _validate_effect_selector_operation(
    operation: DispelEffects | ConsumeEffectStacks | ModifyEffectDuration,
    references: RuleReferences,
) -> None:
    effect_id = getattr(operation, "effect_id", None)
    if effect_id and effect_id not in references.effects:
        raise KeyError(f"Effect 操作 {operation.id} 引用了未知 Effect：{effect_id}")


def _validate_cooldown_operation(
    operation: ModifyCooldown,
    references: RuleReferences,
) -> None:
    if operation.ability_id not in references.abilities:
        raise KeyError(f"Effect 操作 {operation.id} 引用了未知 Ability：{operation.ability_id}")


def _validate_ability_operation(operation: GrantAbility, references: RuleReferences) -> None:
    if operation.ability_id not in references.abilities:
        raise KeyError(f"Effect 操作 {operation.id} 引用了未知 Ability：{operation.ability_id}")


def _validate_trigger_operation(operation: GrantTrigger, references: RuleReferences) -> None:
    if operation.trigger_id not in references.triggers:
        raise KeyError(f"Effect 操作 {operation.id} 引用了未知 Trigger：{operation.trigger_id}")


def _validate_interceptor_operation(
    operation: GrantInterceptor,
    references: RuleReferences,
) -> None:
    if operation.interceptor_id not in references.interceptors:
        raise KeyError(
            f"Effect 操作 {operation.id} 引用了未知伤害干预器：{operation.interceptor_id}"
        )


def _validate_target_constraint_operation(
    operation: GrantTargetConstraint,
    references: RuleReferences,
) -> None:
    if operation.constraint_id not in references.target_constraints:
        raise KeyError(
            f"Effect 操作 {operation.id} 引用了未知目标约束：{operation.constraint_id}"
        )


__all__ = [
    "ChooseOne",
    "ChangeResource",
    "ConsumeEffectStacks",
    "CooldownMutation",
    "DispelEffects",
    "EffectContribution",
    "EffectDefinition",
    "EffectEngine",
    "EffectFact",
    "EffectMutation",
    "EffectOperationContext",
    "EffectOperationHandlers",
    "EffectResult",
    "EffectSpec",
    "GrantAbility",
    "GrantInterceptor",
    "GrantTargetConstraint",
    "GrantTag",
    "GrantTrigger",
    "ModifyAttribute",
    "ModifyCooldown",
    "ModifyCurrentCooldowns",
    "ModifyEffectDuration",
    "RuleReferences",
    "StackingPolicy",
    "TransferResource",
]
