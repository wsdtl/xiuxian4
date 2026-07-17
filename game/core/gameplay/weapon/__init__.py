"""单武器槽的品质、等级、经验和核心战斗贡献。"""

WEAPON_FOUNDATION_VERSION = "weapon.foundation.v3"

from .models import (
    WeaponCatalog,
    WeaponDefinition,
    WeaponLevelAttribute,
    WeaponQualityProfile,
    WeaponState,
    WEAPON_STATE_DATA_KEY,
    weapon_state_data,
    weapon_state_from_data,
    weapon_state_from_instance,
    weapon_level_contribution,
)
from .runtime import (
    WeaponContributionProvider,
    WeaponEngine,
    WeaponExecution,
    WeaponExperienceTransaction,
)

__all__ = [
    "WEAPON_FOUNDATION_VERSION",
    "WeaponCatalog",
    "WeaponContributionProvider",
    "WeaponDefinition",
    "WeaponEngine",
    "WeaponExecution",
    "WeaponExperienceTransaction",
    "WeaponLevelAttribute",
    "WeaponQualityProfile",
    "WeaponState",
    "WEAPON_STATE_DATA_KEY",
    "weapon_state_data",
    "weapon_state_from_data",
    "weapon_state_from_instance",
    "weapon_level_contribution",
]
