"""正式装备实例生成规则。"""

from .generation import (
    EQUIPMENT_GENERATION_PROTOCOL_VERSION,
    EquipmentGenerationRequest,
    EquipmentGenerationResult,
    EquipmentInstanceGenerator,
)
from .guarantees import (
    EQUIPMENT_SET_GUARANTEE_AGGREGATE,
    EquipmentSetGuaranteeState,
    activate_equipment_set_guarantee,
    consume_equipment_set_guarantee,
)


__all__ = [
    "EQUIPMENT_GENERATION_PROTOCOL_VERSION",
    "EquipmentGenerationRequest",
    "EquipmentGenerationResult",
    "EquipmentInstanceGenerator",
    "EQUIPMENT_SET_GUARANTEE_AGGREGATE",
    "EquipmentSetGuaranteeState",
    "activate_equipment_set_guarantee",
    "consume_equipment_set_guarantee",
]
