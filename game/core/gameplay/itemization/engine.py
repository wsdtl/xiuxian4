"""受约束武器与开放装备共用的确定性随机生成器。"""

from __future__ import annotations

from math import isclose, isfinite
from types import MappingProxyType

from ..character import AttributeGrant, ContributionSpec, merge_contribution_specs
from ..context import RuleContext
from ..tags import EMPTY_TAGS
from ..valuation import ValuationEngine
from .models import (
    GenerationDecision,
    GenerationProfileDefinition,
    GenerationReceipt,
    ItemGenerationCommand,
    ItemGenerationExecution,
    ItemRollState,
    ItemizationKind,
    PropertyDefinition,
    PropertyTierDefinition,
    RolledProperty,
)


GENERATOR_VERSION = "itemization.generator.v1"


class _GenerationRejected(Exception):
    """当前随机组合不可用，但内容定义本身仍可能生成合法结果。"""


class ItemizationCatalog:
    def __init__(self) -> None:
        self.properties: dict[str, PropertyDefinition] = {}
        self.profiles: dict[str, GenerationProfileDefinition] = {}
        self._finalized = False

    def register_property(self, definition: PropertyDefinition) -> None:
        self._register(self.properties, definition.id, definition, "随机属性")

    def register_profile(self, definition: GenerationProfileDefinition) -> None:
        self._register(self.profiles, definition.id, definition, "生成策略")

    def finalize(self) -> None:
        if self._finalized:
            return
        for profile in self.profiles.values():
            unknown = set(profile.property_ids) - set(self.properties)
            if unknown:
                raise KeyError(
                    f"生成策略 {profile.id} 引用了未知属性：{', '.join(sorted(unknown))}"
                )
        self.properties = MappingProxyType(dict(self.properties))
        self.profiles = MappingProxyType(dict(self.profiles))
        self._finalized = True

    @property
    def finalized(self) -> bool:
        return self._finalized

    def require_property(self, property_id: str) -> PropertyDefinition:
        try:
            return self.properties[property_id]
        except KeyError as exc:
            raise KeyError(f"未知随机属性：{property_id}") from exc

    def require_profile(self, profile_id: str) -> GenerationProfileDefinition:
        try:
            return self.profiles[profile_id]
        except KeyError as exc:
            raise KeyError(f"未知生成策略：{profile_id}") from exc

    def _register(self, target, key, definition, label) -> None:
        if self._finalized:
            raise RuntimeError("物品化目录已经冻结")
        if key in target:
            raise ValueError(f"{label}重复：{key}")
        target[key] = definition


