"""战斗伤害请求、类型、规则和结算明细。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from ..ids import StableId, stable_id
from ..tags import EMPTY_TAGS, TagSet


@dataclass(frozen=True)
class DamageTypeDefinition:
    """一种伤害如何读取防御、穿透和专属增减伤。"""

    id: StableId
    defense_attribute: StableId | None = None
    flat_penetration_attribute: StableId | None = None
    rate_penetration_attribute: StableId | None = None
    source_rate_attribute: StableId | None = None
    target_rate_attribute: StableId | None = None
    ignores_defense: bool = False
    tags: TagSet = EMPTY_TAGS

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="damage type id"))
        for field_name in (
            "defense_attribute",
            "flat_penetration_attribute",
            "rate_penetration_attribute",
            "source_rate_attribute",
            "target_rate_attribute",
        ):
            value = getattr(self, field_name)
            if value:
                object.__setattr__(self, field_name, stable_id(value, field=field_name))
        penetration_attributes = (
            self.flat_penetration_attribute,
            self.rate_penetration_attribute,
        )
        if self.ignores_defense and (self.defense_attribute or any(penetration_attributes)):
            raise ValueError(f"伤害类型 {self.id} 忽略防御时不能引用防御或穿透属性")
        if not self.defense_attribute and any(penetration_attributes):
            raise ValueError(f"伤害类型 {self.id} 未设置防御属性，不能单独设置穿透属性")


class DamageStage(str, Enum):
    RAW = "raw"
    AFTER_CRITICAL = "after_critical"
    AFTER_DEFENSE = "after_defense"
    AFTER_RATES = "after_rates"
    AFTER_BLOCK = "after_block"
    BEFORE_SHIELD = "before_shield"


class InterceptorSide(str, Enum):
    SOURCE = "source"
    TARGET = "target"
    BOTH = "both"


@dataclass(frozen=True)
class DamageRedirect:
    target_id: str
    amount: float
    damage_type: StableId

    def __post_init__(self) -> None:
        if not self.target_id.strip():
            raise ValueError("DamageRedirect.target_id 不能为空")
        if self.amount < 0:
            raise ValueError("DamageRedirect.amount 不能小于 0")
        object.__setattr__(self, "damage_type", stable_id(self.damage_type, field="damage type id"))


@dataclass(frozen=True)
class DamageFrame:
    amount: float
    damage_type: StableId
    bypass_shield: bool = False
    minimum_health: float = 0.0
    redirects: tuple[DamageRedirect, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "damage_type", stable_id(self.damage_type, field="damage type id"))
        if self.amount < 0 or self.minimum_health < 0:
            raise ValueError("DamageFrame 数值不能小于 0")


@dataclass(frozen=True)
class DamageInterceptionRecord:
    interceptor_id: StableId
    owner_id: str
    source_id: str
    stage: DamageStage
    before: DamageFrame
    after: DamageFrame


@dataclass(frozen=True)
class CombatStats:
    """战斗内核使用的公共属性键；未配置的机制保持中性。"""

    health_resource: StableId
    shield_resource: StableId | None = None
    accuracy_attribute: StableId | None = None
    evasion_attribute: StableId | None = None
    critical_chance_attribute: StableId | None = None
    critical_damage_attribute: StableId | None = None
    block_chance_attribute: StableId | None = None
    block_reduction_attribute: StableId | None = None
    outgoing_rate_attribute: StableId | None = None
    incoming_rate_attribute: StableId | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "health_resource",
            stable_id(self.health_resource, field="health resource id"),
        )
        for field_name in (
            "shield_resource",
            "accuracy_attribute",
            "evasion_attribute",
            "critical_chance_attribute",
            "critical_damage_attribute",
            "block_chance_attribute",
            "block_reduction_attribute",
            "outgoing_rate_attribute",
            "incoming_rate_attribute",
        ):
            value = getattr(self, field_name)
            if value:
                object.__setattr__(self, field_name, stable_id(value, field=field_name))


@dataclass(frozen=True)
class DamageRules:
    """场景可替换的伤害公共边界，不在公式中埋具体玩法常量。"""

    base_hit_chance: float = 1.0
    minimum_hit_chance: float = 0.0
    maximum_hit_chance: float = 1.0
    maximum_critical_chance: float = 1.0
    default_critical_damage: float = 0.5
    maximum_critical_multiplier: float | None = None
    maximum_block_chance: float = 1.0
    default_block_reduction: float = 0.0
    maximum_block_reduction: float = 0.9
    defense_constant: float = 100.0
    minimum_rate_multiplier: float = 0.0
    maximum_rate_multiplier: float | None = None
    minimum_damage: float = 0.0

    def __post_init__(self) -> None:
        if not 0 <= self.minimum_hit_chance <= self.maximum_hit_chance <= 1:
            raise ValueError("命中概率边界必须满足 0 <= minimum <= maximum <= 1")
        if not 0 <= self.maximum_critical_chance <= 1:
            raise ValueError("maximum_critical_chance 必须在 0 到 1 之间")
        if self.default_critical_damage < 0:
            raise ValueError("default_critical_damage 不能小于 0")
        if self.maximum_critical_multiplier is not None and self.maximum_critical_multiplier < 1:
            raise ValueError("maximum_critical_multiplier 不能小于 1")
        if not 0 <= self.maximum_block_chance <= 1:
            raise ValueError("maximum_block_chance 必须在 0 到 1 之间")
        if not 0 <= self.default_block_reduction <= self.maximum_block_reduction <= 1:
            raise ValueError("格挡减伤边界必须位于 0 到 1 之间")
        if self.defense_constant <= 0:
            raise ValueError("defense_constant 必须大于 0")
        if self.minimum_rate_multiplier < 0:
            raise ValueError("minimum_rate_multiplier 不能小于 0")
        if (
            self.maximum_rate_multiplier is not None
            and self.maximum_rate_multiplier < self.minimum_rate_multiplier
        ):
            raise ValueError("maximum_rate_multiplier 不能小于 minimum_rate_multiplier")
        if self.minimum_damage < 0:
            raise ValueError("minimum_damage 不能小于 0")


@dataclass(frozen=True)
class DamageRequest:
    """一次进入标准伤害流水线的请求。"""

    id: str
    damage_type: StableId
    amount: float
    tags: TagSet = EMPTY_TAGS
    can_miss: bool = True
    can_critical: bool = True
    can_block: bool = True
    bypass_shield: bool = False
    minimum_damage: float | None = None
    maximum_damage: float | None = None
    maximum_target_health_ratio: float | None = None

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("DamageRequest 缺少 id")
        object.__setattr__(self, "damage_type", stable_id(self.damage_type, field="damage type id"))
        if self.amount < 0:
            raise ValueError("DamageRequest.amount 不能小于 0")
        if self.minimum_damage is not None and self.minimum_damage < 0:
            raise ValueError("minimum_damage 不能小于 0")
        if self.maximum_damage is not None and self.maximum_damage < 0:
            raise ValueError("maximum_damage 不能小于 0")
        if (
            self.minimum_damage is not None
            and self.maximum_damage is not None
            and self.minimum_damage > self.maximum_damage
        ):
            raise ValueError("minimum_damage 不能大于 maximum_damage")
        if self.maximum_target_health_ratio is not None and self.maximum_target_health_ratio < 0:
            raise ValueError("maximum_target_health_ratio 不能小于 0")


@dataclass(frozen=True)
class DamageBreakdown:
    """伤害每一层的可审计数值。"""

    raw: float
    hit_chance: float
    hit_roll: float | None
    critical_chance: float
    critical_roll: float | None
    critical_multiplier: float
    after_critical: float
    defense: float
    effective_defense: float
    defense_multiplier: float
    after_defense: float
    rate_multiplier: float
    after_rates: float
    block_chance: float
    block_roll: float | None
    block_reduction: float
    after_block: float
    limited: float


@dataclass(frozen=True)
class DamageResolution:
    """最终伤害、资源变化和供 Trigger 消费的事实。"""

    request: DamageRequest
    hit: bool
    critical: bool
    blocked: bool
    defeated: bool
    shield_broken: bool
    shield_damage: float
    health_damage: float
    overkill: float
    health_before: float
    health_after: float
    shield_before: float
    shield_after: float
    breakdown: DamageBreakdown
    resource_deltas: Mapping[StableId, float]
    interceptions: tuple[DamageInterceptionRecord, ...] = ()
    redirects: tuple[DamageRedirect, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "resource_deltas", MappingProxyType(dict(self.resource_deltas)))


__all__ = [
    "CombatStats",
    "DamageBreakdown",
    "DamageFrame",
    "DamageInterceptionRecord",
    "DamageRequest",
    "DamageRedirect",
    "DamageResolution",
    "DamageRules",
    "DamageStage",
    "DamageTypeDefinition",
    "InterceptorSide",
]
