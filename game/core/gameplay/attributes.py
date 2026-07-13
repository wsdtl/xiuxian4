"""统一属性、数值来源和计算顺序。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Callable, Mapping, Protocol, TypeVar

from .ids import StableId, stable_id
from .tags import EMPTY_TAGS, TagSet


class ModifierLayer(str, Enum):
    """属性修改的固定计算层。"""

    LOCAL_FLAT = "local_flat"
    LOCAL_RATE = "local_rate"
    GLOBAL_FLAT = "global_flat"
    GLOBAL_RATE = "global_rate"
    FINAL_RATE = "final_rate"


@dataclass(frozen=True)
class AttributeDefinition:
    """一个可计算属性的边界定义。"""

    id: StableId
    default: float = 0.0
    minimum: float | None = None
    maximum: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="attribute id"))
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError(f"属性 {self.id} 的 minimum 不能大于 maximum")

    def clamp(self, value: float) -> float:
        result = float(value)
        if self.minimum is not None:
            result = max(float(self.minimum), result)
        if self.maximum is not None:
            result = min(float(self.maximum), result)
        return result


@dataclass(frozen=True)
class ResourceDefinition:
    """会被消耗或恢复的当前资源，例如当前血气和当前精神。"""

    id: StableId
    minimum: float = 0.0
    maximum_attribute: StableId | None = None
    fixed_maximum: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="resource id"))
        if self.maximum_attribute:
            object.__setattr__(
                self,
                "maximum_attribute",
                stable_id(self.maximum_attribute, field="maximum attribute id"),
            )
        if self.maximum_attribute and self.fixed_maximum is not None:
            raise ValueError(f"资源 {self.id} 不能同时使用 maximum_attribute 和 fixed_maximum")

    def clamp(self, value: float, attributes: "AttributeSnapshot") -> float:
        result = max(float(self.minimum), float(value))
        maximum = self.fixed_maximum
        if self.maximum_attribute:
            maximum = attributes.value(self.maximum_attribute)
        if maximum is not None:
            result = min(float(maximum), result)
        return result


class Magnitude(Protocol):
    """数值表达式标记协议；具体类型由求值器注册。"""


@dataclass(frozen=True)
class FixedMagnitude:
    """固定数值。"""

    value: float


@dataclass(frozen=True)
class AttributeMagnitude:
    """读取来源或目标属性后进行线性换算。"""

    attribute_id: StableId
    owner: str = "source"
    scale: float = 1.0
    offset: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "attribute_id", stable_id(self.attribute_id, field="magnitude attribute id"))
        if self.owner not in {"source", "target"}:
            raise ValueError("AttributeMagnitude.owner 只能是 source 或 target")


@dataclass(frozen=True)
class ParameterMagnitude:
    """读取 EffectSpec 参数，常用于把事件数值传入触发效果。"""

    key: str
    scale: float = 1.0
    offset: float = 0.0

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("ParameterMagnitude 缺少参数 key")


class ResourceValueMode(str, Enum):
    CURRENT = "current"
    MISSING = "missing"
    RATIO = "ratio"
    MISSING_RATIO = "missing_ratio"


@dataclass(frozen=True)
class ResourceMagnitude:
    """读取来源或目标的当前、缺失或比例资源。"""

    resource_id: StableId
    owner: str = "target"
    mode: ResourceValueMode = ResourceValueMode.CURRENT
    maximum_attribute_id: StableId | None = None
    scale: float = 1.0
    offset: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "resource_id", stable_id(self.resource_id, field="resource id"))
        if self.owner not in {"source", "target"}:
            raise ValueError("ResourceMagnitude.owner 只能是 source 或 target")
        if self.maximum_attribute_id:
            object.__setattr__(
                self,
                "maximum_attribute_id",
                stable_id(self.maximum_attribute_id, field="maximum attribute id"),
            )
        if self.mode is not ResourceValueMode.CURRENT and not self.maximum_attribute_id:
            raise ValueError(f"ResourceMagnitude.{self.mode.value} 需要 maximum_attribute_id")


@dataclass(frozen=True)
class SumMagnitude:
    terms: tuple[Magnitude, ...]

    def __post_init__(self) -> None:
        if not self.terms:
            raise ValueError("SumMagnitude.terms 不能为空")


@dataclass(frozen=True)
class ProductMagnitude:
    factors: tuple[Magnitude, ...]

    def __post_init__(self) -> None:
        if not self.factors:
            raise ValueError("ProductMagnitude.factors 不能为空")


@dataclass(frozen=True)
class MinimumMagnitude:
    values: tuple[Magnitude, ...]

    def __post_init__(self) -> None:
        if not self.values:
            raise ValueError("MinimumMagnitude.values 不能为空")


@dataclass(frozen=True)
class MaximumMagnitude:
    values: tuple[Magnitude, ...]

    def __post_init__(self) -> None:
        if not self.values:
            raise ValueError("MaximumMagnitude.values 不能为空")


@dataclass(frozen=True)
class ClampMagnitude:
    value: Magnitude
    minimum: Magnitude | None = None
    maximum: Magnitude | None = None

    def __post_init__(self) -> None:
        if self.minimum is None and self.maximum is None:
            raise ValueError("ClampMagnitude 至少需要一个边界")


@dataclass(frozen=True)
class RatioMagnitude:
    numerator: Magnitude
    denominator: Magnitude
    zero_default: float = 0.0


@dataclass(frozen=True)
class PowerMagnitude:
    value: Magnitude
    exponent: float


@dataclass(frozen=True)
class MagnitudeContext:
    source_attributes: "AttributeSnapshot"
    target_attributes: "AttributeSnapshot"
    parameters: Mapping[str, float] = field(default_factory=dict)
    source_resources: Mapping[StableId, float] = field(default_factory=dict)
    target_resources: Mapping[StableId, float] = field(default_factory=dict)


MagnitudeT = TypeVar("MagnitudeT")
MagnitudeEvaluator = Callable[[object, MagnitudeContext], float]
MagnitudeValidator = Callable[
    [object, frozenset[StableId], frozenset[StableId]],
    None,
]


class MagnitudeEvaluators:
    """数值表达式求值注册表。

    新公式类型只需新增一个 dataclass 和一个求值器，不需要修改 Effect 或
    Ability 执行器。
    """

    def __init__(self) -> None:
        self._evaluators: dict[type, MagnitudeEvaluator] = {}
        self._validators: dict[type, MagnitudeValidator] = {}

    def register(
        self,
        magnitude_type: type[MagnitudeT],
        evaluator: Callable[[MagnitudeT, MagnitudeContext], float],
        validator: Callable[
            [MagnitudeT, frozenset[StableId], frozenset[StableId]],
            None,
        ]
        | None = None,
    ) -> None:
        if magnitude_type in self._evaluators:
            raise ValueError(f"数值表达式求值器重复：{magnitude_type.__name__}")
        self._evaluators[magnitude_type] = evaluator  # type: ignore[assignment]
        if validator:
            self._validators[magnitude_type] = validator  # type: ignore[assignment]

    def evaluate(self, magnitude: Magnitude, context: MagnitudeContext) -> float:
        try:
            evaluator = self._evaluators[type(magnitude)]
        except KeyError as exc:
            raise TypeError(f"未注册数值表达式求值器：{type(magnitude).__name__}") from exc
        return float(evaluator(magnitude, context))

    def validate(
        self,
        magnitude: Magnitude,
        attributes: frozenset[StableId],
        resources: frozenset[StableId] = frozenset(),
    ) -> None:
        """启动时校验公式类型及其静态属性引用。"""

        if type(magnitude) not in self._evaluators:
            raise TypeError(f"未注册数值表达式求值器：{type(magnitude).__name__}")
        validator = self._validators.get(type(magnitude))
        if validator:
            validator(magnitude, attributes, resources)

    @classmethod
    def with_defaults(cls) -> "MagnitudeEvaluators":
        result = cls()
        result.register(FixedMagnitude, lambda value, _context: value.value)
        result.register(
            AttributeMagnitude,
            lambda value, context: (
                context.source_attributes if value.owner == "source" else context.target_attributes
            ).value(value.attribute_id)
            * value.scale
            + value.offset,
            _validate_attribute_magnitude,
        )
        result.register(
            ParameterMagnitude,
            lambda value, context: context.parameters.get(value.key, 0.0)
            * value.scale
            + value.offset,
        )
        result.register(ResourceMagnitude, _resource_magnitude, _validate_resource_magnitude)
        result.register(
            SumMagnitude,
            lambda value, context: sum(result.evaluate(term, context) for term in value.terms),
            lambda value, attributes, resources: _validate_nested(
                result,
                value.terms,
                attributes,
                resources,
            ),
        )
        result.register(
            ProductMagnitude,
            lambda value, context: _product_values(
                result.evaluate(factor, context) for factor in value.factors
            ),
            lambda value, attributes, resources: _validate_nested(
                result,
                value.factors,
                attributes,
                resources,
            ),
        )
        result.register(
            MinimumMagnitude,
            lambda value, context: min(result.evaluate(item, context) for item in value.values),
            lambda value, attributes, resources: _validate_nested(
                result,
                value.values,
                attributes,
                resources,
            ),
        )
        result.register(
            MaximumMagnitude,
            lambda value, context: max(result.evaluate(item, context) for item in value.values),
            lambda value, attributes, resources: _validate_nested(
                result,
                value.values,
                attributes,
                resources,
            ),
        )
        result.register(
            ClampMagnitude,
            lambda value, context: _clamp_magnitude(result, value, context),
            lambda value, attributes, resources: _validate_nested(
                result,
                tuple(
                    item
                    for item in (value.value, value.minimum, value.maximum)
                    if item is not None
                ),
                attributes,
                resources,
            ),
        )
        result.register(
            RatioMagnitude,
            lambda value, context: _ratio_magnitude(result, value, context),
            lambda value, attributes, resources: _validate_nested(
                result,
                (value.numerator, value.denominator),
                attributes,
                resources,
            ),
        )
        result.register(
            PowerMagnitude,
            lambda value, context: result.evaluate(value.value, context) ** value.exponent,
            lambda value, attributes, resources: result.validate(
                value.value,
                attributes,
                resources,
            ),
        )
        return result


def _validate_attribute_magnitude(
    magnitude: AttributeMagnitude,
    attributes: frozenset[StableId],
    _resources: frozenset[StableId],
) -> None:
    if magnitude.attribute_id not in attributes:
        raise KeyError(f"数值公式引用未知属性：{magnitude.attribute_id}")


def _resource_magnitude(value: ResourceMagnitude, context: MagnitudeContext) -> float:
    resources = context.source_resources if value.owner == "source" else context.target_resources
    attributes = context.source_attributes if value.owner == "source" else context.target_attributes
    current = float(resources.get(value.resource_id, 0.0))
    if value.mode is ResourceValueMode.CURRENT:
        result = current
    else:
        assert value.maximum_attribute_id is not None
        maximum = attributes.value(value.maximum_attribute_id)
        if value.mode is ResourceValueMode.MISSING:
            result = max(0.0, maximum - current)
        elif maximum <= 0:
            result = 0.0
        elif value.mode is ResourceValueMode.RATIO:
            result = current / maximum
        else:
            result = max(0.0, maximum - current) / maximum
    return result * value.scale + value.offset


def _validate_resource_magnitude(
    magnitude: ResourceMagnitude,
    attributes: frozenset[StableId],
    resources: frozenset[StableId],
) -> None:
    if magnitude.resource_id not in resources:
        raise KeyError(f"数值公式引用未知资源：{magnitude.resource_id}")
    if magnitude.maximum_attribute_id and magnitude.maximum_attribute_id not in attributes:
        raise KeyError(f"数值公式引用未知资源上限属性：{magnitude.maximum_attribute_id}")


def _validate_nested(
    evaluators: MagnitudeEvaluators,
    values: tuple[Magnitude, ...],
    attributes: frozenset[StableId],
    resources: frozenset[StableId],
) -> None:
    for value in values:
        evaluators.validate(value, attributes, resources)


def _product_values(values) -> float:
    result = 1.0
    for value in values:
        result *= value
    return result


def _clamp_magnitude(
    evaluators: MagnitudeEvaluators,
    value: ClampMagnitude,
    context: MagnitudeContext,
) -> float:
    result = evaluators.evaluate(value.value, context)
    if value.minimum is not None:
        result = max(result, evaluators.evaluate(value.minimum, context))
    if value.maximum is not None:
        result = min(result, evaluators.evaluate(value.maximum, context))
    return result


def _ratio_magnitude(
    evaluators: MagnitudeEvaluators,
    value: RatioMagnitude,
    context: MagnitudeContext,
) -> float:
    denominator = evaluators.evaluate(value.denominator, context)
    if denominator == 0:
        return value.zero_default
    return evaluators.evaluate(value.numerator, context) / denominator


@dataclass(frozen=True)
class AttributeModifier:
    """已经求值得到具体数字的一条属性修改。"""

    id: str
    attribute_id: StableId
    layer: ModifierLayer
    value: float
    source_id: str
    required_tags: TagSet = EMPTY_TAGS
    blocked_tags: TagSet = EMPTY_TAGS
    priority: int = 0

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("属性修改缺少运行实例 id")
        object.__setattr__(self, "attribute_id", stable_id(self.attribute_id, field="modifier attribute id"))


@dataclass(frozen=True)
class AttributeBreakdown:
    """一个属性的可审计计算明细。"""

    base: float
    local_flat: float
    local_rate: float
    global_flat: float
    global_rate: float
    final_multiplier: float
    unclamped: float
    final: float


@dataclass(frozen=True)
class AttributeSnapshot:
    """一次规则执行使用的不可变属性快照。"""

    values: Mapping[StableId, float]
    breakdowns: Mapping[StableId, AttributeBreakdown]

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))
        object.__setattr__(self, "breakdowns", MappingProxyType(dict(self.breakdowns)))

    def value(self, attribute_id: StableId) -> float:
        key = stable_id(attribute_id, field="attribute id")
        try:
            return self.values[key]
        except KeyError as exc:
            raise KeyError(f"属性快照中不存在：{key}") from exc


class AttributeResolver:
    """按固定层级生成属性快照。"""

    def __init__(self, definitions: Mapping[StableId, AttributeDefinition]) -> None:
        self.definitions = dict(definitions)
        for key, definition in self.definitions.items():
            if key != definition.id:
                raise ValueError(f"属性定义映射键与 id 不一致：{key} != {definition.id}")

    def resolve(
        self,
        base_values: Mapping[StableId, float],
        modifiers: tuple[AttributeModifier, ...] = (),
        tags: TagSet = EMPTY_TAGS,
    ) -> AttributeSnapshot:
        unknown_base = set(base_values) - set(self.definitions)
        if unknown_base:
            raise KeyError(f"存在未知基础属性：{', '.join(sorted(unknown_base))}")

        active: dict[StableId, list[AttributeModifier]] = {key: [] for key in self.definitions}
        for modifier in sorted(modifiers, key=lambda item: (item.priority, item.id)):
            if modifier.attribute_id not in self.definitions:
                raise KeyError(f"属性修改引用未知属性：{modifier.attribute_id}")
            if tags.allows(required=modifier.required_tags, blocked=modifier.blocked_tags):
                active[modifier.attribute_id].append(modifier)

        values: dict[StableId, float] = {}
        breakdowns: dict[StableId, AttributeBreakdown] = {}
        for key, definition in self.definitions.items():
            base = float(base_values.get(key, definition.default))
            grouped = active[key]
            local_flat = self._sum(grouped, ModifierLayer.LOCAL_FLAT)
            local_rate = self._sum(grouped, ModifierLayer.LOCAL_RATE)
            global_flat = self._sum(grouped, ModifierLayer.GLOBAL_FLAT)
            global_rate = self._sum(grouped, ModifierLayer.GLOBAL_RATE)
            final_multiplier = self._product(grouped, ModifierLayer.FINAL_RATE)
            value = (base + local_flat) * (1.0 + local_rate)
            value = (value + global_flat) * (1.0 + global_rate)
            unclamped = value * final_multiplier
            final = definition.clamp(unclamped)
            values[key] = final
            breakdowns[key] = AttributeBreakdown(
                base=base,
                local_flat=local_flat,
                local_rate=local_rate,
                global_flat=global_flat,
                global_rate=global_rate,
                final_multiplier=final_multiplier,
                unclamped=unclamped,
                final=final,
            )
        return AttributeSnapshot(values, breakdowns)

    @staticmethod
    def _sum(modifiers: list[AttributeModifier], layer: ModifierLayer) -> float:
        return sum(modifier.value for modifier in modifiers if modifier.layer is layer)

    @staticmethod
    def _product(modifiers: list[AttributeModifier], layer: ModifierLayer) -> float:
        result = 1.0
        for modifier in modifiers:
            if modifier.layer is layer:
                result *= 1.0 + modifier.value
        return result


__all__ = [
    "AttributeBreakdown",
    "AttributeDefinition",
    "AttributeMagnitude",
    "AttributeModifier",
    "AttributeResolver",
    "AttributeSnapshot",
    "ClampMagnitude",
    "FixedMagnitude",
    "Magnitude",
    "MagnitudeContext",
    "MagnitudeEvaluators",
    "MaximumMagnitude",
    "MinimumMagnitude",
    "ModifierLayer",
    "ParameterMagnitude",
    "PowerMagnitude",
    "ProductMagnitude",
    "RatioMagnitude",
    "ResourceMagnitude",
    "ResourceDefinition",
    "ResourceValueMode",
    "SumMagnitude",
]
