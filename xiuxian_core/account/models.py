"""协议中立的账号、外部身份、绑定目录和结构化事实。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import re
from types import MappingProxyType
from typing import Mapping, TypeAlias


IdentityKey: TypeAlias = tuple[str, str, str, str, str]
_STABLE_ID_PATTERN = re.compile(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+")


def _stable_id(value: object, *, field_name: str) -> str:
    """账号包不依赖 Gameplay，但使用相同的英文稳定 ID 约束。"""

    text = str(value or "").strip()
    if not _STABLE_ID_PATTERN.fullmatch(text):
        raise ValueError(f"{field_name} 必须是至少两段的英文小写稳定标识：{text!r}")
    return text


class AccountStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


@dataclass(frozen=True, order=True)
class ExternalIdentity:
    """一个外部平台命名空间中的唯一身份键。"""

    provider_id: str
    tenant_id: str
    subject_kind: str
    scope_id: str
    external_id: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "provider_id",
            _stable_id(self.provider_id, field_name="provider_id"),
        )
        object.__setattr__(
            self,
            "subject_kind",
            _stable_id(self.subject_kind, field_name="subject_kind"),
        )
        for field_name in ("tenant_id", "external_id"):
            value = str(getattr(self, field_name) or "").strip()
            if not value:
                raise ValueError(f"ExternalIdentity 缺少 {field_name}")
            object.__setattr__(self, field_name, value)
        object.__setattr__(self, "scope_id", str(self.scope_id or "").strip())

    @property
    def key(self) -> IdentityKey:
        return (
            self.provider_id,
            self.tenant_id,
            self.subject_kind,
            self.scope_id,
            self.external_id,
        )


@dataclass(frozen=True)
class IdentityEvidence:
    """同一个已验证平台事件同时证明的一组身份。"""

    id: str
    primary: ExternalIdentity
    aliases: tuple[ExternalIdentity, ...]
    source_kind: str
    logical_time: datetime

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("IdentityEvidence 缺少 id")
        object.__setattr__(
            self,
            "source_kind",
            _stable_id(self.source_kind, field_name="source_kind"),
        )
        if self.logical_time.tzinfo is None or self.logical_time.utcoffset() is None:
            raise ValueError("IdentityEvidence.logical_time 必须包含时区")
        identities = (self.primary, *self.aliases)
        if len({identity.key for identity in identities}) != len(identities):
            raise ValueError("IdentityEvidence 中存在重复身份")
        namespaces = {(identity.provider_id, identity.tenant_id) for identity in identities}
        if len(namespaces) != 1:
            raise ValueError("一次身份凭据不能跨平台或跨机器人租户自动关联")

    @property
    def identities(self) -> tuple[ExternalIdentity, ...]:
        return (self.primary, *self.aliases)

    @property
    def identity_keys(self) -> tuple[IdentityKey, ...]:
        return tuple(sorted(identity.key for identity in self.identities))


@dataclass(frozen=True)
class AccountState:
    id: str
    status: AccountStatus
    created_at: datetime
    revision: int = 0

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("AccountState 缺少 id")
        object.__setattr__(self, "status", AccountStatus(self.status))
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("AccountState.created_at 必须包含时区")
        if self.revision < 0:
            raise ValueError("AccountState.revision 不能小于 0")


@dataclass(frozen=True)
class IdentityBinding:
    identity: ExternalIdentity
    account_id: str
    bound_at: datetime
    source_evidence_id: str

    def __post_init__(self) -> None:
        if not self.account_id.strip() or not self.source_evidence_id.strip():
            raise ValueError("IdentityBinding 缺少账号或凭据 id")
        if self.bound_at.tzinfo is None or self.bound_at.utcoffset() is None:
            raise ValueError("IdentityBinding.bound_at 必须包含时区")


@dataclass(frozen=True)
class IdentityConflict:
    id: str
    identity_keys: tuple[IdentityKey, ...]
    account_ids: tuple[str, ...]
    detected_at: datetime
    source_kind: str

    def __post_init__(self) -> None:
        account_ids = tuple(sorted(set(self.account_ids)))
        if not self.id.strip() or len(account_ids) < 2:
            raise ValueError("IdentityConflict 缺少冲突身份或账号")
        if self.detected_at.tzinfo is None or self.detected_at.utcoffset() is None:
            raise ValueError("IdentityConflict.detected_at 必须包含时区")
        object.__setattr__(self, "identity_keys", tuple(sorted(self.identity_keys)))
        object.__setattr__(self, "account_ids", account_ids)
        object.__setattr__(
            self,
            "source_kind",
            _stable_id(self.source_kind, field_name="source_kind"),
        )


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    identity_keys: tuple[IdentityKey, ...]
    account_id: str | None = None
    conflict_id: str | None = None

    def __post_init__(self) -> None:
        if not self.evidence_id.strip():
            raise ValueError("EvidenceRecord 缺少 evidence_id")
        if (self.account_id is None) == (self.conflict_id is None):
            raise ValueError("EvidenceRecord 必须且只能指向账号或冲突")
        object.__setattr__(self, "identity_keys", tuple(sorted(self.identity_keys)))


@dataclass(frozen=True)
class AccountEvent:
    kind: str
    account_id: str
    trace_id: str
    logical_time: datetime
    values: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _stable_id(self.kind, field_name="event kind"))
        if not self.trace_id.strip():
            raise ValueError("AccountEvent 缺少 trace_id")
        if self.logical_time.tzinfo is None or self.logical_time.utcoffset() is None:
            raise ValueError("AccountEvent.logical_time 必须包含时区")
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))


@dataclass(frozen=True)
class AccountDirectoryState:
    accounts: Mapping[str, AccountState] = field(default_factory=dict)
    bindings: Mapping[IdentityKey, IdentityBinding] = field(default_factory=dict)
    conflicts: Mapping[str, IdentityConflict] = field(default_factory=dict)
    evidence_records: Mapping[str, EvidenceRecord] = field(default_factory=dict)
    applied_transactions: Mapping[str, str] = field(default_factory=dict)
    revision: int = 0

    def __post_init__(self) -> None:
        accounts = dict(self.accounts)
        bindings = dict(self.bindings)
        conflicts = dict(self.conflicts)
        records = dict(self.evidence_records)
        transactions = dict(self.applied_transactions)
        if self.revision < 0:
            raise ValueError("AccountDirectoryState.revision 不能小于 0")
        for key, account in accounts.items():
            if key != account.id:
                raise ValueError(f"账号映射键与 id 不一致：{key}")
        for key, binding in bindings.items():
            if key != binding.identity.key:
                raise ValueError("身份绑定映射键与身份内容不一致")
            if binding.account_id not in accounts:
                raise ValueError(f"身份绑定引用未知账号：{binding.account_id}")
        for key, conflict in conflicts.items():
            if key != conflict.id:
                raise ValueError(f"身份冲突映射键与 id 不一致：{key}")
            if not set(conflict.account_ids).issubset(accounts):
                raise ValueError("身份冲突引用未知账号")
        for key, record in records.items():
            if key != record.evidence_id:
                raise ValueError(f"凭据记录映射键与 id 不一致：{key}")
            if record.account_id is not None and record.account_id not in accounts:
                raise ValueError("凭据记录引用未知账号")
            if record.conflict_id is not None and record.conflict_id not in conflicts:
                raise ValueError("凭据记录引用未知冲突")
        for transaction_id, account_id in transactions.items():
            if not transaction_id.strip() or account_id not in accounts:
                raise ValueError("账号事务防重放记录无效")
        object.__setattr__(self, "accounts", MappingProxyType(accounts))
        object.__setattr__(self, "bindings", MappingProxyType(bindings))
        object.__setattr__(self, "conflicts", MappingProxyType(conflicts))
        object.__setattr__(self, "evidence_records", MappingProxyType(records))
        object.__setattr__(self, "applied_transactions", MappingProxyType(transactions))

    def account_for(self, identity: ExternalIdentity) -> AccountState | None:
        binding = self.bindings.get(identity.key)
        return self.accounts.get(binding.account_id) if binding else None

    def identities_for(self, account_id: str) -> tuple[ExternalIdentity, ...]:
        return tuple(
            sorted(
                binding.identity
                for binding in self.bindings.values()
                if binding.account_id == account_id
            )
        )


__all__ = [
    "AccountDirectoryState",
    "AccountEvent",
    "AccountState",
    "AccountStatus",
    "EvidenceRecord",
    "ExternalIdentity",
    "IdentityBinding",
    "IdentityConflict",
    "IdentityEvidence",
    "IdentityKey",
]
