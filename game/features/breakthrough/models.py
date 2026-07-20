"""突破业务的稳定结果和持久化键。"""

from dataclasses import dataclass
from game.core.gameplay import CharacterState, StableId, stable_id


@dataclass(frozen=True)
class BreakthroughReceipt:
    transaction_id: str
    actor_id: str
    item_asset_id: str
    progression_id: StableId
    level_before: int
    level_after: int
    cap_before: int
    cap_after: int
    replayed: bool = False

    def __post_init__(self) -> None:
        for field_name in ("transaction_id", "actor_id", "item_asset_id"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"BreakthroughReceipt 缺少 {field_name}")
        object.__setattr__(
            self,
            "progression_id",
            stable_id(self.progression_id, field="progression id"),
        )
        if self.level_before < 1 or self.level_after <= self.level_before:
            raise ValueError("突破前后等级无效")
        if self.cap_before < self.level_before or self.cap_after <= self.cap_before:
            raise ValueError("突破前后等级上限无效")


@dataclass(frozen=True)
class BreakthroughResult:
    status: str
    character: CharacterState
    receipt: BreakthroughReceipt | None = None
    failure_message: str = ""


@dataclass(frozen=True)
class BreakthroughStorageKinds:
    character: str
    inventory: str


__all__ = [
    "BreakthroughReceipt",
    "BreakthroughResult",
    "BreakthroughStorageKinds",
]
