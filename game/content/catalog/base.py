"""完整内容运行期必须具备的最小稳定定义。"""

from game.core.gameplay import (
    CombatProfileDefinition,
    CombatStats,
    CurrencyDefinition,
    QualityDefinition,
    RecoveryStats,
    core_attribute_definitions,
    persistent_resource_definitions,
)


PRIMARY_CURRENCY_ID = "currency.primary"
COMMON_QUALITY_ID = "quality.common"
STANDARD_COMBAT_PROFILE_ID = "combat_profile.standard"

BASE_CURRENCIES = (CurrencyDefinition(PRIMARY_CURRENCY_ID),)
BASE_QUALITIES = (QualityDefinition(COMMON_QUALITY_ID, 0),)
BASE_ATTRIBUTES = tuple(core_attribute_definitions().values())
BASE_RESOURCES = tuple(persistent_resource_definitions().values())
BASE_COMBAT_PROFILES = (
    CombatProfileDefinition(
        id=STANDARD_COMBAT_PROFILE_ID,
        combat_stats=CombatStats("health.current"),
        recovery_stats=RecoveryStats("health.current"),
    ),
)
BASE_DISPLAY_CONTENT_IDS = frozenset({PRIMARY_CURRENCY_ID, COMMON_QUALITY_ID})


__all__ = [
    "BASE_ATTRIBUTES",
    "BASE_COMBAT_PROFILES",
    "BASE_CURRENCIES",
    "BASE_DISPLAY_CONTENT_IDS",
    "BASE_QUALITIES",
    "BASE_RESOURCES",
    "COMMON_QUALITY_ID",
    "PRIMARY_CURRENCY_ID",
    "STANDARD_COMBAT_PROFILE_ID",
]
