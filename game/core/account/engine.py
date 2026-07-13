"""外部身份自动解析、账号状态和解绑事务。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from hashlib import sha256
from types import MappingProxyType
from typing import Mapping

from .models import (
    AccountDirectoryState,
    AccountEvent,
    AccountState,
    AccountStatus,
    EvidenceRecord,
    ExternalIdentity,
    IdentityBinding,
    IdentityConflict,
    IdentityEvidence,
)


class AccountViolation(Exception):
    """账号域可预期失败，code 可由上层稳定翻译。"""

    def __init__(
        self,
        code: str,
        message: str,
        details: Mapping[str, object] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.details = MappingProxyType(dict(details or {}))
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class AccountResolution:
    directory: AccountDirectoryState
    account: AccountState | None
    conflict: IdentityConflict | None
    events: tuple[AccountEvent, ...]
    created: bool = False
    replayed: bool = False

    @property
    def resolved(self) -> bool:
        return self.account is not None


@dataclass(frozen=True)
class AccountStatusTransaction:
    id: str
    account_id: str
    expected_revision: int
    status: AccountStatus
    reason: str
    logical_time: datetime

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.account_id.strip() or not self.reason.strip():
            raise ValueError("AccountStatusTransaction 缺少必要字段")
        if self.expected_revision < 0:
            raise ValueError("expected_revision 不能小于 0")
        object.__setattr__(self, "status", AccountStatus(self.status))
        if self.logical_time.tzinfo is None or self.logical_time.utcoffset() is None:
            raise ValueError("logical_time 必须包含时区")


@dataclass(frozen=True)
class UnbindIdentityTransaction:
    id: str
    account_id: str
    expected_revision: int
    identity: ExternalIdentity
    reason: str
    logical_time: datetime

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.account_id.strip() or not self.reason.strip():
            raise ValueError("UnbindIdentityTransaction 缺少必要字段")
        if self.expected_revision < 0:
            raise ValueError("expected_revision 不能小于 0")
        if self.logical_time.tzinfo is None or self.logical_time.utcoffset() is None:
            raise ValueError("logical_time 必须包含时区")


@dataclass(frozen=True)
class AccountMutation:
    directory: AccountDirectoryState
    account: AccountState
    events: tuple[AccountEvent, ...]
    replayed: bool = False


class AccountEngine:
    """只相信同一已验证事件提供的身份关系，不根据昵称猜测。"""

    def __init__(self, account_id_factory: Callable[[], str]) -> None:
        self.account_id_factory = account_id_factory

    def resolve_identity(
        self,
        evidence: IdentityEvidence,
        *,
        state: AccountDirectoryState,
    ) -> AccountResolution:
        previous = state.evidence_records.get(evidence.id)
        if previous is not None:
            if previous.identity_keys != evidence.identity_keys:
                raise AccountViolation(
                    "account.evidence_mismatch",
                    "同一个身份凭据 id 携带了不同身份集合",
                    {"evidence_id": evidence.id},
                )
            if previous.account_id is not None:
                return AccountResolution(
                    state,
                    state.accounts[previous.account_id],
                    None,
                    (),
                    replayed=True,
                )
            assert previous.conflict_id is not None
            return AccountResolution(
                state,
                None,
                state.conflicts[previous.conflict_id],
                (),
                replayed=True,
            )

        accounts = dict(state.accounts)
        bindings = dict(state.bindings)
        conflicts = dict(state.conflicts)
        records = dict(state.evidence_records)
        account_ids = {
            binding.account_id
            for identity in evidence.identities
            if (binding := bindings.get(identity.key)) is not None
        }
        if len(account_ids) > 1:
            conflict = IdentityConflict(
                id=f"identity-conflict:{evidence.id}",
                identity_keys=evidence.identity_keys,
                account_ids=tuple(sorted(account_ids)),
                detected_at=evidence.logical_time,
                source_kind=evidence.source_kind,
            )
            conflicts[conflict.id] = conflict
            records[evidence.id] = EvidenceRecord(
                evidence.id,
                evidence.identity_keys,
                conflict_id=conflict.id,
            )
            directory = self._directory(
                state,
                accounts=accounts,
                bindings=bindings,
                conflicts=conflicts,
                records=records,
            )
            event = AccountEvent(
                "account.identity.conflict",
                "",
                evidence.id,
                evidence.logical_time,
                {
                    "account_ids": conflict.account_ids,
                    "identity_fingerprints": tuple(
                        _identity_fingerprint(identity) for identity in evidence.identities
                    ),
                },
            )
            return AccountResolution(directory, None, conflict, (event,))

        created = False
        events: list[AccountEvent] = []
        if not account_ids:
            account_id = str(self.account_id_factory() or "").strip()
            if not account_id:
                raise RuntimeError("account_id_factory 返回了空账号 id")
            if account_id in accounts:
                raise RuntimeError(f"account_id_factory 产生重复账号 id：{account_id}")
            account = AccountState(
                account_id,
                AccountStatus.ACTIVE,
                evidence.logical_time,
            )
            accounts[account.id] = account
            created = True
            events.append(
                AccountEvent(
                    "account.created",
                    account.id,
                    evidence.id,
                    evidence.logical_time,
                    {"source_kind": evidence.source_kind},
                )
            )
        else:
            account_id = next(iter(account_ids))
            account = accounts[account_id]

        bound_count = 0
        for identity in evidence.identities:
            if identity.key in bindings:
                continue
            bindings[identity.key] = IdentityBinding(
                identity,
                account.id,
                evidence.logical_time,
                evidence.id,
            )
            bound_count += 1
            events.append(
                AccountEvent(
                    "account.identity.bound",
                    account.id,
                    evidence.id,
                    evidence.logical_time,
                    {
                        "provider_id": identity.provider_id,
                        "subject_kind": identity.subject_kind,
                        "identity_fingerprint": _identity_fingerprint(identity),
                    },
                )
            )
        if bound_count and not created:
            account = replace(account, revision=account.revision + 1)
            accounts[account.id] = account
        records[evidence.id] = EvidenceRecord(
            evidence.id,
            evidence.identity_keys,
            account_id=account.id,
        )
        directory = self._directory(
            state,
            accounts=accounts,
            bindings=bindings,
            conflicts=conflicts,
            records=records,
        )
        return AccountResolution(directory, account, None, tuple(events), created=created)

    def change_status(
        self,
        transaction: AccountStatusTransaction,
        *,
        state: AccountDirectoryState,
    ) -> AccountMutation:
        replay = self._replayed_mutation(transaction.id, transaction.account_id, state)
        if replay is not None:
            return replay
        account = self._require_revision(
            transaction.account_id,
            transaction.expected_revision,
            state,
        )
        if account.status is AccountStatus.CLOSED:
            raise AccountViolation("account.closed", "已经关闭的账号不能重新启用")
        if account.status is transaction.status:
            raise AccountViolation("account.status_unchanged", "账号状态没有变化")
        account = replace(
            account,
            status=transaction.status,
            revision=account.revision + 1,
        )
        accounts = dict(state.accounts)
        accounts[account.id] = account
        transactions = dict(state.applied_transactions)
        transactions[transaction.id] = account.id
        directory = self._directory(
            state,
            accounts=accounts,
            transactions=transactions,
        )
        event = AccountEvent(
            "account.status.changed",
            account.id,
            transaction.id,
            transaction.logical_time,
            {"status": account.status.value, "reason": transaction.reason},
        )
        return AccountMutation(directory, account, (event,))

    def unbind_identity(
        self,
        transaction: UnbindIdentityTransaction,
        *,
        state: AccountDirectoryState,
    ) -> AccountMutation:
        replay = self._replayed_mutation(transaction.id, transaction.account_id, state)
        if replay is not None:
            return replay
        account = self._require_revision(
            transaction.account_id,
            transaction.expected_revision,
            state,
        )
        binding = state.bindings.get(transaction.identity.key)
        if binding is None or binding.account_id != account.id:
            raise AccountViolation(
                "account.identity_not_bound",
                "指定外部身份不属于当前账号",
            )
        if len(state.identities_for(account.id)) <= 1:
            raise AccountViolation(
                "account.last_identity",
                "不能解绑账号的最后一个外部身份",
            )
        bindings = dict(state.bindings)
        del bindings[transaction.identity.key]
        account = replace(account, revision=account.revision + 1)
        accounts = dict(state.accounts)
        accounts[account.id] = account
        transactions = dict(state.applied_transactions)
        transactions[transaction.id] = account.id
        directory = self._directory(
            state,
            accounts=accounts,
            bindings=bindings,
            transactions=transactions,
        )
        event = AccountEvent(
            "account.identity.unbound",
            account.id,
            transaction.id,
            transaction.logical_time,
            {
                "provider_id": transaction.identity.provider_id,
                "subject_kind": transaction.identity.subject_kind,
                "identity_fingerprint": _identity_fingerprint(transaction.identity),
                "reason": transaction.reason,
            },
        )
        return AccountMutation(directory, account, (event,))

    @staticmethod
    def require_active(account: AccountState) -> None:
        if account.status is not AccountStatus.ACTIVE:
            raise AccountViolation(
                "account.not_active",
                "当前账号不能执行游戏业务",
                {"status": account.status.value},
            )

    @staticmethod
    def _require_revision(
        account_id: str,
        expected_revision: int,
        state: AccountDirectoryState,
    ) -> AccountState:
        try:
            account = state.accounts[account_id]
        except KeyError as exc:
            raise AccountViolation("account.unknown", "找不到账号") from exc
        if account.revision != expected_revision:
            raise AccountViolation(
                "account.revision_conflict",
                "账号状态版本与事务预期不一致",
                {"expected": expected_revision, "actual": account.revision},
            )
        return account

    @staticmethod
    def _replayed_mutation(
        transaction_id: str,
        account_id: str,
        state: AccountDirectoryState,
    ) -> AccountMutation | None:
        previous_account_id = state.applied_transactions.get(transaction_id)
        if previous_account_id is None:
            return None
        if previous_account_id != account_id:
            raise AccountViolation(
                "account.transaction_mismatch",
                "同一个账号事务 id 被用于不同账号",
            )
        return AccountMutation(
            state,
            state.accounts[account_id],
            (),
            replayed=True,
        )

    @staticmethod
    def _directory(
        original: AccountDirectoryState,
        *,
        accounts: Mapping[str, AccountState] | None = None,
        bindings: Mapping[tuple[str, str, str, str, str], IdentityBinding] | None = None,
        conflicts: Mapping[str, IdentityConflict] | None = None,
        records: Mapping[str, EvidenceRecord] | None = None,
        transactions: Mapping[str, str] | None = None,
    ) -> AccountDirectoryState:
        return AccountDirectoryState(
            accounts=accounts if accounts is not None else original.accounts,
            bindings=bindings if bindings is not None else original.bindings,
            conflicts=conflicts if conflicts is not None else original.conflicts,
            evidence_records=records if records is not None else original.evidence_records,
            applied_transactions=(
                transactions if transactions is not None else original.applied_transactions
            ),
            revision=original.revision + 1,
        )


def _identity_fingerprint(identity: ExternalIdentity) -> str:
    payload = "\x1f".join(identity.key).encode("utf-8")
    return sha256(payload).hexdigest()[:12]


__all__ = [
    "AccountEngine",
    "AccountMutation",
    "AccountResolution",
    "AccountStatusTransaction",
    "AccountViolation",
    "UnbindIdentityTransaction",
]