class ItemizationEngine:
    def __init__(self, catalog: ItemizationCatalog, valuation: ValuationEngine) -> None:
        if not catalog.finalized:
            catalog.finalize()
        self.catalog = catalog
        self.valuation = valuation

    def generate(
        self,
        command: ItemGenerationCommand,
        *,
        context: RuleContext,
    ) -> ItemGenerationExecution:
        checkpoint = context.random.checkpoint()
        profile = self.catalog.require_profile(command.profile_id)
        try:
            for attempt in range(1, profile.maximum_attempts + 1):
                try:
                    properties = self._generate_properties(profile, context)
                except _GenerationRejected:
                    continue
                contribution = self.resolve(properties)
                value = self.valuation.evaluate(contribution, strict=True).value
                quality = next(
                    (
                        band.quality_id
                        for band in profile.quality_bands
                        if band.contains(value.total)
                    ),
                    None,
                )
                if quality is None:
                    continue
                decisions = tuple(
                    GenerationDecision(index, item.property_id, item.tier, item.values)
                    for index, item in enumerate(properties)
                )
                receipt = GenerationReceipt(
                    command.id,
                    profile.id,
                    GENERATOR_VERSION,
                    command.content_fingerprint,
                    context.trace_id,
                    context.logical_time,
                    attempt,
                    decisions,
                )
                return ItemGenerationExecution(
                    ItemRollState(profile.id, quality, properties, value, receipt),
                    contribution,
                )
        except Exception:
            context.random.restore(checkpoint)
            raise
        context.random.restore(checkpoint)
        raise ValueError(f"生成策略在最大尝试次数内无法产生合法品质：{profile.id}")

    def resolve(self, properties: tuple[RolledProperty, ...]) -> ContributionSpec:
        specs = []
        for rolled in properties:
            definition = self.catalog.require_property(rolled.property_id)
            tier = _tier(definition, rolled.tier)
            expected = {parameter.id for parameter in tier.parameters}
            if set(rolled.values) != expected:
                raise ValueError(f"随机属性参数与定义不一致：{rolled.property_id}")
            grants = []
            for parameter in tier.parameters:
                value = rolled.values[parameter.id]
                if not _valid_parameter_roll(parameter.minimum, parameter.maximum, parameter.step, value):
                    raise ValueError(f"随机属性参数越界：{rolled.property_id}/{parameter.id}")
                grants.append(
                    AttributeGrant(
                        parameter.attribute_id,
                        parameter.layer,
                        value,
                        priority=parameter.priority,
                    )
                )
            specs.append(
                merge_contribution_specs(
                    tier.contribution,
                    ContributionSpec(attributes=tuple(grants), tags=definition.tags),
                )
            )
        return merge_contribution_specs(*specs)

    def validate_roll(self, roll: ItemRollState) -> ContributionSpec:
        profile = self.catalog.require_profile(roll.profile_id)
        if roll.receipt.generator_version != GENERATOR_VERSION:
            raise ValueError("生成物品使用了不受支持的生成器版本")
        if roll.receipt.attempts > profile.maximum_attempts:
            raise ValueError("生成物品凭据尝试次数超过策略上限")
        if not profile.minimum_properties <= len(roll.properties) <= profile.maximum_properties:
            raise ValueError("生成物品属性数量不符合策略")
        if any(value.property_id not in profile.property_ids for value in roll.properties):
            raise ValueError("生成物品包含策略外属性")
        expected_decisions = tuple(
            GenerationDecision(index, item.property_id, item.tier, item.values)
            for index, item in enumerate(roll.properties)
        )
        if roll.receipt.decisions != expected_decisions:
            raise ValueError("生成物品属性与保存的判定凭据不一致")
        definitions = tuple(
            self.catalog.require_property(value.property_id)
            for value in roll.properties
        )
        if profile.kind is ItemizationKind.WEAPON:
            if definitions[0].id not in profile.core_property_ids or any(
                value.id in profile.core_property_ids for value in definitions[1:]
            ):
                raise ValueError("生成武器必须且只能以一个流派核心开头")
        if profile.enforce_compatibility:
            selected: list[PropertyDefinition] = []
            selected_tags = EMPTY_TAGS
            for definition in definitions:
                if selected and not _compatible(definition, selected, selected_tags):
                    raise ValueError("生成物品包含不兼容属性组合")
                selected.append(definition)
                selected_tags = selected_tags.merged(definition.tags)
        contribution = self.resolve(roll.properties)
        actual = self.valuation.evaluate(contribution, strict=True).value
        if not _same_value_vector(actual, roll.intrinsic_value):
            raise ValueError("生成物品价值与当前内容定义不一致")
        band = next(
            (value for value in profile.quality_bands if value.quality_id == roll.quality_id),
            None,
        )
        if band is None:
            raise ValueError(f"生成物品品质不属于策略：{roll.quality_id}")
        if not band.contains(actual.total):
            raise ValueError("生成物品价值不属于保存的品质区间")
        return contribution

    def _generate_properties(
        self,
        profile: GenerationProfileDefinition,
        context: RuleContext,
    ) -> tuple[RolledProperty, ...]:
        target_count = context.random.randint(
            profile.minimum_properties,
            profile.maximum_properties,
        )
        selected: list[PropertyDefinition] = []
        selected_tags = EMPTY_TAGS
        if profile.kind is ItemizationKind.WEAPON:
            core_candidates = [
                self.catalog.require_property(value)
                for value in sorted(profile.core_property_ids)
            ]
            core = _weighted_choice(core_candidates, context)
            selected.append(core)
            selected_tags = selected_tags.merged(core.tags)

        while len(selected) < target_count:
            candidates = [
                self.catalog.require_property(value)
                for value in sorted(profile.property_ids)
                if value not in {item.id for item in selected}
                and not (
                    profile.kind is ItemizationKind.WEAPON
                    and value in profile.core_property_ids
                )
            ]
            if profile.enforce_compatibility:
                candidates = [
                    candidate
                    for candidate in candidates
                    if _compatible(candidate, selected, selected_tags)
                ]
            if not candidates:
                raise _GenerationRejected
            chosen = _weighted_choice(candidates, context)
            selected.append(chosen)
            selected_tags = selected_tags.merged(chosen.tags)

        result = []
        for definition in selected:
            tier = _weighted_choice(list(definition.tiers), context)
            values = {
                parameter.id: _roll_parameter(parameter, context)
                for parameter in tier.parameters
            }
            result.append(RolledProperty(definition.id, tier.tier, values))
        return tuple(result)


def _compatible(candidate, selected, selected_tags) -> bool:
    if not selected_tags.allows(
        required=candidate.required_selected_tags,
        blocked=candidate.blocked_selected_tags,
    ):
        return False
    return all(
        candidate.tags.allows(blocked=existing.blocked_selected_tags)
        for existing in selected
    )


def _weighted_choice(values, context):
    total = sum(value.weight for value in values)
    sampled = context.random.randint(1, total)
    cursor = 0
    for value in values:
        cursor += value.weight
        if sampled <= cursor:
            return value
    return values[-1]


def _tier(definition: PropertyDefinition, tier_number: int) -> PropertyTierDefinition:
    try:
        return next(value for value in definition.tiers if value.tier == tier_number)
    except StopIteration as exc:
        raise ValueError(f"随机属性档位不存在：{definition.id}/{tier_number}") from exc


def _roll_parameter(parameter, context) -> float:
    steps = round((parameter.maximum - parameter.minimum) / parameter.step)
    return parameter.minimum + context.random.randint(0, steps) * parameter.step


def _valid_parameter_roll(minimum, maximum, step, value) -> bool:
    if not isfinite(value):
        return False
    if not minimum <= value <= maximum:
        return False
    steps = (value - minimum) / step
    return abs(steps - round(steps)) <= 1e-9


def _same_value_vector(left, right) -> bool:
    return all(
        isclose(getattr(left, field), getattr(right, field), rel_tol=1e-12, abs_tol=1e-9)
        for field in ("offense", "survival", "sustain", "tempo", "control", "volatility")
    )


__all__ = ["GENERATOR_VERSION", "ItemizationCatalog", "ItemizationEngine"]
