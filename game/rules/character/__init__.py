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
    CHARACTER_WORLD_AGGREGATE,
    CHARACTER_WORLD_RULE_VERSION,
    CharacterWorldState,
    WorldShiftResult,
    assign_initial_world,
    shift_world,
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
    MULTIVERSE_WORLD_STATE_ID,
)
from .loadout import equipped_character_contributions


__all__ = [
    "CHARACTER_CREATION_PROTOCOL_VERSION",
    "CHARACTER_WORLD_AGGREGATE",
    "CHARACTER_WORLD_RULE_VERSION",
    "CHARACTER_SETTINGS_AGGREGATE",
    "CharacterIdentityPolicy",
    "CharacterWorldState",
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
    "WorldShiftResult",
    "PRIMARY_ISSUER_ACCOUNT_ID",
    "PRIMARY_LEDGER_ID",
    "MULTIVERSE_WORLD_STATE_ID",
    "PreparedCharacterIdentity",
    "validate_character_name",
    "equipped_character_contributions",
    "assign_initial_world",
    "shift_world",
]
