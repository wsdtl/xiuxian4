"""奖励声明、领取记录、结算快照与结构化凭据。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Mapping, Protocol

from ..character import CharacterState
from ..economy import LedgerState
from ..events import RuleEvent
from ..ids import StableId, stable_id
from ..inventory import InventoryState
from ..weapon import WeaponState


class RewardSpec(Protocol):
    """可以由奖励规划器翻译的声明标记。"""


class DuplicateUnlockPolicy(str, Enum):
    IGNORE = "ignore"
    REJECT = "reject"


class RewardDisposition(str, Enum):
    GRANTED = "granted"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class CurrencyReward:
    issuer_account_id: str
    destination_account_id: str
    amount: int


@dataclass(frozen=True)
class StackItemReward:
    asset_id: str
    definition_id: StableId
    container_id: str
    quantity: int
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "definition_id", stable_id(self.definition_id, field="item id"))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class InstanceItemReward:
    asset_id: str
    definition_id: StableId
    container_id: str
    data: Mapping[str, object] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "definition_id", stable_id(self.definition_id, field="item id"))
        object.__setattr__(self, "data", MappingProxyType(dict(self.data)))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class CharacterExperienceReward:
    character_id: str
    progression_id: StableId
    amount: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "progression_id",
            stable_id(self.progression_id, field="progression id"),
        )


@dataclass(frozen=True)
class CharacterFeatureReward:
    character_id: str
    feature_id: StableId
    duplicate_policy: DuplicateUnlockPolicy = DuplicateUnlockPolicy.IGNORE

    def __post_init__(self) -> None:
        object.__setattr__(self, "feature_id", stable_id(self.feature_id, field="feature id"))
        object.__setattr__(self, "duplicate_policy", DuplicateUnlockPolicy(self.duplicate_policy))


@dataclass(frozen=True)
class CharacterProgressionReward:
    character_id: str
    progression_id: StableId
    duplicate_policy: DuplicateUnlockPolicy = DuplicateUnlockPolicy.IGNORE

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "progression_id",
            stable_id(self.progression_id, field="progression id"),
        )
        object.__setattr__(self, "duplicate_policy", DuplicateUnlockPolicy(self.duplicate_policy))


@dataclass(frozen=True)
class WeaponExperienceReward:
    asset_id: str
    amount: int


@dataclass(frozen=True)
class RewardExpectations:
    """正式提交时必须仍然成立的各领域并发版本。"""

    claim_revision: int
    inventory_revision: int | None = None
    ledger_account_revisions: Mapping[str, int] = field(default_factory=dict)
    character_revisions: Mapping[str, int] = field(default_factory=dict)
    weapon_revisions: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.claim_revision < 0:
            raise ValueError("RewardExpectations.claim_revision 不能小于 0")
        if self.inventory_revision is not None and self.inventory_revision < 0:
            raise ValueError("RewardExpectations.inventory_revision 不能小于 0")
        for field_name in (
            "ledger_account_revisions",
            "character_revisions",
            "weapon_revisions",
        ):
            values = dict(getattr(self, field_name))
            if any(not key.strip() or value < 0 for key, value in values.items()):
                raise ValueError(f"RewardExpectations.{field_name} 无效")
            object.__setattr__(self, field_name, MappingProxyType(values))


@dataclass(frozen=True)
class RewardSettlement:
    """一份业务已经决定好内容和数量的奖励清单。"""

    id: str
    actor_id: str
    claim_scope_id: str
    source_kind: StableId
    source_id: str
    rewards: tuple[RewardSpec, ...]
    expectations: RewardExpectations
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if (
            not self.id.strip()
            or not self.actor_id.strip()
            or not self.claim_scope_id.strip()
            or not self.source_id.strip()
        ):
            raise ValueError("RewardSettlement 缺少必要身份")
        object.__setattr__(self, "source_kind", stable_id(self.source_kind, field="source kind"))
        if not self.rewards:
            raise ValueError("RewardSettlement.rewards 不能为空")
        object.__setattr__(self, "rewards", tuple(self.rewards))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class RewardLine:
    index: int
    kind: StableId
    target_id: str
    subject_id: str
    amount: int | float | None
    disposition: RewardDisposition = RewardDisposition.GRANTED
    details: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.index < 0 or not self.target_id.strip() or not self.subject_id.strip():
            raise ValueError("RewardLine 缺少有效索引或目标")
        object.__setattr__(self, "kind", stable_id(self.kind, field="reward kind"))
        object.__setattr__(self, "disposition", RewardDisposition(self.disposition))
        object.__setattr__(self, "details", MappingProxyType(dict(self.details)))


@dataclass(frozen=True)
class RewardReceipt:
    settlement_id: str
    fingerprint: str
    source_kind: StableId
    source_id: str
    logical_time: datetime
    lines: tuple[RewardLine, ...]
    domain_transaction_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.settlement_id.strip() or not self.fingerprint.strip() or not self.source_id.strip():
            raise ValueError("RewardReceipt 缺少结算身份")
        object.__setattr__(self, "source_kind", stable_id(self.source_kind, field="source kind"))
        if self.logical_time.tzinfo is None or self.logical_time.utcoffset() is None:
            raise ValueError("RewardReceipt.logical_time 必须包含时区")


@dataclass(frozen=True)
class RewardClaimRecord:
    settlement_id: str
    fingerprint: str
    receipt: RewardReceipt
    resulting_revision: int

    def __post_init__(self) -> None:
        if self.settlement_id != self.receipt.settlement_id:
            raise ValueError("RewardClaimRecord 与凭据结算 id 不一致")
        if self.fingerprint != self.receipt.fingerprint or self.resulting_revision < 1:
            raise ValueError("RewardClaimRecord 内容无效")


@dataclass(frozen=True)
class RewardClaimState:
    scope_id: str
    records: Mapping[str, RewardClaimRecord] = field(default_factory=dict)
    revision: int = 0

    def __post_init__(self) -> None:
        records = dict(self.records)
        if not self.scope_id.strip():
            raise ValueError("RewardClaimState 缺少 scope_id")
        if self.revision < 0:
            raise ValueError("RewardClaimState.revision 不能小于 0")
        for key, record in records.items():
            if key != record.settlement_id or record.resulting_revision > self.revision:
                raise ValueError(f"奖励领取记录无效：{key}")
        object.__setattr__(self, "records", MappingProxyType(records))


@dataclass(frozen=True)
class RewardSettlementSnapshot:
    """结算时借用的领域快照，不改变各领域的数据所有权。"""

    inventory: InventoryState
    ledger: LedgerState
    characters: Mapping[str, CharacterState]
    weapons: Mapping[str, WeaponState]
    claims: RewardClaimState

    def __post_init__(self) -> None:
        characters = dict(self.characters)
        weapons = dict(self.weapons)
        for key, value in characters.items():
            if key != value.id:
                raise ValueError(f"角色快照映射键与 id 不一致：{key}")
        for key, value in weapons.items():
            if key != value.asset_id:
                raise ValueError(f"武器快照映射键与 asset_id 不一致：{key}")
        object.__setattr__(self, "characters", MappingProxyType(characters))
        object.__setattr__(self, "weapons", MappingProxyType(weapons))


@dataclass(frozen=True)
class RewardSettlementExecution:
    settlement_id: str
    snapshot: RewardSettlementSnapshot
    receipt: RewardReceipt
    events: tuple[RuleEvent, ...]
    replayed: bool = False
    preview: bool = False


@dataclass(frozen=True)
class RewardSettlementPreview:
    """预检只暴露凭据与事实，避免候选快照被误当成正式结果持久化。"""

    settlement_id: str
    receipt: RewardReceipt
    events: tuple[RuleEvent, ...]
    replayed: bool = False


__all__ = [
    "CharacterExperienceReward",
    "CharacterFeatureReward",
    "CharacterProgressionReward",
    "CurrencyReward",
    "DuplicateUnlockPolicy",
    "InstanceItemReward",
    "RewardClaimRecord",
    "RewardClaimState",
    "RewardDisposition",
    "RewardExpectations",
    "RewardLine",
    "RewardReceipt",
    "RewardSettlement",
    "RewardSettlementExecution",
    "RewardSettlementPreview",
    "RewardSettlementSnapshot",
    "RewardSpec",
    "StackItemReward",
    "WeaponExperienceReward",
]
