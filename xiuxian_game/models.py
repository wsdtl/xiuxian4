"""首个可玩闭环需要的玩家档案索引与只读业务视图。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlayerProfileState:
    account_id: str
    character_id: str
    inventory_id: str
    ledger_id: str
    loadout_id: str
    claim_scope_id: str
    starter_weapon_asset_id: str
    created: bool = True
    revision: int = 0

    def __post_init__(self) -> None:
        values = (
            self.account_id,
            self.character_id,
            self.inventory_id,
            self.ledger_id,
            self.loadout_id,
            self.claim_scope_id,
            self.starter_weapon_asset_id,
        )
        if any(not value.strip() for value in values):
            raise ValueError("PlayerProfileState 缺少必要聚合 ID")
        if self.revision < 0:
            raise ValueError("PlayerProfileState.revision 不能小于 0")


@dataclass(frozen=True)
class PendingTrial:
    id: str
    sequence: int
    enemy_id: str
    damage: int
    enemy_health: int
    reward_settlement_id: str

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.enemy_id.strip() or not self.reward_settlement_id.strip():
            raise ValueError("PendingTrial 缺少必要身份")
        if self.sequence < 1 or self.damage < 0 or self.enemy_health < 1:
            raise ValueError("PendingTrial 数值边界无效")


@dataclass(frozen=True)
class EntryResult:
    account_id: str
    created: bool


@dataclass(frozen=True)
class PlayerStatusView:
    account_id: str
    character_id: str
    level: int
    experience: int
    health: int
    maximum_health: int
    spirit: int
    maximum_spirit: int
    stones: int
    herb_quantity: int
    starter_weapon_asset_id: str
    equipped_weapon_asset_id: str | None
    pending_trial: PendingTrial | None


@dataclass(frozen=True)
class TrialResultView:
    pending: PendingTrial
    replayed: bool = False


@dataclass(frozen=True)
class ClaimResultView:
    settlement_id: str
    stones: int
    herb_quantity: int
    experience: int
    replayed: bool = False


@dataclass(frozen=True)
class EquipResultView:
    weapon_asset_id: str
    replayed: bool = False


__all__ = [
    "ClaimResultView",
    "EntryResult",
    "EquipResultView",
    "PendingTrial",
    "PlayerProfileState",
    "PlayerStatusView",
    "TrialResultView",
]
