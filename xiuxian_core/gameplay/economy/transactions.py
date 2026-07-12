"""经济账本的原子事务与标准资金操作。"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass, replace
from datetime import datetime
from enum import Enum
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Mapping, Protocol

from ..context import RuleContext
from ..errors import RuleOutcome, RuleViolation
from ..events import RuleEvent
from ..ids import StableId, stable_id
from .definitions import CurrencyCatalog
from .models import (
    AppliedLedgerTransaction,
    FundHold,
    JournalEntry,
    LedgerAccount,
    LedgerAccountKind,
    LedgerPosting,
    LedgerState,
)


class LedgerOperation(Protocol):
    """账本事务接受的原子操作标记。"""


@dataclass(frozen=True)
class FundAllocation:
    destination_account_id: str
    amount: int


@dataclass(frozen=True)
class OpenLedgerAccount:
    account: LedgerAccount


@dataclass(frozen=True)
class TransferFunds:
    source_account_id: str
    destination_account_id: str
    amount: int


@dataclass(frozen=True)
class SplitFunds:
    """从一个账户原子拆分到多个账户，税金和分成都由上层给出结果。"""

    source_account_id: str
    allocations: tuple[FundAllocation, ...]


@dataclass(frozen=True)
class IssueFunds:
    issuer_account_id: str
    destination_account_id: str
    amount: int


@dataclass(frozen=True)
class RetireFunds:
    source_account_id: str
    issuer_account_id: str
    amount: int


@dataclass(frozen=True)
class PlaceFundHold:
    hold_id: str
    account_id: str
    amount: int
    business_kind: StableId
    business_id: str
    expires_at: datetime | None = None


@dataclass(frozen=True)
class ReleaseFundHold:
    hold_id: str


@dataclass(frozen=True)
class CaptureFundHold:
    """从冻结金额中扣款；未捕获的余额继续冻结。"""

    hold_id: str
    allocations: tuple[FundAllocation, ...]


@dataclass(frozen=True)
class LedgerTransaction:
    """调用方提交的唯一事务、并发预期和有序操作。"""

    id: str
    actor_id: str
    reason: StableId
    operations: tuple[LedgerOperation, ...]
    expected_revisions: Mapping[str, int] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.actor_id.strip():
            raise ValueError("LedgerTransaction 缺少事务或操作者 id")
        object.__setattr__(self, "reason", stable_id(self.reason, field="transaction reason"))
        if not self.operations:
            raise ValueError("LedgerTransaction.operations 不能为空")
        revisions = dict(self.expected_revisions)
        if any(not key.strip() or value < 0 for key, value in revisions.items()):
            raise ValueError("LedgerTransaction.expected_revisions 无效")
        object.__setattr__(self, "expected_revisions", MappingProxyType(revisions))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class LedgerExecution:
    transaction_id: str
    state: LedgerState
    events: tuple[RuleEvent, ...]
    entries: tuple[JournalEntry, ...]
    replayed: bool = False


@dataclass
class _Draft:
    accounts: dict[str, LedgerAccount]
    holds: dict[str, FundHold]
    entries: list[JournalEntry]
    events: list[RuleEvent]
    existing_account_ids: frozenset[str]
    checked_account_ids: set[str]
    mutated_account_ids: set[str]


class LedgerEngine:
    """只执行资金方案，不决定价格、税率、奖励量或交易是否划算。"""

    def __init__(self, currencies: CurrencyCatalog) -> None:
        if not currencies.finalized:
            currencies.finalize()
        self.currencies = currencies

    def execute(
        self,
        transaction: LedgerTransaction,
        *,
        state: LedgerState,
        context: RuleContext,
    ) -> RuleOutcome[LedgerExecution]:
        fingerprint = _transaction_fingerprint(transaction)
        previous = state.applied_transactions.get(transaction.id)
        if previous is not None:
            if previous.fingerprint != fingerprint:
                return RuleOutcome.failed(
                    self._failure(
                        "economy.transaction_mismatch",
                        "同一个 transaction_id 携带了不同事务内容",
                        {"transaction_id": transaction.id},
                    )
                )
            return RuleOutcome.success(
                LedgerExecution(transaction.id, state, (), (), replayed=True)
            )

        checkpoint = context.random.checkpoint()
        draft = _Draft(
            accounts=dict(state.accounts),
            holds=dict(state.holds),
            entries=[],
            events=[],
            existing_account_ids=frozenset(state.accounts),
            checked_account_ids=set(),
            mutated_account_ids=set(),
        )
        try:
            self._release_expired_holds(draft, transaction, context)
            for operation in transaction.operations:
                self._apply(operation, draft, transaction, context)
            unused = set(transaction.expected_revisions) - draft.checked_account_ids
            if unused:
                self._fail(
                    "economy.unused_revision",
                    "事务包含未参与变更的账户 revision",
                    {"account_ids": tuple(sorted(unused))},
                )
            accounts = {
                account_id: replace(
                    account,
                    revision=account.revision + (account_id in draft.mutated_account_ids),
                )
                for account_id, account in draft.accounts.items()
            }
            revision = state.revision + 1
            applied = dict(state.applied_transactions)
            applied[transaction.id] = AppliedLedgerTransaction(
                transaction.id,
                fingerprint,
                revision,
            )
            result = LedgerState(
                accounts=accounts,
                holds=draft.holds,
                journal=state.journal + tuple(draft.entries),
                applied_transactions=applied,
                revision=revision,
            )
            return RuleOutcome.success(
                LedgerExecution(
                    transaction.id,
                    result,
                    tuple(draft.events),
                    tuple(draft.entries),
                )
            )
        except RuleViolation as exc:
            context.random.restore(checkpoint)
            return RuleOutcome.failed(exc.failure)

    def _apply(
        self,
        operation: LedgerOperation,
        draft: _Draft,
        transaction: LedgerTransaction,
        context: RuleContext,
    ) -> None:
        handlers = {
            OpenLedgerAccount: self._open_account,
            TransferFunds: self._transfer,
            SplitFunds: self._split,
            IssueFunds: self._issue,
            RetireFunds: self._retire,
            PlaceFundHold: self._place_hold,
            ReleaseFundHold: self._release_hold,
            CaptureFundHold: self._capture_hold,
        }
        try:
            handler = handlers[type(operation)]
        except KeyError as exc:
            raise TypeError(f"未知账本操作：{type(operation).__name__}") from exc
        handler(operation, draft, transaction, context)

    def _open_account(
        self,
        operation: OpenLedgerAccount,
        draft: _Draft,
        transaction: LedgerTransaction,
        context: RuleContext,
    ) -> None:
        account = operation.account
        if account.id in draft.accounts:
            self._fail("economy.account_exists", "账本账户已经存在", {"account_id": account.id})
        try:
            self.currencies.require(account.currency_id)
        except KeyError:
            self._fail(
                "economy.currency_unknown",
                "账户引用了未知货币",
                {"currency_id": account.currency_id},
            )
        if account.balance != 0 or account.revision != 0:
            self._fail("economy.account_not_empty", "新账户必须以零余额和零 revision 开立")
        if account.kind is LedgerAccountKind.ISSUER and any(
            value.kind is LedgerAccountKind.ISSUER
            and value.currency_id == account.currency_id
            for value in draft.accounts.values()
        ):
            self._fail(
                "economy.issuer_exists",
                "同一种货币只能存在一个发行账户",
                {"currency_id": account.currency_id},
            )
        draft.accounts[account.id] = account
        self._event(
            draft,
            transaction,
            context,
            "economy.account.opened",
            transaction.actor_id,
            account.id,
            account.currency_id,
            {"account_kind": account.kind.value, "owner_kind": account.owner_kind},
        )

    def _transfer(self, operation, draft, transaction, context) -> None:
        self._positive_amount(operation.amount)
        source, destination = self._movement_accounts(
            operation.source_account_id,
            operation.destination_account_id,
            draft,
            transaction,
            allow_issuer=False,
        )
        self._require_available(source.id, operation.amount, draft, context.logical_time)
        self._record_movement(
            source,
            (FundAllocation(destination.id, operation.amount),),
            "economy.funds.transferred",
            draft,
            transaction,
            context,
        )

    def _split(self, operation, draft, transaction, context) -> None:
        allocations = self._validate_allocations(operation.allocations)
        source = self._require_account(operation.source_account_id, draft)
        self._require_non_issuer(source)
        self._touch(source.id, draft, transaction)
        destinations = self._allocation_accounts(source, allocations, draft, transaction)
        total = sum(value.amount for value in allocations)
        self._require_available(source.id, total, draft, context.logical_time)
        self._record_movement(
            source,
            tuple(FundAllocation(account.id, allocation.amount) for account, allocation in destinations),
            "economy.funds.split",
            draft,
            transaction,
            context,
        )

    def _issue(self, operation, draft, transaction, context) -> None:
        self._positive_amount(operation.amount)
        issuer, destination = self._movement_accounts(
            operation.issuer_account_id,
            operation.destination_account_id,
            draft,
            transaction,
            allow_issuer=True,
        )
        if issuer.kind is not LedgerAccountKind.ISSUER or destination.kind is LedgerAccountKind.ISSUER:
            self._fail("economy.invalid_issuance", "发行必须从发行账户进入非发行账户")
        self._record_movement(
            issuer,
            (FundAllocation(destination.id, operation.amount),),
            "economy.funds.issued",
            draft,
            transaction,
            context,
        )

    def _retire(self, operation, draft, transaction, context) -> None:
        self._positive_amount(operation.amount)
        source, issuer = self._movement_accounts(
            operation.source_account_id,
            operation.issuer_account_id,
            draft,
            transaction,
            allow_issuer=True,
        )
        if source.kind is LedgerAccountKind.ISSUER or issuer.kind is not LedgerAccountKind.ISSUER:
            self._fail("economy.invalid_retirement", "回收必须从非发行账户进入发行账户")
        self._require_available(source.id, operation.amount, draft, context.logical_time)
        if issuer.balance + operation.amount > 0:
            self._fail(
                "economy.retirement_exceeds_issuance",
                "回收金额不能超过该发行账户的历史净发行量",
                {"issued": -issuer.balance, "requested": operation.amount},
            )
        self._record_movement(
            source,
            (FundAllocation(issuer.id, operation.amount),),
            "economy.funds.retired",
            draft,
            transaction,
            context,
        )

    def _place_hold(self, operation, draft, transaction, context) -> None:
        self._positive_amount(operation.amount)
        if operation.hold_id in draft.holds:
            self._fail("economy.hold_exists", "资金预约已经存在", {"hold_id": operation.hold_id})
        account = self._require_account(operation.account_id, draft)
        self._require_non_issuer(account)
        self._touch(account.id, draft, transaction)
        self._require_available(account.id, operation.amount, draft, context.logical_time)
        try:
            hold = FundHold(
                operation.hold_id,
                account.id,
                operation.amount,
                operation.business_kind,
                operation.business_id,
                context.logical_time,
                operation.expires_at,
            )
        except ValueError as exc:
            self._fail("economy.invalid_hold", str(exc))
        draft.holds[hold.id] = hold
        draft.mutated_account_ids.add(account.id)
        self._event(
            draft,
            transaction,
            context,
            "economy.funds.held",
            account.id,
            account.id,
            account.currency_id,
            {"hold_id": hold.id, "amount": hold.amount, "business_kind": hold.business_kind},
        )

    def _release_hold(self, operation, draft, transaction, context) -> None:
        hold = self._require_hold(operation.hold_id, draft)
        account = self._require_account(hold.account_id, draft)
        self._touch(account.id, draft, transaction)
        del draft.holds[hold.id]
        draft.mutated_account_ids.add(account.id)
        self._event(
            draft,
            transaction,
            context,
            "economy.funds.released",
            account.id,
            account.id,
            account.currency_id,
            {"hold_id": hold.id, "amount": hold.amount, "release_cause": "explicit"},
        )

    def _capture_hold(self, operation, draft, transaction, context) -> None:
        allocations = self._validate_allocations(operation.allocations)
        hold = self._require_hold(operation.hold_id, draft)
        if not hold.active_at(context.logical_time):
            self._fail("economy.hold_expired", "资金预约已经过期", {"hold_id": hold.id})
        source = self._require_account(hold.account_id, draft)
        self._touch(source.id, draft, transaction)
        destinations = self._allocation_accounts(source, allocations, draft, transaction)
        total = sum(value.amount for value in allocations)
        if total > hold.amount:
            self._fail(
                "economy.hold_insufficient",
                "捕获金额超过资金预约余额",
                {"hold_id": hold.id, "held": hold.amount, "requested": total},
            )
        if total == hold.amount:
            del draft.holds[hold.id]
        else:
            draft.holds[hold.id] = replace(hold, amount=hold.amount - total)
        self._record_movement(
            source,
            tuple(FundAllocation(account.id, allocation.amount) for account, allocation in destinations),
            "economy.funds.captured",
            draft,
            transaction,
            context,
            metadata={"hold_id": hold.id, "remaining_hold": hold.amount - total},
        )

    def _record_movement(
        self,
        source: LedgerAccount,
        allocations: tuple[FundAllocation, ...],
        event_kind: StableId,
        draft: _Draft,
        transaction: LedgerTransaction,
        context: RuleContext,
        *,
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        total = sum(value.amount for value in allocations)
        postings = (LedgerPosting(source.id, -total),) + tuple(
            LedgerPosting(value.destination_account_id, value.amount) for value in allocations
        )
        for posting in postings:
            account = draft.accounts[posting.account_id]
            draft.accounts[account.id] = replace(account, balance=account.balance + posting.amount)
            draft.mutated_account_ids.add(account.id)
        entry = JournalEntry(
            id=f"{transaction.id}:entry:{len(draft.entries) + 1}",
            transaction_id=transaction.id,
            currency_id=source.currency_id,
            reason=transaction.reason,
            actor_id=transaction.actor_id,
            logical_time=context.logical_time,
            postings=postings,
            metadata={**transaction.metadata, **(metadata or {}), "operation_kind": event_kind},
        )
        draft.entries.append(entry)
        self._event(
            draft,
            transaction,
            context,
            event_kind,
            source.id,
            allocations[0].destination_account_id,
            source.currency_id,
            {
                "entry_id": entry.id,
                "amount": total,
                "allocations": tuple(
                    (value.destination_account_id, value.amount) for value in allocations
                ),
                **(metadata or {}),
            },
        )

    def _movement_accounts(self, source_id, destination_id, draft, transaction, *, allow_issuer):
        if source_id == destination_id:
            self._fail("economy.same_account", "资金来源和去向不能是同一账户")
        source = self._require_account(source_id, draft)
        destination = self._require_account(destination_id, draft)
        if source.currency_id != destination.currency_id:
            self._fail("economy.currency_mismatch", "不能在不同币种账户之间直接转账")
        if not allow_issuer:
            self._require_non_issuer(source)
            self._require_non_issuer(destination)
        self._touch(source.id, draft, transaction)
        self._touch(destination.id, draft, transaction)
        return source, destination

    def _allocation_accounts(self, source, allocations, draft, transaction):
        values = []
        for allocation in allocations:
            if allocation.destination_account_id == source.id:
                self._fail("economy.same_account", "拆账去向不能包含来源账户")
            account = self._require_account(allocation.destination_account_id, draft)
            self._require_non_issuer(account)
            if account.currency_id != source.currency_id:
                self._fail("economy.currency_mismatch", "拆账账户币种必须一致")
            self._touch(account.id, draft, transaction)
            values.append((account, allocation))
        return tuple(values)

    def _validate_allocations(self, allocations):
        if not allocations:
            self._fail("economy.empty_allocation", "资金拆分去向不能为空")
        ids = [value.destination_account_id for value in allocations]
        if len(ids) != len(set(ids)):
            self._fail("economy.duplicate_allocation", "同一拆账中不能重复目标账户")
        for allocation in allocations:
            self._positive_amount(allocation.amount)
        return tuple(allocations)

    def _require_available(self, account_id, amount, draft, logical_time) -> None:
        account = draft.accounts[account_id]
        held = sum(
            hold.amount
            for hold in draft.holds.values()
            if hold.account_id == account_id and hold.active_at(logical_time)
        )
        available = account.balance - held
        if amount > available:
            self._fail(
                "economy.insufficient_funds",
                "账户可用余额不足",
                {"account_id": account_id, "available": available, "requested": amount},
            )

    def _touch(self, account_id, draft, transaction) -> None:
        if account_id not in draft.existing_account_ids:
            return
        account = draft.accounts[account_id]
        expected = transaction.expected_revisions.get(account_id)
        if expected is None:
            self._fail(
                "economy.revision_required",
                "变更已有账户必须提供 expected revision",
                {"account_id": account_id, "actual": account.revision},
            )
        if expected != account.revision:
            self._fail(
                "economy.revision_conflict",
                "账本账户 revision 已变化",
                {"account_id": account_id, "expected": expected, "actual": account.revision},
            )
        draft.checked_account_ids.add(account_id)

    def _release_expired_holds(self, draft, transaction, context) -> None:
        for hold in tuple(draft.holds.values()):
            if hold.active_at(context.logical_time):
                continue
            del draft.holds[hold.id]
            account = draft.accounts[hold.account_id]
            self._event(
                draft,
                transaction,
                context,
                "economy.funds.released",
                account.id,
                account.id,
                account.currency_id,
                {"hold_id": hold.id, "amount": hold.amount, "release_cause": "expired"},
            )

    def _require_account(self, account_id, draft) -> LedgerAccount:
        try:
            return draft.accounts[account_id]
        except KeyError:
            self._fail("economy.account_unknown", "未知账本账户", {"account_id": account_id})

    def _require_hold(self, hold_id, draft) -> FundHold:
        try:
            return draft.holds[hold_id]
        except KeyError:
            self._fail("economy.hold_unknown", "未知资金预约", {"hold_id": hold_id})

    def _require_non_issuer(self, account: LedgerAccount) -> None:
        if account.kind is LedgerAccountKind.ISSUER:
            self._fail("economy.issuer_forbidden", "发行账户只能用于发行或回收")

    def _positive_amount(self, amount) -> None:
        if not isinstance(amount, int) or isinstance(amount, bool) or amount < 1:
            self._fail("economy.invalid_amount", "资金金额必须是大于 0 的整数最小单位")

    @staticmethod
    def _event(draft, transaction, context, kind, source_id, target_id, currency_id, values):
        draft.events.append(
            RuleEvent.from_context(
                context,
                kind=kind,
                source_id=source_id,
                target_id=target_id,
                subject_id=currency_id,
                values={"transaction_id": transaction.id, "reason": transaction.reason, **values},
            )
        )

    @staticmethod
    def _failure(code, message, details=None):
        try:
            raise RuleViolation(code, message, details or {})
        except RuleViolation as exc:
            return exc.failure

    @staticmethod
    def _fail(code, message, details=None) -> None:
        raise RuleViolation(code, message, details or {})


def _transaction_fingerprint(transaction: LedgerTransaction) -> str:
    payload = _canonical(transaction)
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def _canonical(value):
    if is_dataclass(value):
        return {item.name: _canonical(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _canonical(item) for key, item in sorted(value.items())}
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    return value


__all__ = [
    "CaptureFundHold",
    "FundAllocation",
    "IssueFunds",
    "LedgerEngine",
    "LedgerExecution",
    "LedgerOperation",
    "LedgerTransaction",
    "OpenLedgerAccount",
    "PlaceFundHold",
    "ReleaseFundHold",
    "RetireFunds",
    "SplitFunds",
    "TransferFunds",
]
