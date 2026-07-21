"""跃迁业务使用的存储键。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DimensionShiftStorageKinds:
    character_world: str
    world: str
    action: str
    exploration: str
    inventory: str


__all__ = ["DimensionShiftStorageKinds"]
