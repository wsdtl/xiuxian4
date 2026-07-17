"""正式武器实例生成规则。"""

from .generation import (
    WEAPON_GENERATION_PROTOCOL_VERSION,
    WeaponGenerationRequest,
    WeaponGenerationResult,
    WeaponInstanceGenerator,
)


__all__ = [
    "WEAPON_GENERATION_PROTOCOL_VERSION",
    "WeaponGenerationRequest",
    "WeaponGenerationResult",
    "WeaponInstanceGenerator",
]
