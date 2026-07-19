"""角色创世、成长和恢复规则。"""

from .identity import (
    CharacterIdentityPolicy,
    CharacterIdentityViolation,
    CharacterNameSource,
    PreparedCharacterIdentity,
    validate_character_name,
)
from .settings import (
    CharacterSettingsState,
)
from .dimension import (
    CHARACTER_DIMENSION_AGGREGATE,
    CHARACTER_DIMENSION_RULE_VERSION,
    CharacterDimensionState,
    DimensionShiftResult,
    assign_initial_dimension,
    shift_dimension,
)
from .creation import (
    CHARACTER_CREATION_PROTOCOL_VERSION,
    CHARACTER_SETTINGS_AGGREGATE,
    CharacterCreationIds,
    CharacterCreationPlan,
    CharacterCreationPlanner,
    CharacterCreationReceipt,
    CharacterCreationRequest,
    CharacterCreationViolation,
    CharacterCreationWorkflow,
    character_creation_context,
    PRIMARY_ISSUER_ACCOUNT_ID,
    PRIMARY_LEDGER_ID,
    PRIMARY_WORLD_ID,
)
from .loadout import equipped_character_contributions


__all__ = [
    "CHARACTER_CREATION_PROTOCOL_VERSION",
    "CHARACTER_DIMENSION_AGGREGATE",
    "CHARACTER_DIMENSION_RULE_VERSION",
    "CHARACTER_SETTINGS_AGGREGATE",
    "CharacterIdentityPolicy",
    "CharacterDimensionState",
    "CharacterCreationIds",
    "CharacterCreationPlan",
    "CharacterCreationPlanner",
    "CharacterCreationReceipt",
    "CharacterCreationRequest",
    "CharacterCreationViolation",
    "CharacterCreationWorkflow",
    "character_creation_context",
    "CharacterIdentityViolation",
    "CharacterNameSource",
    "CharacterSettingsState",
    "DimensionShiftResult",
    "PRIMARY_ISSUER_ACCOUNT_ID",
    "PRIMARY_LEDGER_ID",
    "PRIMARY_WORLD_ID",
    "PreparedCharacterIdentity",
    "validate_character_name",
    "equipped_character_contributions",
    "assign_initial_dimension",
    "shift_dimension",
]
