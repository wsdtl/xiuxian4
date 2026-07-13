"""快速内在价值、整套价值和边际价值估算。"""

from __future__ import annotations

from collections import defaultdict
from math import isfinite
from types import MappingProxyType

from ..character import ContributionSpec
from ..tags import EMPTY_TAGS
from .models import (
    AttributeValuationDefinition,
    ReferenceValuationDefinition,
    ReferenceValueKind,
    SynergyValuationDefinition,
    ValuationResult,
    ValueVector,
)


class ValuationCatalog:
    def __init__(self) -> None:
        self.attributes: dict[tuple[str, object], AttributeValuationDefinition] = {}
        self.references: dict[tuple[ReferenceValueKind, str], ReferenceValuationDefinition] = {}
        self.synergies: dict[str, SynergyValuationDefinition] = {}
        self._finalized = False

    def register_attribute(self, definition: AttributeValuationDefinition) -> None:
        self._register(self.attributes, definition.key, definition, "属性价值")

    def register_reference(self, definition: ReferenceValuationDefinition) -> None:
        self._register(self.references, definition.key, definition, "机制价值")

    def register_synergy(self, definition: SynergyValuationDefinition) -> None:
        self._register(self.synergies, definition.id, definition, "协同价值")

    def finalize(self) -> None:
        if self._finalized:
            return
        self.attributes = MappingProxyType(dict(self.attributes))
        self.references = MappingProxyType(dict(self.references))
        self.synergies = MappingProxyType(dict(self.synergies))
        self._finalized = True

    @property
    def finalized(self) -> bool:
        return self._finalized

    def _register(self, target, key, definition, label) -> None:
        if self._finalized:
            raise RuntimeError("价值目录已经冻结")
        if key in target:
            raise ValueError(f"{label}重复：{key}")
        target[key] = definition


class ValuationEngine:
    def __init__(self, catalog: ValuationCatalog) -> None:
        if not catalog.finalized:
            catalog.finalize()
        self.catalog = catalog

    def evaluate(
        self,
        *specs: ContributionSpec,
        strict: bool = True,
    ) -> ValuationResult:
        attribute_values = defaultdict(float)
        tags = EMPTY_TAGS
        abilities: set[str] = set()
        triggers: set[str] = set()
        interceptors: set[str] = set()
        constraints: set[str] = set()
        for spec in specs:
            tags = tags.merged(spec.tags)
            abilities.update(spec.abilities)
            triggers.update(spec.triggers)
            interceptors.update(spec.interceptors)
            constraints.update(spec.target_constraints)
            for grant in spec.attributes:
                attribute_values[(grant.attribute_id, grant.layer)] += grant.value

        value = ValueVector()
        unvalued: list[str] = []
        for key, amount in sorted(attribute_values.items(), key=lambda item: (item[0][0], item[0][1].value)):
            if not isfinite(amount):
                raise ValueError(f"属性价值输入必须是有限数：{key[0]}:{key[1].value}")
            definition = self.catalog.attributes.get(key)
            if definition is None:
                unvalued.append(f"attribute:{key[0]}:{key[1].value}")
                continue
            points = _curve_value(definition, amount)
            value += ValueVector.on_axis(definition.axis, points)

        references = (
            (ReferenceValueKind.ABILITY, abilities),
            (ReferenceValueKind.TRIGGER, triggers),
            (ReferenceValueKind.INTERCEPTOR, interceptors),
            (ReferenceValueKind.TARGET_CONSTRAINT, constraints),
            (ReferenceValueKind.TAG, set(tags.strings())),
        )
        for kind, identifiers in references:
            for identifier in sorted(identifiers):
                definition = self.catalog.references.get((kind, identifier))
                if definition is None:
                    if kind is not ReferenceValueKind.TAG:
                        unvalued.append(f"{kind.value}:{identifier}")
                    continue
                value += definition.value

        for definition in self.catalog.synergies.values():
            if tags.allows(
                required=definition.required_tags,
                blocked=definition.blocked_tags,
            ):
                value += definition.value

        if strict and unvalued:
            raise ValueError("存在未登记价值的贡献：" + ", ".join(unvalued))
        return ValuationResult(value, tuple(unvalued))

    def marginal(
        self,
        base: tuple[ContributionSpec, ...],
        added: tuple[ContributionSpec, ...],
        *,
        strict: bool = True,
    ) -> ValuationResult:
        before = self.evaluate(*base, strict=strict)
        after = self.evaluate(*base, *added, strict=strict)
        return ValuationResult(
            after.value - before.value,
            tuple(sorted(set(before.unvalued) | set(after.unvalued))),
        )


def _curve_value(definition: AttributeValuationDefinition, amount: float) -> float:
    points = definition.curve
    if amount <= points[0].input_value:
        return points[0].points
    if amount >= points[-1].input_value:
        return points[-1].points
    for left, right in zip(points, points[1:]):
        if left.input_value <= amount <= right.input_value:
            ratio = (amount - left.input_value) / (right.input_value - left.input_value)
            return left.points + (right.points - left.points) * ratio
    raise AssertionError("价值曲线区间不完整")


__all__ = ["ValuationCatalog", "ValuationEngine"]
