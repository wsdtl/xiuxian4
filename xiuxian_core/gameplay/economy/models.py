"""经济账户、资金预约、复式流水与账本快照。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from ..ids import StableId, stable_id


class LedgerAccountKind(str, Enum):
    """账户的会计职责，不代表具体游戏玩法。"""

    STANDARD = "standard"
    ESCROW = "escrow"
    ISSUER = "issuer"


@dataclass(frozen=True)
class LedgerAccount:
    """一种货币下的独立账户及其当前余额。"""

    id: str
    owner_kind: StableId
    owner_id: str
    currency_id: StableId
    kind: LedgerAccountKind = LedgerAccountKind.STANDARD
    balance: int = 0
    revision: int = 0

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.owner_id.strip():
            raise ValueError("LedgerAccount 缺少账户或所有者 id")
        object.__setattr__(self, "owner_kind", stable_id(self.owner_kind, field="owner kind"))
        object.__setattr__(self, "currency_id", stable_id(self.currency_id, field="currency id"))
        object.__setattr__(self, "kind", LedgerAccountKind(self.kind))
        if not isinstance(self.balance, int) or isinstance(self.balance, bool):
            raise TypeError("LedgerAccount.balance 必须是整数最小单位")
        if self.revision < 0:
            raise ValueError("LedgerAccount.revision 不能小于 0")
        if self.kind is LedgerAccountKind.ISSUER and self.balance > 0:
            raise ValueError("发行账户余额不能大于 0")
        if self.kind is not LedgerAccountKind.ISSUER and self.balance < 0:
            raise ValueError("非发行账户余额不能小于 0")


@dataclass(frozen=True)
class FundHold:
    """业务流程冻结在原账户内、尚未转移所有权的资金。"""

    id: str
    account_id: str
    amount: int
    business_kind: StableId
    business_id: str
    created_at: datetime
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.account_id.strip() or not self.business_id.strip():
            raise ValueError("FundHold 缺少必要 id")
        if not isinstance(self.amount, int) or isinstance(self.amount, bool) or self.amount < 1:
            raise ValueError("FundHold.amount 必须是大于 0 的整数")
        object.__setattr__(
            self,
            "business_kind",
            stable_id(self.business_kind, field="hold business kind"),
        )
        for field_name, value in (("created_at", self.created_at), ("expires_at", self.expires_at)):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError(f"FundHold.{field_name} 必须包含时区")
        if self.expires_at is not None and self.expires_at <= self.created_at:
            raise ValueError("FundHold.expires_at 必须晚于 created_at")

    def active_at(self, logical_time: datetime) -> bool:
        return self.expires_at is None or logical_time < self.expires_at


@dataclass(frozen=True)
class LedgerPosting:
    """流水中的一个账户增减分录，正数入账、负数出账。"""

    account_id: str
    amount: int

    def __post_init__(self) -> None:
        if not self.account_id.strip():
            raise ValueError("LedgerPosting 缺少 account_id")
        if not isinstance(self.amount, int) or isinstance(self.amount, bool) or self.amount == 0:
            raise ValueError("LedgerPosting.amount 必须是非零整数")


@dataclass(frozen=True)
class JournalEntry:
    """同一货币内借贷平衡且不可拆开的资金事实。"""

    id: str
    transaction_id: str
    currency_id: StableId
    reason: StableId
    actor_id: str
    logical_time: datetime
    postings: tuple[LedgerPosting, ...]
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.transaction_id.strip() or not self.actor_id.strip():
            raise ValueError("JournalEntry 缺少必要 id")
        object.__setattr__(self, "currency_id", stable_id(self.currency_id, field="currency id"))
        object.__setattr__(self, "reason", stable_id(self.reason, field="journal reason"))
        if self.logical_time.tzinfo is None or self.logical_time.utcoffset() is None:
            raise ValueError("JournalEntry.logical_time 必须包含时区")
        if len(self.postings) < 2 or sum(value.amount for value in self.postings) != 0:
            raise ValueError("JournalEntry 必须至少包含两条且借贷合计为 0")
        if len({value.account_id for value in self.postings}) != len(self.postings):
            raise ValueError("JournalEntry 中同一账户只能出现一次")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class AppliedLedgerTransaction:
    transaction_id: str
    fingerprint: str
    resulting_revision: int

    def __post_init__(self) -> None:
        if not self.transaction_id.strip() or not self.fingerprint.strip():
            raise ValueError("AppliedLedgerTransaction 缺少事务信息")
        if self.resulting_revision < 1:
            raise ValueError("AppliedLedgerTransaction.resulting_revision 必须大于 0")


@dataclass(frozen=True)
class LedgerState:
    """可由持久化层整体替换的经济账本快照。"""

    accounts: Mapping[str, LedgerAccount] = field(default_factory=dict)
    holds: Mapping[str, FundHold] = field(default_factory=dict)
    journal: tuple[JournalEntry, ...] = ()
    applied_transactions: Mapping[str, AppliedLedgerTransaction] = field(default_factory=dict)
    revision: int = 0

    def __post_init__(self) -> None:
        accounts = dict(self.accounts)
        holds = dict(self.holds)
        transactions = dict(self.applied_transactions)
        if self.revision < 0:
            raise ValueError("LedgerState.revision 不能小于 0")
        for key, account in accounts.items():
            if key != account.id:
                raise ValueError(f"账户映射键与 id 不一致：{key}")
        issuer_currencies = [
            account.currency_id
            for account in accounts.values()
            if account.kind is LedgerAccountKind.ISSUER
        ]
        if len(issuer_currencies) != len(set(issuer_currencies)):
            raise ValueError("同一种货币只能存在一个发行账户")
        held_totals: dict[str, int] = {}
        for key, hold in holds.items():
            if key != hold.id or hold.account_id not in accounts:
                raise ValueError(f"资金预约映射或账户引用无效：{key}")
            account = accounts[hold.account_id]
            if account.kind is LedgerAccountKind.ISSUER:
                raise ValueError("发行账户不能冻结资金")
            held_totals[account.id] = held_totals.get(account.id, 0) + hold.amount
        for account_id, held in held_totals.items():
            if held > accounts[account_id].balance:
                raise ValueError(f"账户 {account_id} 的冻结资金超过余额")
        entry_ids: set[str] = set()
        for entry in self.journal:
            if entry.id in entry_ids:
                raise ValueError(f"重复流水 id：{entry.id}")
            entry_ids.add(entry.id)
            for posting in entry.postings:
                account = accounts.get(posting.account_id)
                if account is None or account.currency_id != entry.currency_id:
                    raise ValueError(f"流水 {entry.id} 引用了未知或错误币种账户")
        for key, record in transactions.items():
            if key != record.transaction_id or record.resulting_revision > self.revision:
                raise ValueError(f"账本事务防重记录无效：{key}")
        object.__setattr__(self, "accounts", MappingProxyType(accounts))
        object.__setattr__(self, "holds", MappingProxyType(holds))
        object.__setattr__(self, "applied_transactions", MappingProxyType(transactions))

    def held_balance(self, account_id: str, *, logical_time: datetime | None = None) -> int:
        holds = (value for value in self.holds.values() if value.account_id == account_id)
        if logical_time is not None:
            holds = (value for value in holds if value.active_at(logical_time))
        return sum(value.amount for value in holds)

    def available_balance(self, account_id: str, *, logical_time: datetime | None = None) -> int:
        account = self.accounts[account_id]
        if account.kind is LedgerAccountKind.ISSUER:
            raise ValueError("发行账户没有可用余额概念")
        return account.balance - self.held_balance(account_id, logical_time=logical_time)


__all__ = [
    "AppliedLedgerTransaction",
    "FundHold",
    "JournalEntry",
    "LedgerAccount",
    "LedgerAccountKind",
    "LedgerPosting",
    "LedgerState",
]
