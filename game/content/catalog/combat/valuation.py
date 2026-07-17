"""当前正式内容使用到的最小价值基线。"""

from game.core.gameplay import (
    COMBAT_ATTACK,
    COMBAT_DEFENSE,
    COMBAT_SPEED,
    HEALTH_MAXIMUM,
    SPIRIT_MAXIMUM,
    AttributeValuationDefinition,
    ModifierLayer,
    ReferenceValuationDefinition,
    ReferenceValueKind,
    ValueAxis,
    ValueCurvePoint,
    ValueVector,
)

from .definitions import BREAKING_STRIKE_ABILITY_ID
from .stats import (
    COMBAT_ACCURACY,
    COMBAT_BLOCK_CHANCE,
    COMBAT_BLOCK_REDUCTION,
    COMBAT_CONTROL_CHANCE,
    COMBAT_CRITICAL_CHANCE,
    COMBAT_CRITICAL_DAMAGE,
    COMBAT_EVASION,
    COMBAT_FLAT_PENETRATION,
    COMBAT_HEALING_RATE,
    COMBAT_HEALING_RECEIVED,
    COMBAT_INCOMING_RATE,
    COMBAT_OUTGOING_RATE,
    COMBAT_RATE_PENETRATION,
    COMBAT_TENACITY,
    COMBAT_CONTROL_RESISTANCE,
)


def _curve(attribute_id, axis, points):
    return AttributeValuationDefinition(
        attribute_id,
        ModifierLayer.GLOBAL_FLAT,
        axis,
        tuple(ValueCurvePoint(value, score) for value, score in points),
    )


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
    AttributeValuationDefinition(
        COMBAT_DEFENSE,
        ModifierLayer.LOCAL_FLAT,
        ValueAxis.SURVIVAL,
        (ValueCurvePoint(0, 0), ValueCurvePoint(25, 22), ValueCurvePoint(60, 42)),
    ),
    AttributeValuationDefinition(
        COMBAT_SPEED,
        ModifierLayer.LOCAL_FLAT,
        ValueAxis.TEMPO,
        (ValueCurvePoint(0, 0), ValueCurvePoint(20, 20), ValueCurvePoint(50, 36)),
    ),
    AttributeValuationDefinition(
        HEALTH_MAXIMUM,
        ModifierLayer.LOCAL_FLAT,
        ValueAxis.SURVIVAL,
        (
            ValueCurvePoint(0, 0),
            ValueCurvePoint(100, 15),
            ValueCurvePoint(300, 35),
            ValueCurvePoint(800, 60),
        ),
    ),
    AttributeValuationDefinition(
        SPIRIT_MAXIMUM,
        ModifierLayer.LOCAL_FLAT,
        ValueAxis.SUSTAIN,
        (
            ValueCurvePoint(0, 0),
            ValueCurvePoint(50, 12),
            ValueCurvePoint(150, 28),
            ValueCurvePoint(400, 48),
        ),
    ),
    _curve(COMBAT_ACCURACY, ValueAxis.OFFENSE, ((0, 0), (0.15, 22), (0.40, 40))),
    _curve(COMBAT_EVASION, ValueAxis.SURVIVAL, ((0, 0), (0.15, 24), (0.40, 48))),
    _curve(COMBAT_CRITICAL_CHANCE, ValueAxis.OFFENSE, ((0, 0), (0.15, 25), (0.40, 55))),
    _curve(COMBAT_CRITICAL_DAMAGE, ValueAxis.OFFENSE, ((0, 0), (0.30, 22), (1.00, 55))),
    _curve(COMBAT_BLOCK_CHANCE, ValueAxis.SURVIVAL, ((0, 0), (0.15, 22), (0.40, 50))),
    _curve(COMBAT_BLOCK_REDUCTION, ValueAxis.SURVIVAL, ((0, 0), (0.25, 18), (0.70, 42))),
    _curve(COMBAT_OUTGOING_RATE, ValueAxis.OFFENSE, ((0, 0), (0.15, 28), (0.50, 70))),
    _curve(COMBAT_INCOMING_RATE, ValueAxis.SURVIVAL, ((-0.50, 70), (-0.20, 35), (-0.10, 18), (0, 0))),
    _curve(COMBAT_FLAT_PENETRATION, ValueAxis.OFFENSE, ((0, 0), (20, 20), (60, 45))),
    _curve(COMBAT_RATE_PENETRATION, ValueAxis.OFFENSE, ((0, 0), (0.15, 22), (0.50, 55))),
    _curve(COMBAT_HEALING_RATE, ValueAxis.SUSTAIN, ((0, 0), (0.20, 22), (0.60, 55))),
    _curve(COMBAT_HEALING_RECEIVED, ValueAxis.SUSTAIN, ((0, 0), (0.20, 18), (0.60, 45))),
    _curve(COMBAT_CONTROL_CHANCE, ValueAxis.CONTROL, ((0, 0), (0.15, 25), (0.40, 55))),
    _curve(COMBAT_CONTROL_RESISTANCE, ValueAxis.SURVIVAL, ((0, 0), (0.15, 22), (0.40, 52))),
    _curve(COMBAT_TENACITY, ValueAxis.SURVIVAL, ((0, 0), (0.15, 18), (0.50, 48))),
)

BASE_REFERENCE_VALUATIONS = (
    ReferenceValuationDefinition(
        ReferenceValueKind.ABILITY,
        BREAKING_STRIKE_ABILITY_ID,
        ValueVector(offense=8, tempo=2),
    ),
)


__all__ = ["BASE_ATTRIBUTE_VALUATIONS", "BASE_REFERENCE_VALUATIONS"]
