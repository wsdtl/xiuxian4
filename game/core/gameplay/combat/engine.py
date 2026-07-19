"""可重放、可审计的标准伤害流水线。"""

from __future__ import annotations

from dataclasses import replace
from typing import Mapping

from ..attributes import AttributeResolver, AttributeSnapshot, ResourceDefinition
from ..context import RuleContext
from ..entity import RuleEntity
from ..ids import StableId
from .models import (
    CombatStats,
    DamageBreakdown,
    DamageFrame,
    DamageInterceptionRecord,
    DamageRequest,
    DamageResolution,
    DamageRules,
    DamageStage,
    DamageTypeDefinition,
)
from .interceptors import DamageInterceptorRegistry


class DamageEngine:
    """只计算伤害，不决定行动顺序、技能选择或战斗胜负奖励。"""

    def __init__(
        self,
        damage_types: Mapping[StableId, DamageTypeDefinition],
        attributes: AttributeResolver,
        resources: Mapping[StableId, ResourceDefinition],
        stats: CombatStats,
        rules: DamageRules | None = None,
        interceptors: DamageInterceptorRegistry | None = None,
    ) -> None:
        self.damage_types = dict(damage_types)
        self.attributes = attributes
        self.resources = dict(resources)
        self.stats = stats
        self.rules = rules or DamageRules()
        self.interceptors = interceptors
        self._validate_references()
        if self.interceptors:
            self.interceptors.freeze()

    def resolve(
        self,
        request: DamageRequest,
        *,
        source: RuleEntity,
        target: RuleEntity,
        context: RuleContext,
    ) -> DamageResolution:
        """按固定层级结算一次伤害，并返回实际资源变化。"""

        source_attributes = source.snapshot(self.attributes)
        target_attributes = target.snapshot(self.attributes)
        raw = max(0.0, float(request.amount))
        frame = DamageFrame(raw, request.damage_type, request.bypass_shield)
        frame, interceptions = self._intercept(
            DamageStage.RAW,
            frame,
            request,
            source,
            target,
            context,
        )
        try:
            damage_type = self.damage_types[frame.damage_type]
        except KeyError as exc:
            raise KeyError(f"未知伤害类型：{frame.damage_type}") from exc
        effective_request = replace(
            request,
            damage_type=frame.damage_type,
            tags=request.tags.merged(damage_type.tags),
        )
        raw_after_interception = frame.amount

        hit_chance = self._hit_chance(source_attributes, target_attributes)
        hit_roll = context.random.random() if request.can_miss else None
        hit = not request.can_miss or bool(hit_roll is not None and hit_roll < hit_chance)
        if not hit:
            return self._missed_resolution(
                effective_request,
                target,
                raw,
                hit_chance,
                hit_roll,
                interceptions,
            )

        critical_chance = self._clamp(
            self._attribute(source_attributes, self.stats.critical_chance_attribute),
            0.0,
            self.rules.maximum_critical_chance,
        )
        critical_roll = context.random.random() if request.can_critical else None
        critical = bool(
            request.can_critical
            and critical_roll is not None
            and critical_roll < critical_chance
        )
        critical_multiplier = 1.0
        if critical:
            critical_multiplier += self._attribute(
                source_attributes,
                self.stats.critical_damage_attribute,
                self.rules.default_critical_damage,
            )
            critical_multiplier = max(1.0, critical_multiplier)
            if self.rules.maximum_critical_multiplier is not None:
                critical_multiplier = min(
                    self.rules.maximum_critical_multiplier,
                    critical_multiplier,
                )
        after_critical = raw_after_interception * critical_multiplier
        frame = replace(frame, amount=after_critical)
        frame, records = self._intercept(
            DamageStage.AFTER_CRITICAL,
            frame,
            effective_request,
            source,
            target,
            context,
        )
        interceptions += records
        after_critical = frame.amount

        defense, effective_defense, defense_multiplier = self._defense_layer(
            damage_type,
            source_attributes,
            target_attributes,
        )
        after_defense = after_critical * defense_multiplier
        frame = replace(frame, amount=after_defense)
        frame, records = self._intercept(
            DamageStage.AFTER_DEFENSE,
            frame,
            effective_request,
            source,
            target,
            context,
        )
        interceptions += records
        after_defense = frame.amount
        rate_multiplier = self._rate_multiplier(
            damage_type,
            source_attributes,
            target_attributes,
        )
        after_rates = after_defense * rate_multiplier
        frame = replace(frame, amount=after_rates)
        frame, records = self._intercept(
            DamageStage.AFTER_RATES,
            frame,
            effective_request,
            source,
            target,
            context,
        )
        interceptions += records
        after_rates = frame.amount

        block_chance = self._clamp(
            self._attribute(target_attributes, self.stats.block_chance_attribute),
            0.0,
            self.rules.maximum_block_chance,
        )
        block_roll = context.random.random() if request.can_block else None
        blocked = bool(
            request.can_block
            and block_roll is not None
            and block_roll < block_chance
        )
        block_reduction = 0.0
        if blocked:
            block_reduction = self._clamp(
                self._attribute(
                    target_attributes,
                    self.stats.block_reduction_attribute,
                    self.rules.default_block_reduction,
                ),
                0.0,
                self.rules.maximum_block_reduction,
            )
        after_block = after_rates * (1.0 - block_reduction)
        frame = replace(frame, amount=after_block)
        frame, records = self._intercept(
            DamageStage.AFTER_BLOCK,
            frame,
            effective_request,
            source,
            target,
            context,
        )
        interceptions += records
        after_block = frame.amount
        limited = self._limit_damage(
            effective_request,
            after_block,
            target_attributes,
            prevented=frame.prevented,
        )
        frame = replace(frame, amount=limited)
        frame, records = self._intercept(
            DamageStage.BEFORE_SHIELD,
            frame,
            effective_request,
            source,
            target,
            context,
        )
        interceptions += records
        limited = frame.amount

        health_definition = self.resources[self.stats.health_resource]
        health_before = target.resources.get(
            self.stats.health_resource,
            health_definition.minimum,
        )
        shield_before = self._shield_value(target)
        shield_damage = 0.0
        if self.stats.shield_resource and not frame.bypass_shield:
            shield_damage = min(shield_before, limited)
        pending_health_damage = max(0.0, limited - shield_damage)
        health_floor = max(health_definition.minimum, frame.minimum_health)
        available_health = max(0.0, health_before - health_floor)
        health_damage = min(available_health, pending_health_damage)
        overkill = max(0.0, pending_health_damage - health_damage)
        health_after = health_before - health_damage
        shield_after = shield_before - shield_damage
        defeated = health_before > health_definition.minimum and health_after <= health_definition.minimum
        shield_broken = shield_before > 0 and shield_after <= 0

        deltas: dict[StableId, float] = {}
        if shield_damage and self.stats.shield_resource:
            deltas[self.stats.shield_resource] = -shield_damage
        if health_damage:
            deltas[self.stats.health_resource] = -health_damage
        breakdown = DamageBreakdown(
            raw=raw,
            hit_chance=hit_chance,
            hit_roll=hit_roll,
            critical_chance=critical_chance,
            critical_roll=critical_roll,
            critical_multiplier=critical_multiplier,
            after_critical=after_critical,
            defense=defense,
            effective_defense=effective_defense,
            defense_multiplier=defense_multiplier,
            after_defense=after_defense,
            rate_multiplier=rate_multiplier,
            after_rates=after_rates,
            block_chance=block_chance,
            block_roll=block_roll,
            block_reduction=block_reduction,
            after_block=after_block,
            limited=limited,
        )
        return DamageResolution(
            request=effective_request,
            hit=True,
            critical=critical,
            blocked=blocked,
            defeated=defeated,
            shield_broken=shield_broken,
            shield_damage=shield_damage,
            health_damage=health_damage,
            overkill=overkill,
            health_before=health_before,
            health_after=health_after,
            shield_before=shield_before,
            shield_after=shield_after,
            breakdown=breakdown,
            resource_deltas=deltas,
            interceptions=interceptions,
            redirects=frame.redirects,
        )

    def _missed_resolution(
        self,
        request: DamageRequest,
        target: RuleEntity,
        raw: float,
        hit_chance: float,
        hit_roll: float | None,
        interceptions: tuple[DamageInterceptionRecord, ...] = (),
    ) -> DamageResolution:
        health_definition = self.resources[self.stats.health_resource]
        health = target.resources.get(self.stats.health_resource, health_definition.minimum)
        shield = self._shield_value(target)
        breakdown = DamageBreakdown(
            raw=raw,
            hit_chance=hit_chance,
            hit_roll=hit_roll,
            critical_chance=0.0,
            critical_roll=None,
            critical_multiplier=1.0,
            after_critical=0.0,
            defense=0.0,
            effective_defense=0.0,
            defense_multiplier=1.0,
            after_defense=0.0,
            rate_multiplier=1.0,
            after_rates=0.0,
            block_chance=0.0,
            block_roll=None,
            block_reduction=0.0,
            after_block=0.0,
            limited=0.0,
        )
        return DamageResolution(
            request=request,
            hit=False,
            critical=False,
            blocked=False,
            defeated=False,
            shield_broken=False,
            shield_damage=0.0,
            health_damage=0.0,
            overkill=0.0,
            health_before=health,
            health_after=health,
            shield_before=shield,
            shield_after=shield,
            breakdown=breakdown,
            resource_deltas={},
            interceptions=interceptions,
            redirects=(),
        )

    def _intercept(
        self,
        stage: DamageStage,
        frame: DamageFrame,
        request: DamageRequest,
        source: RuleEntity,
        target: RuleEntity,
        context: RuleContext,
    ) -> tuple[DamageFrame, tuple[DamageInterceptionRecord, ...]]:
        if not self.interceptors:
            return frame, ()
        return self.interceptors.apply(
            stage,
            frame,
            request=request,
            source=source,
            target=target,
            context=context,
        )

    def _hit_chance(
        self,
        source: AttributeSnapshot,
        target: AttributeSnapshot,
    ) -> float:
        value = self.rules.base_hit_chance
        value += self._attribute(source, self.stats.accuracy_attribute)
        value -= self._attribute(target, self.stats.evasion_attribute)
        return self._clamp(
            value,
            self.rules.minimum_hit_chance,
            self.rules.maximum_hit_chance,
        )

    def _defense_layer(
        self,
        damage_type: DamageTypeDefinition,
        source: AttributeSnapshot,
        target: AttributeSnapshot,
    ) -> tuple[float, float, float]:
        if damage_type.ignores_defense or not damage_type.defense_attribute:
            return 0.0, 0.0, 1.0
        defense = self._attribute(target, damage_type.defense_attribute)
        rate_penetration = self._clamp(
            self._attribute(source, damage_type.rate_penetration_attribute),
            0.0,
            1.0,
        )
        flat_penetration = self._attribute(source, damage_type.flat_penetration_attribute)
        effective = defense * (1.0 - rate_penetration) - flat_penetration
        constant = self.rules.defense_constant
        if effective >= 0:
            multiplier = constant / (constant + effective)
        else:
            # 负防御平滑转为增伤，并渐近于 2 倍，避免数值越界和奇点。
            multiplier = 2.0 - constant / (constant - effective)
        return defense, effective, multiplier

    def _rate_multiplier(
        self,
        damage_type: DamageTypeDefinition,
        source: AttributeSnapshot,
        target: AttributeSnapshot,
    ) -> float:
        rate = self._attribute(source, self.stats.outgoing_rate_attribute)
        rate += self._attribute(target, self.stats.incoming_rate_attribute)
        rate += self._attribute(source, damage_type.source_rate_attribute)
        rate += self._attribute(target, damage_type.target_rate_attribute)
        multiplier = max(self.rules.minimum_rate_multiplier, 1.0 + rate)
        if self.rules.maximum_rate_multiplier is not None:
            multiplier = min(self.rules.maximum_rate_multiplier, multiplier)
        return multiplier

    def _limit_damage(
        self,
        request: DamageRequest,
        value: float,
        target: AttributeSnapshot,
        *,
        prevented: bool = False,
    ) -> float:
        if prevented:
            return 0.0
        minimum = self.rules.minimum_damage
        if request.minimum_damage is not None:
            minimum = max(minimum, request.minimum_damage)
        maximum = request.maximum_damage
        if request.maximum_target_health_ratio is not None:
            health_definition = self.resources[self.stats.health_resource]
            if health_definition.maximum_attribute:
                ratio_cap = (
                    target.value(health_definition.maximum_attribute)
                    * request.maximum_target_health_ratio
                )
            elif health_definition.fixed_maximum is not None:
                ratio_cap = health_definition.fixed_maximum * request.maximum_target_health_ratio
            else:
                ratio_cap = None
            if ratio_cap is not None:
                maximum = ratio_cap if maximum is None else min(maximum, ratio_cap)
        result = max(minimum, value)
        if maximum is not None:
            result = min(maximum, result)
        return max(0.0, result)

    def _shield_value(self, target: RuleEntity) -> float:
        if not self.stats.shield_resource:
            return 0.0
        definition = self.resources[self.stats.shield_resource]
        return target.resources.get(self.stats.shield_resource, definition.minimum)

    @staticmethod
    def _attribute(
        snapshot: AttributeSnapshot,
        attribute_id: StableId | None,
        default: float = 0.0,
    ) -> float:
        return default if attribute_id is None else snapshot.value(attribute_id)

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        return min(maximum, max(minimum, value))

    def _validate_references(self) -> None:
        for key, definition in self.damage_types.items():
            if key != definition.id:
                raise ValueError(f"伤害类型映射键与 id 不一致：{key} != {definition.id}")
        if self.stats.health_resource not in self.resources:
            raise KeyError(f"战斗血气资源不存在：{self.stats.health_resource}")
        if self.stats.shield_resource and self.stats.shield_resource not in self.resources:
            raise KeyError(f"战斗护盾资源不存在：{self.stats.shield_resource}")
        attribute_ids = set(self.attributes.definitions)
        references = {
            self.stats.accuracy_attribute,
            self.stats.evasion_attribute,
            self.stats.critical_chance_attribute,
            self.stats.critical_damage_attribute,
            self.stats.block_chance_attribute,
            self.stats.block_reduction_attribute,
            self.stats.outgoing_rate_attribute,
            self.stats.incoming_rate_attribute,
        }
        for definition in self.damage_types.values():
            references.update(
                {
                    definition.defense_attribute,
                    definition.flat_penetration_attribute,
                    definition.rate_penetration_attribute,
                    definition.source_rate_attribute,
                    definition.target_rate_attribute,
                }
            )
        unknown = {value for value in references if value and value not in attribute_ids}
        if unknown:
            raise KeyError(f"战斗规则引用未知属性：{', '.join(sorted(unknown))}")
        if self.interceptors:
            for definition in self.interceptors.definitions:
                if definition.handler_id not in {
                    "interceptor.convert",
                    "interceptor.redirect_to_grant_source",
                }:
                    continue
                damage_type = definition.configuration.get("damage_type")
                if damage_type is None and definition.handler_id == "interceptor.redirect_to_grant_source":
                    continue
                if damage_type not in self.damage_types:
                    raise KeyError(
                        f"伤害干预器 {definition.id} 转换到未知伤害类型：{damage_type}"
                    )


__all__ = ["DamageEngine"]
