"""首个可玩闭环需要的玩家档案索引与只读业务视图。"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping


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


@dataclass(frozen=True)
class UsableItemView:
    definition_id: str
    ability_id: str
    quantity: int
    available_quantity: int
    asset_count: int

    def __post_init__(self) -> None:
        if not self.definition_id.strip() or not self.ability_id.strip():
            raise ValueError("UsableItemView 缺少稳定内容 ID")
        if min(self.quantity, self.available_quantity, self.asset_count) < 0:
            raise ValueError("UsableItemView 数量不能小于 0")
        if self.available_quantity > self.quantity:
            raise ValueError("UsableItemView 可用数量不能大于总数量")


@dataclass(frozen=True)
class ItemUseResultView:
    transaction_id: str
    item_definition_id: str
    ability_id: str
    actor_character_id: str
    target_character_id: str
    consumed_quantity: int
    resource_changes: Mapping[str, Mapping[str, float]] = field(default_factory=dict)
    replayed: bool = False

    def __post_init__(self) -> None:
        values = (
            self.transaction_id,
            self.item_definition_id,
            self.ability_id,
            self.actor_character_id,
            self.target_character_id,
        )
        if any(not value.strip() for value in values):
            raise ValueError("ItemUseResultView 缺少必要稳定 ID")
        if self.consumed_quantity < 0:
            raise ValueError("ItemUseResultView.consumed_quantity 不能小于 0")
        object.__setattr__(
            self,
            "resource_changes",
            MappingProxyType(
                {
                    character_id: MappingProxyType(
                        {resource_id: float(delta) for resource_id, delta in changes.items()}
                    )
                    for character_id, changes in self.resource_changes.items()
                }
            ),
        )


__all__ = [
    "ClaimResultView",
    "EntryResult",
    "EquipResultView",
    "ItemUseResultView",
    "PendingTrial",
    "PlayerProfileState",
    "PlayerStatusView",
    "TrialResultView",
    "UsableItemView",
]
