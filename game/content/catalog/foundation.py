"""完整内容运行期必须具备的最小稳定定义。"""

from game.core.gameplay import (
    CurrencyDefinition,
    QualityDefinition,
    core_attribute_definitions,
    persistent_resource_definitions,
)

from .combat.stats import (
    BASE_COMBAT_PROFILES,
    BATTLE_RESOURCES,
    DERIVED_COMBAT_ATTRIBUTES,
    STANDARD_COMBAT_PROFILE_ID,
)


PRIMARY_CURRENCY_ID = "currency.primary"
COMMON_QUALITY_ID = "quality.common"
FINE_QUALITY_ID = "quality.fine"
RARE_QUALITY_ID = "quality.rare"
EPIC_QUALITY_ID = "quality.epic"
LEGENDARY_QUALITY_ID = "quality.legendary"

BASE_CURRENCIES = (CurrencyDefinition(PRIMARY_CURRENCY_ID),)
BASE_QUALITIES = (
    QualityDefinition(COMMON_QUALITY_ID, 0),
    QualityDefinition(FINE_QUALITY_ID, 1),
    QualityDefinition(RARE_QUALITY_ID, 2),
    QualityDefinition(EPIC_QUALITY_ID, 3),
    QualityDefinition(LEGENDARY_QUALITY_ID, 4),
)
BASE_ATTRIBUTES = (*core_attribute_definitions().values(), *DERIVED_COMBAT_ATTRIBUTES)
BASE_RESOURCES = (*persistent_resource_definitions().values(), *BATTLE_RESOURCES)
QUALITY_IDS = tuple(definition.id for definition in BASE_QUALITIES)
BASE_DISPLAY_CONTENT_IDS = frozenset({PRIMARY_CURRENCY_ID, *QUALITY_IDS})


__all__ = [
    "BASE_ATTRIBUTES",
    "BASE_COMBAT_PROFILES",
    "BASE_CURRENCIES",
    "BASE_DISPLAY_CONTENT_IDS",
    "BASE_QUALITIES",
    "BASE_RESOURCES",
    "COMMON_QUALITY_ID",
    "EPIC_QUALITY_ID",
    "FINE_QUALITY_ID",
    "LEGENDARY_QUALITY_ID",
    "PRIMARY_CURRENCY_ID",
    "QUALITY_IDS",
    "RARE_QUALITY_ID",
    "STANDARD_COMBAT_PROFILE_ID",
]
