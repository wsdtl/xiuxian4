"""协议、存储和具体玩法无关的快速价值评估底座。"""

VALUATION_FOUNDATION_VERSION = "valuation.foundation.v1"

from .engine import ValuationCatalog, ValuationEngine
from .models import (
    AttributeValuationDefinition,
    ReferenceValuationDefinition,
    ReferenceValueKind,
    SynergyValuationDefinition,
    ValuationResult,
    ValueAxis,
    ValueCurvePoint,
    ValueVector,
)

__all__ = [
    "VALUATION_FOUNDATION_VERSION",
    "AttributeValuationDefinition",
    "ReferenceValuationDefinition",
    "ReferenceValueKind",
    "SynergyValuationDefinition",
    "ValuationCatalog",
    "ValuationEngine",
    "ValuationResult",
    "ValueAxis",
    "ValueCurvePoint",
    "ValueVector",
]
