"""正式治疗与护盾授予协议。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ..attributes import AttributeResolver, Magnitude, ResourceDefinition
from ..effects import (
    EffectContribution,
    EffectFact,
    EffectOperationContext,
    EffectOperationHandlers,
    RuleReferences,
)
from ..entity import RuleEntity
from ..ids import StableId, stable_id


@dataclass(frozen=True)
class RecoveryStats:
    health_resource: StableId
    shield_resource: StableId | None = None
    source_healing_rate_attribute: StableId | None = None
    target_healing_received_attribute: StableId | None = None
    minimum_healing_multiplier: float = 0.0
    maximum_healing_multiplier: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "health_resource",
            stable_id(self.health_resource, field="health resource id"),
        )
        for field_name in (
            "shield_resource",
            "source_healing_rate_attribute",
            "target_healing_received_attribute",
        ):
            value = getattr(self, field_name)
            if value:
                object.__setattr__(self, field_name, stable_id(value, field=field_name))
        if self.minimum_healing_multiplier < 0:
            raise ValueError("minimum_healing_multiplier 不能小于 0")
        if (
            self.maximum_healing_multiplier is not None
            and self.maximum_healing_multiplier < self.minimum_healing_multiplier
        ):
            raise ValueError("maximum_healing_multiplier 不能小于 minimum_healing_multiplier")


@dataclass(frozen=True)
class HealingResolution:
    requested: float
    multiplier: float
    modified: float
    actual: float
    overheal: float
    before: float
    after: float
    revived: bool


class RecoveryEngine:
    """统一计算治疗增益、受疗修正、禁疗和过量治疗。"""

    def __init__(
        self,
        attributes: AttributeResolver,
        resources: Mapping[StableId, ResourceDefinition],
        stats: RecoveryStats,
    ) -> None:
        self.attributes = attributes
        self.resources = dict(resources)
        self.stats = stats
        self._validate_references()

    def resolve_healing(
        self,
        amount: float,
        *,
        source: RuleEntity,
        target: RuleEntity,
    ) -> HealingResolution:
        requested = max(0.0, float(amount))
        source_snapshot = source.snapshot(self.attributes)
        target_snapshot = target.snapshot(self.attributes)
        multiplier = 1.0
        if self.stats.source_healing_rate_attribute:
            multiplier += source_snapshot.value(self.stats.source_healing_rate_attribute)
        if self.stats.target_healing_received_attribute:
            multiplier += target_snapshot.value(self.stats.target_healing_received_attribute)
        multiplier = max(self.stats.minimum_healing_multiplier, multiplier)
        if self.stats.maximum_healing_multiplier is not None:
            multiplier = min(self.stats.maximum_healing_multiplier, multiplier)
        modified = requested * multiplier
        definition = self.resources[self.stats.health_resource]
        before = target.resources.get(definition.id, definition.minimum)
        maximum = definition.fixed_maximum
        if definition.maximum_attribute:
            maximum = target_snapshot.value(definition.maximum_attribute)
        available = modified if maximum is None else max(0.0, maximum - before)
        actual = min(modified, available)
        return HealingResolution(
            requested=requested,
            multiplier=multiplier,
            modified=modified,
            actual=actual,
            overheal=max(0.0, modified - actual),
            before=before,
            after=before + actual,
            revived=before <= definition.minimum and before + actual > definition.minimum,
        )

    def resolve_shield(
        self,
        amount: float,
        *,
        target: RuleEntity,
        maximum_target_health_ratio: float | None,
    ) -> tuple[float, float, float]:
        if not self.stats.shield_resource:
            raise ValueError("RecoveryStats 未配置 shield_resource")
        requested = max(0.0, float(amount))
        definition = self.resources[self.stats.shield_resource]
        before = target.resources.get(definition.id, definition.minimum)
        actual = requested
        if maximum_target_health_ratio is not None:
            health = self.resources[self.stats.health_resource]
            maximum_health = health.fixed_maximum
            if health.maximum_attribute:
                maximum_health = target.snapshot(self.attributes).value(health.maximum_attribute)
            if maximum_health is not None:
                actual = min(actual, max(0.0, maximum_health * maximum_target_health_ratio - before))
        return requested, actual, before

    def _validate_references(self) -> None:
        if self.stats.health_resource not in self.resources:
            raise KeyError(f"治疗协议缺少血气资源：{self.stats.health_resource}")
        if self.stats.shield_resource and self.stats.shield_resource not in self.resources:
            raise KeyError(f"治疗协议缺少护盾资源：{self.stats.shield_resource}")
        attributes = set(self.attributes.definitions)
        unknown = {
            value
            for value in (
                self.stats.source_healing_rate_attribute,
                self.stats.target_healing_received_attribute,
            )
            if value and value not in attributes
        }
        if unknown:
            raise KeyError(f"治疗协议引用未知属性：{', '.join(sorted(unknown))}")


@dataclass(frozen=True)
class Heal:
    id: StableId
    magnitude: Magnitude

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="operation id"))


@dataclass(frozen=True)
class GrantShield:
    id: StableId
    magnitude: Magnitude
    maximum_target_health_ratio: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="operation id"))
        if self.maximum_target_health_ratio is not None and self.maximum_target_health_ratio < 0:
            raise ValueError("GrantShield.maximum_target_health_ratio 不能小于 0")


def register_recovery_operations(
    handlers: EffectOperationHandlers,
    engine: RecoveryEngine,
) -> None:
    def heal(operation: Heal, context: EffectOperationContext) -> EffectContribution:
        amount = context.magnitudes.evaluate(operation.magnitude, context.magnitude_context)
        resolution = engine.resolve_healing(
            amount,
            source=context.source,
            target=context.target,
        )
        facts = [
            EffectFact(
                "combat.healing.resolved",
                engine.stats.health_resource,
                {
                    "operation_id": operation.id,
                    "requested": resolution.requested,
                    "multiplier": resolution.multiplier,
                    "modified": resolution.modified,
                    "actual": resolution.actual,
                    "overheal": resolution.overheal,
                    "before": resolution.before,
                    "after": resolution.after,
                },
            )
        ]
        if resolution.revived:
            facts.append(
                EffectFact(
                    "combat.target.revived",
                    engine.stats.health_resource,
                    {
                        "before": resolution.before,
                        "after": resolution.after,
                        "actual": resolution.actual,
                    },
                )
            )
        return EffectContribution(
            resource_deltas={engine.stats.health_resource: resolution.actual},
            facts=tuple(facts),
        )

    def shield(operation: GrantShield, context: EffectOperationContext) -> EffectContribution:
        amount = context.magnitudes.evaluate(operation.magnitude, context.magnitude_context)
        requested, actual, before = engine.resolve_shield(
            amount,
            target=context.target,
            maximum_target_health_ratio=operation.maximum_target_health_ratio,
        )
        assert engine.stats.shield_resource is not None
        return EffectContribution(
            resource_deltas={engine.stats.shield_resource: actual},
            facts=(
                EffectFact(
                    "combat.shield.granted",
                    engine.stats.shield_resource,
                    {
                        "operation_id": operation.id,
                        "requested": requested,
                        "actual": actual,
                        "before": before,
                        "after": before + actual,
                    },
                ),
            ),
        )

    def validate_heal(_operation: Heal, references: RuleReferences) -> None:
        if engine.stats.health_resource not in references.resources:
            raise KeyError(f"治疗操作缺少资源：{engine.stats.health_resource}")

    def validate_shield(_operation: GrantShield, references: RuleReferences) -> None:
        if not engine.stats.shield_resource:
            raise KeyError("GrantShield 需要 RecoveryStats.shield_resource")
        if engine.stats.shield_resource not in references.resources:
            raise KeyError(f"护盾操作缺少资源：{engine.stats.shield_resource}")

    handlers.register(Heal, heal, validate_heal)
    handlers.register(GrantShield, shield, validate_shield)


__all__ = [
    "GrantShield",
    "Heal",
    "HealingResolution",
    "RecoveryEngine",
    "RecoveryStats",
    "register_recovery_operations",
]
