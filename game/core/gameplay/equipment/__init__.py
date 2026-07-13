"""六槽装备的流派与品质底座。"""

EQUIPMENT_FOUNDATION_VERSION = "equipment.foundation.v1"

from .models import (
    EquipmentCatalog,
    EquipmentContributionProvider,
    EquipmentDefinition,
    EquipmentQualityProfile,
    EquipmentState,
    EquipmentStyleDefinition,
)

__all__ = [
    "EQUIPMENT_FOUNDATION_VERSION",
    "EquipmentCatalog",
    "EquipmentContributionProvider",
    "EquipmentDefinition",
    "EquipmentQualityProfile",
    "EquipmentState",
    "EquipmentStyleDefinition",
]
