"""六槽装备的底座族、随机属性与套装印记底座。"""

EQUIPMENT_FOUNDATION_VERSION = "equipment.foundation.v2"

from .models import (
    EQUIPMENT_STATE_DATA_KEY,
    EquipmentCatalog,
    EquipmentContributionProvider,
    EquipmentDefinition,
    EquipmentFamilyDefinition,
    EquipmentQualityProfile,
    EquipmentSetBonus,
    EquipmentSetDefinition,
    EquipmentState,
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
    "EquipmentFamilyDefinition",
    "EquipmentQualityProfile",
    "EquipmentSetBonus",
    "EquipmentSetDefinition",
    "EquipmentState",
    "equipment_state_data",
    "equipment_state_from_data",
    "equipment_state_from_instance",
]
