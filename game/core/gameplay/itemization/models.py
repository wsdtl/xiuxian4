"""随机属性、生成策略、品质区间与不可变生成凭据。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Mapping

from ..attributes import ModifierLayer
from ..character import ContributionSpec
from ..ids import StableId, stable_id
from ..tags import EMPTY_TAGS, TagSet
from ..valuation import ValueVector


class ItemizationKind(str, Enum):
    WEAPON = "weapon"
    EQUIPMENT = "equipment"


@dataclass(frozen=True)
class PropertyParameterDefinition:
    id: StableId
    attribute_id: StableId
    layer: ModifierLayer
    minimum: float
    maximum: float
    step: float = 1.0
    priority: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="property parameter id"))
        object.__setattr__(self, "attribute_id", stable_id(self.attribute_id, field="attribute id"))
        object.__setattr__(self, "layer", ModifierLayer(self.layer))
        if not all(isfinite(value) for value in (self.minimum, self.maximum, self.step)):
            raise ValueError("随机属性参数只能使用有限数")
        if self.maximum < self.minimum or self.step <= 0:
            raise ValueError("随机属性参数范围或步长无效")
        steps = (self.maximum - self.minimum) / self.step
        if abs(steps - round(steps)) > 1e-9:
            raise ValueError("随机属性参数范围必须能被步长整除")


@dataclass(frozen=True)
class PropertyTierDefinition:
    tier: int
    weight: int
    contribution: ContributionSpec = ContributionSpec()
    parameters: tuple[PropertyParameterDefinition, ...] = ()

    def __post_init__(self) -> None:
        if self.tier < 1 or self.weight < 1:
            raise ValueError("随机属性档位与权重必须大于 0")
        parameters = tuple(self.parameters)
        ids = [value.id for value in parameters]
        if len(ids) != len(set(ids)):
            raise ValueError("同一随机属性档位不能包含重复参数")
        object.__setattr__(self, "parameters", parameters)


@dataclass(frozen=True)
class PropertyDefinition:
    id: StableId
    weight: int
    tiers: tuple[PropertyTierDefinition, ...]
    tags: TagSet = EMPTY_TAGS
    required_selected_tags: TagSet = EMPTY_TAGS
    blocked_selected_tags: TagSet = EMPTY_TAGS

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="property id"))
        tiers = tuple(self.tiers)
        if self.weight < 1 or not tiers:
            raise ValueError("随机属性权重必须大于 0 且至少包含一个档位")
        numbers = [value.tier for value in tiers]
        if len(numbers) != len(set(numbers)):
            raise ValueError("随机属性档位不能重复")
        object.__setattr__(self, "tiers", tiers)


@dataclass(frozen=True)
class QualityValueBand:
    quality_id: StableId
    minimum_value: float
    maximum_value: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "quality_id", stable_id(self.quality_id, field="quality id"))
        if not isfinite(self.minimum_value) or (
            self.maximum_value is not None and not isfinite(self.maximum_value)
        ):
            raise ValueError("品质价值区间只能使用有限数")
        if self.maximum_value is not None and self.maximum_value <= self.minimum_value:
            raise ValueError("品质价值上限必须大于下限")

    def contains(self, value: float) -> bool:
        return value >= self.minimum_value and (
            self.maximum_value is None or value < self.maximum_value
        )


@dataclass(frozen=True)
class GenerationProfileDefinition:
    id: StableId
    kind: ItemizationKind
    property_ids: frozenset[StableId]
    minimum_properties: int
    maximum_properties: int
    quality_bands: tuple[QualityValueBand, ...]
    core_property_ids: frozenset[StableId] = frozenset()
    enforce_compatibility: bool = False
    maximum_attempts: int = 64

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="generation profile id"))
        object.__setattr__(self, "kind", ItemizationKind(self.kind))
        properties = frozenset(stable_id(value, field="property id") for value in self.property_ids)
        core = frozenset(stable_id(value, field="property id") for value in self.core_property_ids)
        bands = tuple(self.quality_bands)
        if not properties or not 1 <= self.minimum_properties <= self.maximum_properties:
            raise ValueError("生成策略属性池或数量边界无效")
        if self.maximum_properties > len(properties) or self.maximum_attempts < 1:
            raise ValueError("生成策略属性数量或尝试次数无效")
        if not core.issubset(properties):
            raise ValueError("流派核心属性必须属于生成池")
        if self.kind is ItemizationKind.WEAPON and not core:
            raise ValueError("武器生成策略必须提供流派核心属性池")
        if self.kind is ItemizationKind.WEAPON and self.maximum_properties > 1 + len(properties - core):
            raise ValueError("武器生成策略只能抽取一个流派核心")
        if self.kind is ItemizationKind.EQUIPMENT and core:
            raise ValueError("装备生成策略不使用流派核心属性池")
        if not bands:
            raise ValueError("生成策略必须提供品质价值区间")
        ordered = sorted(bands, key=lambda value: value.minimum_value)
        if tuple(ordered) != bands:
            raise ValueError("品质价值区间必须按下限递增")
        for left, right in zip(bands, bands[1:]):
            if left.maximum_value != right.minimum_value:
                raise ValueError("品质价值区间必须连续且不能重叠")
        if bands[-1].maximum_value is not None:
            raise ValueError("最后一个品质价值区间必须没有上限")
        object.__setattr__(self, "property_ids", properties)
        object.__setattr__(self, "core_property_ids", core)
        object.__setattr__(self, "quality_bands", bands)


@dataclass(frozen=True)
class RolledProperty:
    property_id: StableId
    tier: int
    values: Mapping[StableId, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "property_id", stable_id(self.property_id, field="property id"))
        if self.tier < 1:
            raise ValueError("随机属性档位必须大于 0")
        values = {
            stable_id(key, field="property parameter id"): float(value)
            for key, value in self.values.items()
        }
        if not all(isfinite(value) for value in values.values()):
            raise ValueError("随机属性滚值只能包含有限数")
        object.__setattr__(self, "values", MappingProxyType(values))


@dataclass(frozen=True)
class GenerationDecision:
    position: int
    property_id: StableId
    tier: int
    values: Mapping[StableId, float]

    def __post_init__(self) -> None:
        if self.position < 0 or self.tier < 1:
            raise ValueError("生成判定位置或档位无效")
        object.__setattr__(self, "property_id", stable_id(self.property_id, field="property id"))
        values = {
            stable_id(key, field="property parameter id"): float(value)
            for key, value in self.values.items()
        }
        if not all(isfinite(value) for value in values.values()):
            raise ValueError("生成判定滚值只能包含有限数")
        object.__setattr__(self, "values", MappingProxyType(values))


@dataclass(frozen=True)
class GenerationReceipt:
    command_id: str
    profile_id: StableId
    generator_version: str
    content_fingerprint: str
    trace_id: str
    generated_at: datetime
    attempts: int
    decisions: tuple[GenerationDecision, ...]

    def __post_init__(self) -> None:
        if not all(
            (
                self.command_id.strip(),
                self.generator_version.strip(),
                self.content_fingerprint.strip(),
                self.trace_id.strip(),
            )
        ):
            raise ValueError("生成凭据缺少身份或版本")
        object.__setattr__(self, "profile_id", stable_id(self.profile_id, field="generation profile id"))
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("生成时间必须包含时区")
        if self.attempts < 1:
            raise ValueError("生成尝试次数必须大于 0")
        object.__setattr__(self, "decisions", tuple(self.decisions))


@dataclass(frozen=True)
class ItemRollState:
    profile_id: StableId
    quality_id: StableId
    properties: tuple[RolledProperty, ...]
    intrinsic_value: ValueVector
    receipt: GenerationReceipt

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", stable_id(self.profile_id, field="generation profile id"))
        object.__setattr__(self, "quality_id", stable_id(self.quality_id, field="quality id"))
        properties = tuple(self.properties)
        ids = [value.property_id for value in properties]
        if not properties or len(ids) != len(set(ids)):
            raise ValueError("生成物品必须包含互不重复的随机属性")
        if self.receipt.profile_id != self.profile_id:
            raise ValueError("生成物品与凭据策略不一致")
        object.__setattr__(self, "properties", properties)


@dataclass(frozen=True)
class ItemGenerationCommand:
    id: str
    profile_id: StableId
    content_fingerprint: str

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.content_fingerprint.strip():
            raise ValueError("物品生成命令缺少身份或内容指纹")
        object.__setattr__(self, "profile_id", stable_id(self.profile_id, field="generation profile id"))


@dataclass(frozen=True)
class ItemGenerationExecution:
    roll: ItemRollState
    contribution: ContributionSpec


__all__ = [
    "GenerationDecision",
    "GenerationProfileDefinition",
    "GenerationReceipt",
    "ItemGenerationCommand",
    "ItemGenerationExecution",
    "ItemRollState",
    "ItemizationKind",
    "PropertyDefinition",
    "PropertyParameterDefinition",
    "PropertyTierDefinition",
    "QualityValueBand",
    "RolledProperty",
]
