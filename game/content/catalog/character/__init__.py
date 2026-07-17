"""人物与成长名录的稳定入口。"""

from .definitions import (
    BASIC_COMBAT_FEATURE_ID,
    CHARACTER_LEVEL_EXPERIENCE_REQUIREMENTS,
    CHARACTER_LEVEL_PROGRESSION_ID,
    DEFAULT_CHARACTER_TEMPLATE_ID,
    MORTAL_PHYSIQUE_FEATURE_ID,
    ORIGIN_HUMAN_FEATURE_ID,
)
from .realms import (
    CHARACTER_REALMS,
    CHARACTER_REALM_CONTENT_DEFINITIONS,
    CHARACTER_REALM_DISPLAY_IDS,
    CharacterRealmDefinition,
    character_realm_for_level,
)


__all__ = [name for name in globals() if not name.startswith("_")]
