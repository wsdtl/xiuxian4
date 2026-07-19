"""跃迁业务使用的存储键。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DimensionShiftStorageKinds:
    dimension: str
    action: str
    exploration: str
    inventory: str


__all__ = ["DimensionShiftStorageKinds"]
