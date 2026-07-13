"""权益活动、凭证、领取资格、迁移清单与兑付凭据。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from ..ids import StableId, stable_id
from ..rewards import (
    RewardExpectations,
    RewardReceipt,
    RewardSettlementExecution,
    RewardSpec,
)


class GrantCampaignStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    REVOKED = "revoked"


class GrantRedemptionPolicy(str, Enum):
    SINGLE_USE = "single_use"
    PER_ACCOUNT = "per_account"
    QUOTA = "quota"


class GrantCredentialKind(str, Enum):
    CODE = "code"
    SIGNED_RECEIPT = "signed_receipt"


class GrantCredentialStatus(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"


class GrantEntitlementStatus(str, Enum):
    AVAILABLE = "available"
    REDEEMED = "redeemed"
    REVOKED = "revoked"


@dataclass(frozen=True)
class GrantCampaign:
    id: str
    version: int
    issuer_id: str
    source_kind: StableId
    offer_id: StableId
    offer_version: int
    policy: GrantRedemptionPolicy
    per_account_limit: int
    total_limit: int | None
    starts_at: datetime
    ends_at: datetime | None = None
    status: GrantCampaignStatus = GrantCampaignStatus.ACTIVE
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("id", "issuer_id"):
            if not str(getattr(self, name) or "").strip():
                raise ValueError(f"GrantCampaign 缺少 {name}")
        if self.version < 1 or self.offer_version < 1 or self.per_account_limit < 1:
            raise ValueError("GrantCampaign 版本和账号额度必须大于 0")
        if self.total_limit is not None and self.total_limit < 1:
            raise ValueError("GrantCampaign.total_limit 必须大于 0")
        _require_aware(self.starts_at, "GrantCampaign.starts_at")
        if self.ends_at is not None:
            _require_aware(self.ends_at, "GrantCampaign.ends_at")
            if self.ends_at <= self.starts_at:
                raise ValueError("GrantCampaign.ends_at 必须晚于 starts_at")
        policy = GrantRedemptionPolicy(self.policy)
        if policy is GrantRedemptionPolicy.SINGLE_USE:
            if self.per_account_limit != 1 or self.total_limit != 1:
                raise ValueError("单次权益活动的账号额度和总额度必须都是 1")
        if policy is GrantRedemptionPolicy.QUOTA and self.total_limit is None:
            raise ValueError("限额权益活动必须提供 total_limit")
        object.__setattr__(self, "source_kind", stable_id(self.source_kind, field="source kind"))
        object.__setattr__(self, "offer_id", stable_id(self.offer_id, field="offer id"))
        object.__setattr__(self, "policy", policy)
        object.__setattr__(self, "status", GrantCampaignStatus(self.status))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class GrantCredential:
    id: str
    campaign_id: str
    kind: GrantCredentialKind
    digest: str
    usage_limit: int | None
    issued_at: datetime
    bound_account_id: str | None = None
    expires_at: datetime | None = None
    external_reference: str | None = None
    status: GrantCredentialStatus = GrantCredentialStatus.ACTIVE
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.campaign_id.strip():
            raise ValueError("GrantCredential 缺少身份")
        digest = self.digest.strip().lower()
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ValueError("GrantCredential.digest 必须是 64 位十六进制摘要")
        if self.usage_limit is not None and self.usage_limit < 1:
            raise ValueError("GrantCredential.usage_limit 必须大于 0")
        _require_aware(self.issued_at, "GrantCredential.issued_at")
        if self.expires_at is not None:
            _require_aware(self.expires_at, "GrantCredential.expires_at")
            if self.expires_at <= self.issued_at:
                raise ValueError("GrantCredential.expires_at 必须晚于 issued_at")
        object.__setattr__(self, "kind", GrantCredentialKind(self.kind))
        object.__setattr__(self, "digest", digest)
        object.__setattr__(self, "bound_account_id", _optional_text(self.bound_account_id))
        object.__setattr__(self, "external_reference", _optional_text(self.external_reference))
        object.__setattr__(self, "status", GrantCredentialStatus(self.status))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class GrantEntitlement:
    id: str
    campaign_id: str
    account_id: str
    offer_id: StableId
    offer_version: int
    issued_at: datetime
    credential_id: str | None = None
    expires_at: datetime | None = None
    status: GrantEntitlementStatus = GrantEntitlementStatus.AVAILABLE
    redeemed_at: datetime | None = None
    settlement_id: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.campaign_id.strip() or not self.account_id.strip():
            raise ValueError("GrantEntitlement 缺少身份")
        if self.offer_version < 1:
            raise ValueError("GrantEntitlement.offer_version 必须大于 0")
        _require_aware(self.issued_at, "GrantEntitlement.issued_at")
        if self.expires_at is not None:
            _require_aware(self.expires_at, "GrantEntitlement.expires_at")
            if self.expires_at <= self.issued_at:
                raise ValueError("GrantEntitlement.expires_at 必须晚于 issued_at")
        status = GrantEntitlementStatus(self.status)
        if status is GrantEntitlementStatus.REDEEMED:
            if self.redeemed_at is None or not _optional_text(self.settlement_id):
                raise ValueError("已兑付权益必须记录时间和奖励结算 ID")
            _require_aware(self.redeemed_at, "GrantEntitlement.redeemed_at")
        elif self.redeemed_at is not None or self.settlement_id is not None:
            raise ValueError("未兑付权益不能携带兑付结果")
        object.__setattr__(self, "offer_id", stable_id(self.offer_id, field="offer id"))
        object.__setattr__(self, "credential_id", _optional_text(self.credential_id))
        object.__setattr__(self, "settlement_id", _optional_text(self.settlement_id))
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class GrantUsage:
    campaign_redeemed: int
    account_redeemed: int
    credential_used: int = 0

    def __post_init__(self) -> None:
        if min(self.campaign_redeemed, self.account_redeemed, self.credential_used) < 0:
            raise ValueError("GrantUsage 不能包含负数")


@dataclass(frozen=True)
class GrantRedemptionCommand:
    id: str
    campaign_id: str
    account_id: str
    entitlement_id: str | None = None

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.campaign_id.strip() or not self.account_id.strip():
            raise ValueError("GrantRedemptionCommand 缺少身份")
        object.__setattr__(self, "entitlement_id", _optional_text(self.entitlement_id))


@dataclass(frozen=True)
class GrantRewardBundle:
    rewards: tuple[RewardSpec, ...]
    expectations: RewardExpectations
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.rewards:
            raise ValueError("GrantRewardBundle.rewards 不能为空")
        object.__setattr__(self, "rewards", tuple(self.rewards))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class GrantRedemptionReceipt:
    redemption_id: str
    entitlement_id: str
    campaign_id: str
    account_id: str
    settlement_id: str
    request_fingerprint: str
    redeemed_at: datetime
    reward_receipt: RewardReceipt
    credential_id: str | None = None

    def __post_init__(self) -> None:
        required = (
            self.redemption_id,
            self.entitlement_id,
            self.campaign_id,
            self.account_id,
            self.settlement_id,
            self.request_fingerprint,
        )
        if any(not value.strip() for value in required):
            raise ValueError("GrantRedemptionReceipt 缺少身份")
        _require_aware(self.redeemed_at, "GrantRedemptionReceipt.redeemed_at")
        object.__setattr__(self, "credential_id", _optional_text(self.credential_id))


@dataclass(frozen=True)
class GrantRedemptionExecution:
    receipt: GrantRedemptionReceipt
    reward: RewardSettlementExecution
    replayed: bool = False


@dataclass(frozen=True)
class GrantProof:
    issuer_id: str
    receipt_id: str
    campaign_id: str
    account_id: str
    nonce: str
    issued_at: datetime
    expires_at: datetime
    payload_digest: str

    def __post_init__(self) -> None:
        if any(
            not value.strip()
            for value in (
                self.issuer_id,
                self.receipt_id,
                self.campaign_id,
                self.account_id,
                self.nonce,
            )
        ):
            raise ValueError("GrantProof 缺少身份或 nonce")
        _require_aware(self.issued_at, "GrantProof.issued_at")
        _require_aware(self.expires_at, "GrantProof.expires_at")
        if self.expires_at <= self.issued_at:
            raise ValueError("GrantProof.expires_at 必须晚于 issued_at")
        digest = self.payload_digest.strip().lower()
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ValueError("GrantProof.payload_digest 必须是 64 位十六进制摘要")
        object.__setattr__(self, "payload_digest", digest)


@dataclass(frozen=True)
class MigrationManifestEntry:
    batch_id: str
    legacy_subject_id: str
    legacy_asset_id: str
    mapping_version: str
    target_account_id: str
    entitlement_id: str
    source_digest: str
    imported_at: datetime
    source_data: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        required = (
            self.batch_id,
            self.legacy_subject_id,
            self.legacy_asset_id,
            self.mapping_version,
            self.target_account_id,
            self.entitlement_id,
        )
        if any(not value.strip() for value in required):
            raise ValueError("MigrationManifestEntry 缺少必要身份")
        digest = self.source_digest.strip().lower()
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ValueError("MigrationManifestEntry.source_digest 必须是 64 位十六进制摘要")
        _require_aware(self.imported_at, "MigrationManifestEntry.imported_at")
        object.__setattr__(self, "source_digest", digest)
        object.__setattr__(self, "source_data", MappingProxyType(dict(self.source_data)))


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} 必须包含时区")
