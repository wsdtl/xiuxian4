"""把标准伤害流水线注册为 Effect 原子操作。"""

from __future__ import annotations

from dataclasses import dataclass

from ..attributes import Magnitude
from ..effects import (
    EffectContribution,
    EffectFact,
    EffectOperationContext,
    EffectOperationHandlers,
    RuleReferences,
)
from ..ids import StableId, stable_id
from ..tags import EMPTY_TAGS, TagSet
from .engine import DamageEngine
from .models import DamageRequest, DamageResolution


@dataclass(frozen=True)
class DealDamage:
    """Effect 中唯一允许进入正式伤害流水线的原子操作。"""

    id: StableId
    damage_type: StableId
    magnitude: Magnitude
    tags: TagSet = EMPTY_TAGS
    can_miss: bool = True
    can_critical: bool = True
    can_block: bool = True
    bypass_shield: bool = False
    minimum_damage: float | None = None
    maximum_damage: float | None = None
    maximum_target_health_ratio: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="operation id"))
        object.__setattr__(self, "damage_type", stable_id(self.damage_type, field="damage type id"))
        if self.minimum_damage is not None and self.minimum_damage < 0:
            raise ValueError("DealDamage.minimum_damage 不能小于 0")
        if self.maximum_damage is not None and self.maximum_damage < 0:
            raise ValueError("DealDamage.maximum_damage 不能小于 0")
        if (
            self.minimum_damage is not None
            and self.maximum_damage is not None
            and self.minimum_damage > self.maximum_damage
        ):
            raise ValueError("DealDamage.minimum_damage 不能大于 maximum_damage")
        if self.maximum_target_health_ratio is not None and self.maximum_target_health_ratio < 0:
            raise ValueError("DealDamage.maximum_target_health_ratio 不能小于 0")


def register_damage_operation(
    handlers: EffectOperationHandlers,
    engine: DamageEngine,
) -> None:
    """向现有处理器注册 DealDamage，不创建第二套 EffectEngine。"""

    def execute(
        operation: DealDamage,
        context: EffectOperationContext,
    ) -> EffectContribution:
        amount = max(
            0.0,
            context.magnitudes.evaluate(operation.magnitude, context.magnitude_context),
        )
        resolution = engine.resolve(
            DamageRequest(
                id=f"{context.spec.instance_id}:{operation.id}",
                damage_type=operation.damage_type,
                amount=amount,
                tags=operation.tags,
                can_miss=operation.can_miss,
                can_critical=operation.can_critical,
                can_block=operation.can_block,
                bypass_shield=operation.bypass_shield,
                minimum_damage=operation.minimum_damage,
                maximum_damage=operation.maximum_damage,
                maximum_target_health_ratio=operation.maximum_target_health_ratio,
            ),
            source=context.source,
            target=context.target,
            context=context.rule,
        )
        return EffectContribution(
            resource_deltas=resolution.resource_deltas,
            facts=_facts(resolution),
        )

    def validate(operation: DealDamage, references: RuleReferences) -> None:
        if operation.damage_type not in engine.damage_types:
            raise KeyError(
                f"伤害操作 {operation.id} 引用了未知伤害类型：{operation.damage_type}"
            )
        required_resources = {engine.stats.health_resource}
        if engine.stats.shield_resource:
            required_resources.add(engine.stats.shield_resource)
        unknown = required_resources - references.resources
        if unknown:
            raise KeyError(
                f"伤害操作 {operation.id} 缺少资源定义：{', '.join(sorted(unknown))}"
            )
        missing_attributes = set(engine.attributes.definitions) - references.attributes
        if missing_attributes:
            raise KeyError(
                f"伤害操作 {operation.id} 缺少属性定义："
                f"{', '.join(sorted(missing_attributes))}"
            )

    handlers.register(DealDamage, execute, validate)


