"""当前正式内容使用到的最小价值基线。"""

from game.core.gameplay import (
    COMBAT_ATTACK,
    AttributeValuationDefinition,
    ModifierLayer,
    ReferenceValuationDefinition,
    ReferenceValueKind,
    ValueAxis,
    ValueCurvePoint,
    ValueVector,
)

from .combat import BREAKING_STRIKE_ABILITY_ID


BASE_ATTRIBUTE_VALUATIONS = (
    AttributeValuationDefinition(
        COMBAT_ATTACK,
        ModifierLayer.LOCAL_FLAT,
        ValueAxis.OFFENSE,
        (
            ValueCurvePoint(0, 0),
            ValueCurvePoint(100, 100),
        ),
    ),
)

BASE_REFERENCE_VALUATIONS = (
    ReferenceValuationDefinition(
        ReferenceValueKind.ABILITY,
        BREAKING_STRIKE_ABILITY_ID,
        ValueVector(offense=8, tempo=2),
    ),
)


__all__ = ["BASE_ATTRIBUTE_VALUATIONS", "BASE_REFERENCE_VALUATIONS"]
