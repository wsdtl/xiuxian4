"""类型化规则条件与可扩展求值器。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Protocol, TypeVar

from .attributes import AttributeResolver
from .context import RuleContext
from .entity import RuleEntity
from .events import RuleEvent
from .ids import StableId, stable_id
from .tags import EMPTY_TAGS, TagSet


class ConditionSubject(str, Enum):
    SOURCE = "source"
    TARGET = "target"


class Comparison(str, Enum):
    EQUAL = "equal"
    NOT_EQUAL = "not_equal"
    LESS = "less"
    LESS_OR_EQUAL = "less_or_equal"
    GREATER = "greater"
    GREATER_OR_EQUAL = "greater_or_equal"

    def test(self, left: float | str, right: float | str) -> bool:
        if self is Comparison.EQUAL:
            return left == right
        if self is Comparison.NOT_EQUAL:
            return left != right
        if isinstance(left, str) or isinstance(right, str):
            raise TypeError(f"比较方式 {self.value} 不支持字符串大小比较")
        if self is Comparison.LESS:
            return left < right
        if self is Comparison.LESS_OR_EQUAL:
            return left <= right
        if self is Comparison.GREATER:
            return left > right
        return left >= right


@dataclass(frozen=True)
class TagCondition:
    id: StableId
    subject: ConditionSubject
    required: TagSet = EMPTY_TAGS
    blocked: TagSet = EMPTY_TAGS

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="condition id"))


@dataclass(frozen=True)
class AttributeCondition:
    id: StableId
    subject: ConditionSubject
    attribute_id: StableId
    comparison: Comparison
    value: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="condition id"))
        object.__setattr__(self, "attribute_id", stable_id(self.attribute_id, field="attribute id"))


@dataclass(frozen=True)
class ResourceRatioCondition:
    id: StableId
    subject: ConditionSubject
    resource_id: StableId
    maximum_attribute_id: StableId
    comparison: Comparison
    value: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="condition id"))
        object.__setattr__(self, "resource_id", stable_id(self.resource_id, field="resource id"))
        object.__setattr__(
            self,
            "maximum_attribute_id",
            stable_id(self.maximum_attribute_id, field="maximum attribute id"),
        )


@dataclass(frozen=True)
class EffectStacksCondition:
    id: StableId
    subject: ConditionSubject
    effect_id: StableId
    comparison: Comparison
    value: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="condition id"))
        object.__setattr__(self, "effect_id", stable_id(self.effect_id, field="effect id"))


@dataclass(frozen=True)
class EventValueCondition:
    id: StableId
    key: str
    comparison: Comparison
    value: float | str

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="condition id"))
        if not self.key.strip():
            raise ValueError("EventValueCondition 缺少事件字段 key")


class RuleCondition(Protocol):
    """自定义条件必须携带稳定 id，并注册对应处理器。"""

    id: StableId


@dataclass(frozen=True)
class ConditionContext:
    source: RuleEntity
    target: RuleEntity
    attributes: AttributeResolver
    rule: RuleContext
    event: RuleEvent | None = None

    def entity(self, subject: ConditionSubject) -> RuleEntity:
        return self.source if subject is ConditionSubject.SOURCE else self.target


ConditionT = TypeVar("ConditionT")
ConditionHandler = Callable[[object, ConditionContext], bool]
ConditionValidator = Callable[[object, "ConditionReferences"], None]


@dataclass(frozen=True)
class ConditionReferences:
    attributes: frozenset[StableId]
    resources: frozenset[StableId]
    effects: frozenset[StableId]


class ConditionHandlers:
    """规则条件处理器注册表。"""

    def __init__(self) -> None:
        self._handlers: dict[type, ConditionHandler] = {}
        self._validators: dict[type, ConditionValidator] = {}

    def register(
        self,
        condition_type: type[ConditionT],
        handler: Callable[[ConditionT, ConditionContext], bool],
        validator: Callable[[ConditionT, ConditionReferences], None] | None = None,
    ) -> None:
        if condition_type in self._handlers:
            raise ValueError(f"条件处理器重复：{condition_type.__name__}")
        self._handlers[condition_type] = handler  # type: ignore[assignment]
        if validator:
            self._validators[condition_type] = validator  # type: ignore[assignment]

    def evaluate(self, condition: object, context: ConditionContext) -> bool:
        try:
            handler = self._handlers[type(condition)]
        except KeyError as exc:
            raise TypeError(f"未注册条件处理器：{type(condition).__name__}") from exc
        return bool(handler(condition, context))

    def validate(self, condition: object, references: ConditionReferences) -> None:
        stable_id(getattr(condition, "id", ""), field="condition id")
        if type(condition) not in self._handlers:
            raise TypeError(f"未注册条件处理器：{type(condition).__name__}")
        validator = self._validators.get(type(condition))
        if validator:
            validator(condition, references)

    @classmethod
    def with_defaults(cls) -> "ConditionHandlers":
        result = cls()
        result.register(TagCondition, _tag_condition)
        result.register(AttributeCondition, _attribute_condition, _validate_attribute_condition)
        result.register(ResourceRatioCondition, _resource_ratio_condition, _validate_resource_ratio_condition)
        result.register(EffectStacksCondition, _effect_stacks_condition, _validate_effect_stacks_condition)
        result.register(EventValueCondition, _event_value_condition)
        return result


class ConditionEngine:
    """统一判断一组必须全部成立的条件。"""

    def __init__(self, handlers: ConditionHandlers | None = None) -> None:
        self.handlers = handlers or ConditionHandlers.with_defaults()

    def failed(
        self,
        conditions: tuple[RuleCondition, ...],
        context: ConditionContext,
    ) -> tuple[StableId, ...]:
        return tuple(
            condition.id
            for condition in conditions
            if not self.handlers.evaluate(condition, context)
        )

    def allows(self, conditions: tuple[RuleCondition, ...], context: ConditionContext) -> bool:
        return not self.failed(conditions, context)

    def validate(
        self,
        conditions: tuple[RuleCondition, ...],
        references: ConditionReferences,
    ) -> None:
        for condition in conditions:
            self.handlers.validate(condition, references)


def _tag_condition(condition: TagCondition, context: ConditionContext) -> bool:
    tags = context.entity(condition.subject).tags.merged(context.rule.effective_tags)
    return tags.allows(required=condition.required, blocked=condition.blocked)


def _attribute_condition(condition: AttributeCondition, context: ConditionContext) -> bool:
    entity = context.entity(condition.subject)
    value = entity.snapshot(context.attributes).value(condition.attribute_id)
    return condition.comparison.test(value, float(condition.value))


def _resource_ratio_condition(condition: ResourceRatioCondition, context: ConditionContext) -> bool:
    entity = context.entity(condition.subject)
    maximum = entity.snapshot(context.attributes).value(condition.maximum_attribute_id)
    current = float(entity.resources.get(condition.resource_id, 0.0))
    ratio = current / maximum if maximum > 0 else 0.0
    return condition.comparison.test(ratio, float(condition.value))


def _effect_stacks_condition(condition: EffectStacksCondition, context: ConditionContext) -> bool:
    entity = context.entity(condition.subject)
    stacks = sum(
        effect.stacks
        for effect in entity.active_effects
        if effect.definition_id == condition.effect_id
    )
    return condition.comparison.test(float(stacks), float(condition.value))


def _event_value_condition(condition: EventValueCondition, context: ConditionContext) -> bool:
    if context.event is None or condition.key not in context.event.values:
        return False
    actual = context.event.values[condition.key]
    if isinstance(condition.value, str):
        return condition.comparison.test(str(actual), condition.value)
    try:
        return condition.comparison.test(float(actual), float(condition.value))
    except (TypeError, ValueError):
        return False


def _validate_attribute_condition(
    condition: AttributeCondition,
    references: ConditionReferences,
) -> None:
    if condition.attribute_id not in references.attributes:
        raise KeyError(f"条件 {condition.id} 引用了未知属性：{condition.attribute_id}")


def _validate_resource_ratio_condition(
    condition: ResourceRatioCondition,
    references: ConditionReferences,
) -> None:
    if condition.resource_id not in references.resources:
        raise KeyError(f"条件 {condition.id} 引用了未知资源：{condition.resource_id}")
    if condition.maximum_attribute_id not in references.attributes:
        raise KeyError(
            f"条件 {condition.id} 引用了未知上限属性：{condition.maximum_attribute_id}"
        )


def _validate_effect_stacks_condition(
    condition: EffectStacksCondition,
    references: ConditionReferences,
) -> None:
    if condition.effect_id not in references.effects:
        raise KeyError(f"条件 {condition.id} 引用了未知 Effect：{condition.effect_id}")


__all__ = [
    "AttributeCondition",
    "Comparison",
    "ConditionContext",
    "ConditionEngine",
    "ConditionHandlers",
    "ConditionReferences",
    "ConditionSubject",
    "EffectStacksCondition",
    "EventValueCondition",
    "ResourceRatioCondition",
    "RuleCondition",
    "TagCondition",
]