def _facts(resolution: DamageResolution) -> tuple[EffectFact, ...]:
    request = resolution.request
    breakdown = resolution.breakdown
    common = {
        "request_id": request.id,
        "damage_type": request.damage_type,
        "raw": breakdown.raw,
    }
    interception_facts = tuple(
        EffectFact(
            "combat.damage.intercepted",
            record.interceptor_id,
            {
                **common,
                "owner_id": record.owner_id,
                "grant_source_id": record.source_id,
                "stage": record.stage.value,
                "before_amount": record.before.amount,
                "after_amount": record.after.amount,
                "before_damage_type": record.before.damage_type,
                "after_damage_type": record.after.damage_type,
                "bypass_shield": record.after.bypass_shield,
                "minimum_health": record.after.minimum_health,
            },
        )
        for record in resolution.interceptions
    )
    redirect_facts = tuple(
        EffectFact(
            "combat.damage.redirected",
            redirect.damage_type,
            {
                **common,
                "amount": redirect.amount,
                "damage_type": redirect.damage_type,
            },
            target_id=redirect.target_id,
        )
        for redirect in resolution.redirects
    )
    if not resolution.hit:
        return (*interception_facts,
            EffectFact(
                "combat.attack.missed",
                request.damage_type,
                {
                    **common,
                    "hit_chance": breakdown.hit_chance,
                    "hit_roll": breakdown.hit_roll,
                },
            ),
        )

    facts: list[EffectFact] = [
        *interception_facts,
        *redirect_facts,
        EffectFact(
            "combat.attack.hit",
            request.damage_type,
            {
                **common,
                "hit_chance": breakdown.hit_chance,
                "hit_roll": breakdown.hit_roll,
            },
        )
    ]
    if resolution.critical:
        facts.append(
            EffectFact(
                "combat.attack.critical",
                request.damage_type,
                {
                    **common,
                    "critical_chance": breakdown.critical_chance,
                    "critical_roll": breakdown.critical_roll,
                    "critical_multiplier": breakdown.critical_multiplier,
                },
            )
        )
    if resolution.blocked:
        facts.append(
            EffectFact(
                "combat.attack.blocked",
                request.damage_type,
                {
                    **common,
                    "block_chance": breakdown.block_chance,
                    "block_roll": breakdown.block_roll,
                    "block_reduction": breakdown.block_reduction,
                },
            )
        )
    if resolution.shield_damage:
        facts.append(
            EffectFact(
                "combat.shield.damaged",
                request.damage_type,
                {
                    **common,
                    "shield_damage": resolution.shield_damage,
                    "shield_before": resolution.shield_before,
                    "shield_after": resolution.shield_after,
                },
            )
        )
    if resolution.shield_broken:
        facts.append(
            EffectFact(
                "combat.shield.broken",
                request.damage_type,
                {**common, "shield_damage": resolution.shield_damage},
            )
        )
    effective_damage = resolution.shield_damage + resolution.health_damage
    damage_values = {
        **common,
        "critical": resolution.critical,
        "blocked": resolution.blocked,
        "requested_damage": breakdown.limited,
        "shield_damage": resolution.shield_damage,
        "health_damage": resolution.health_damage,
        "effective_damage": effective_damage,
        "overkill": resolution.overkill,
        "health_before": resolution.health_before,
        "health_after": resolution.health_after,
        "defense": breakdown.defense,
        "effective_defense": breakdown.effective_defense,
        "defense_multiplier": breakdown.defense_multiplier,
        "rate_multiplier": breakdown.rate_multiplier,
    }
    facts.append(
        EffectFact(
            "combat.damage.dealt" if effective_damage > 0 else "combat.damage.prevented",
            request.damage_type,
            damage_values,
        )
    )
    if resolution.defeated:
        facts.append(
            EffectFact(
                "combat.target.defeated",
                request.damage_type,
                {
                    **common,
                    "health_damage": resolution.health_damage,
                    "overkill": resolution.overkill,
                },
            )
        )
    return tuple(facts)


__all__ = ["DealDamage", "register_damage_operation"]
