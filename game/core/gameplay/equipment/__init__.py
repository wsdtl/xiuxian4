"""六槽装备的流派与品质底座。"""

EQUIPMENT_FOUNDATION_VERSION = "equipment.foundation.v1"

from .models import (
    EQUIPMENT_STATE_DATA_KEY,
    EquipmentCatalog,
    EquipmentContributionProvider,
    EquipmentDefinition,
    EquipmentQualityProfile,
    EquipmentSetBonus,
    EquipmentSetDefinition,
    EquipmentState,
    EquipmentStyleDefinition,
    equipment_state_data,
    equipment_state_from_data,
    equipment_state_from_instance,
)

__all__ = [
    "EQUIPMENT_FOUNDATION_VERSION",
    "EQUIPMENT_STATE_DATA_KEY",
    "EquipmentCatalog",
    "EquipmentContributionProvider",
    "EquipmentDefinition",
    "EquipmentQualityProfile",
    "EquipmentSetBonus",
    "EquipmentSetDefinition",
    "EquipmentState",
    "EquipmentStyleDefinition",
    "equipment_state_data",
    "equipment_state_from_data",
    "equipment_state_from_instance",
]
