"""属性曲线、机制价值、协同规则与多维估值结果。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from ..attributes import ModifierLayer
from ..ids import StableId, stable_id
from ..tags import EMPTY_TAGS, TagSet


class ValueAxis(str, Enum):
    OFFENSE = "offense"
    SURVIVAL = "survival"
    SUSTAIN = "sustain"
    TEMPO = "tempo"
    CONTROL = "control"
    VOLATILITY = "volatility"


class ReferenceValueKind(str, Enum):
    ABILITY = "ability"
    TRIGGER = "trigger"
    INTERCEPTOR = "interceptor"
    TARGET_CONSTRAINT = "target_constraint"
    TAG = "tag"


@dataclass(frozen=True)
class ValueVector:
    offense: float = 0.0
    survival: float = 0.0
    sustain: float = 0.0
    tempo: float = 0.0
    control: float = 0.0
    volatility: float = 0.0

    def __post_init__(self) -> None:
        if not all(
            isfinite(value)
            for value in (
                self.offense,
                self.survival,
                self.sustain,
                self.tempo,
                self.control,
                self.volatility,
            )
        ):
            raise ValueError("价值向量只能包含有限数")

    @property
    def total(self) -> float:
        return self.offense + self.survival + self.sustain + self.tempo + self.control

    def __add__(self, other: "ValueVector") -> "ValueVector":
        if not isinstance(other, ValueVector):
            return NotImplemented
        return ValueVector(
            self.offense + other.offense,
            self.survival + other.survival,
            self.sustain + other.sustain,
            self.tempo + other.tempo,
            self.control + other.control,
            self.volatility + other.volatility,
        )

    def __sub__(self, other: "ValueVector") -> "ValueVector":
        if not isinstance(other, ValueVector):
            return NotImplemented
        return self + other.scaled(-1.0)

    def scaled(self, factor: float) -> "ValueVector":
        if not isfinite(factor):
            raise ValueError("价值缩放系数必须是有限数")
        return ValueVector(
            self.offense * factor,
            self.survival * factor,
            self.sustain * factor,
            self.tempo * factor,
            self.control * factor,
            self.volatility * factor,
        )

    @classmethod
    def on_axis(cls, axis: ValueAxis, points: float) -> "ValueVector":
        values = {value.value: 0.0 for value in ValueAxis}
        values[ValueAxis(axis).value] = float(points)
        return cls(**values)


@dataclass(frozen=True, order=True)
class ValueCurvePoint:
    input_value: float
    points: float

    def __post_init__(self) -> None:
        if not isfinite(self.input_value) or not isfinite(self.points):
            raise ValueError("价值曲线只能包含有限数")


@dataclass(frozen=True)
class AttributeValuationDefinition:
    attribute_id: StableId
    layer: ModifierLayer
    axis: ValueAxis
    curve: tuple[ValueCurvePoint, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "attribute_id", stable_id(self.attribute_id, field="attribute id"))
        object.__setattr__(self, "layer", ModifierLayer(self.layer))
        object.__setattr__(self, "axis", ValueAxis(self.axis))
        curve = tuple(self.curve)
        if len(curve) < 2:
            raise ValueError("属性价值曲线至少需要两个点")
        inputs = [point.input_value for point in curve]
        if inputs != sorted(inputs) or len(inputs) != len(set(inputs)):
            raise ValueError("属性价值曲线输入必须严格递增")
        if not any(point.input_value == 0 for point in curve):
            raise ValueError("属性价值曲线必须包含输入 0")
        object.__setattr__(self, "curve", curve)

    @property
    def key(self) -> tuple[StableId, ModifierLayer]:
        return self.attribute_id, self.layer

    @property
    def id(self) -> StableId:
        return f"valuation_attribute.{self.attribute_id}.{self.layer.value}"


@dataclass(frozen=True)
class ReferenceValuationDefinition:
    kind: ReferenceValueKind
    reference_id: StableId
    value: ValueVector

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", ReferenceValueKind(self.kind))
        object.__setattr__(self, "reference_id", stable_id(self.reference_id, field="reference id"))

    @property
    def key(self) -> tuple[ReferenceValueKind, StableId]:
        return self.kind, self.reference_id

    @property
    def id(self) -> StableId:
        return f"valuation_reference.{self.kind.value}.{self.reference_id}"


@dataclass(frozen=True)
class SynergyValuationDefinition:
    id: StableId
    required_tags: TagSet
    value: ValueVector
    blocked_tags: TagSet = EMPTY_TAGS

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="synergy valuation id"))
        if not self.required_tags.values:
            raise ValueError("协同价值至少需要一个标签")


@dataclass(frozen=True)
class ValuationResult:
    value: ValueVector
    unvalued: tuple[str, ...] = ()

    @property
    def total(self) -> float:
        return self.value.total


__all__ = [
    "AttributeValuationDefinition",
    "ReferenceValuationDefinition",
    "ReferenceValueKind",
    "SynergyValuationDefinition",
    "ValuationResult",
    "ValueAxis",
    "ValueCurvePoint",
    "ValueVector",
]
