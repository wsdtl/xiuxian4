"""交换报价、资产承诺、契约生命周期和结算凭据。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from ..economy import LedgerState
from ..events import RuleEvent
from ..ids import StableId, stable_id
from ..inventory import InventoryState


class ExchangeStatus(str, Enum):
    OPEN = "open"
    COMMITTED = "committed"
    SETTLED = "settled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


@dataclass(frozen=True)
class ExchangeQuoteLine:
    kind_id: StableId
    destination_account_id: str
    amount: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind_id", stable_id(self.kind_id, field="quote line kind"))
        if not self.destination_account_id.strip() or self.amount < 1:
            raise ValueError("交换报价分配无效")


@dataclass(frozen=True)
class ExchangeQuote:
    id: str
    version: int
    currency_id: StableId
    total_amount: int
    allocations: tuple[ExchangeQuoteLine, ...]
    policy_id: StableId
    policy_version: int
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip() or self.version < 1 or self.total_amount < 1:
            raise ValueError("交换报价身份、版本或总额无效")
        object.__setattr__(self, "currency_id", stable_id(self.currency_id, field="currency id"))
        object.__setattr__(self, "policy_id", stable_id(self.policy_id, field="quote policy id"))
        if self.policy_version < 1:
            raise ValueError("报价策略版本必须大于 0")
        allocations = tuple(self.allocations)
        if not allocations or sum(line.amount for line in allocations) != self.total_amount:
            raise ValueError("交换报价分配合计必须等于总额")
        object.__setattr__(self, "allocations", allocations)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class ExchangeAssetOffer:
    id: StableId
    source_asset_id: str
    transfer_asset_id: str
    quantity: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="exchange offer id"))
        if not self.source_asset_id.strip() or not self.transfer_asset_id.strip() or self.quantity < 1:
            raise ValueError("交换资产承诺无效")

    @property
    def reservation_id(self) -> str:
        return f"exchange-reservation:{self.id}:{self.transfer_asset_id}"


@dataclass(frozen=True)
class ExchangeContract:
    id: str
    kind_id: StableId
    creator_id: str
    quote: ExchangeQuote
    asset_offers: tuple[ExchangeAssetOffer, ...]
    opened_at: datetime
    expires_at: datetime
    allowed_counterparty_id: str | None = None
    status: ExchangeStatus = ExchangeStatus.OPEN
    buyer_id: str | None = None
    payer_account_id: str | None = None
    fund_hold_id: str | None = None
    destinations: Mapping[StableId, str] = field(default_factory=dict)
    revision: int = 0

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.creator_id.strip() or self.revision < 0:
            raise ValueError("交换契约身份或 revision 无效")
        object.__setattr__(self, "kind_id", stable_id(self.kind_id, field="exchange kind id"))
        _aware(self.opened_at, "ExchangeContract.opened_at")
        _aware(self.expires_at, "ExchangeContract.expires_at")
        if self.expires_at <= self.opened_at:
            raise ValueError("交换契约期限必须晚于创建时间")
        offers = tuple(self.asset_offers)
        if not offers or len({offer.id for offer in offers}) != len(offers):
            raise ValueError("交换契约必须包含唯一资产承诺")
        status = ExchangeStatus(self.status)
        destinations = {
            stable_id(key, field="exchange offer id"): str(value)
            for key, value in self.destinations.items()
        }
        committed = status in {ExchangeStatus.COMMITTED, ExchangeStatus.SETTLED}
        commitment_values = (self.buyer_id, self.payer_account_id, self.fund_hold_id)
        if committed and (any(not value for value in commitment_values) or set(destinations) != {o.id for o in offers}):
            raise ValueError("已承诺契约缺少买方、资金冻结或目标容器")
        if not committed and (any(value is not None for value in commitment_values) or destinations):
            raise ValueError("未承诺契约不能携带买方结算信息")
        object.__setattr__(self, "asset_offers", offers)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "allowed_counterparty_id", _optional(self.allowed_counterparty_id))
        object.__setattr__(self, "destinations", MappingProxyType(destinations))


@dataclass(frozen=True)
class ExchangeState:
    scope_id: str
    contracts: Mapping[str, ExchangeContract] = field(default_factory=dict)
    revision: int = 0

    def __post_init__(self) -> None:
        if not self.scope_id.strip() or self.revision < 0:
            raise ValueError("ExchangeState 身份或 revision 无效")
        contracts = dict(self.contracts)
        if any(key != value.id for key, value in contracts.items()):
            raise ValueError("交换契约映射键与 ID 不一致")
        object.__setattr__(self, "contracts", MappingProxyType(contracts))


@dataclass(frozen=True)
class OpenExchange:
    contract: ExchangeContract


@dataclass(frozen=True)
class CommitExchange:
    contract_id: str
    buyer_id: str
    payer_account_id: str
    quote_id: str
    quote_version: int
    destinations: Mapping[StableId, str]

    def __post_init__(self) -> None:
        if not all((self.contract_id.strip(), self.buyer_id.strip(), self.payer_account_id.strip(), self.quote_id.strip())):
            raise ValueError("交换承诺缺少身份")
        if self.quote_version < 1:
            raise ValueError("交换承诺报价版本无效")
        object.__setattr__(
            self,
            "destinations",
            MappingProxyType(
                {
                    stable_id(key, field="exchange offer id"): str(value)
                    for key, value in self.destinations.items()
                }
            ),
        )


@dataclass(frozen=True)
class SettleExchange:
    contract_id: str


@dataclass(frozen=True)
class CancelExchange:
    contract_id: str


@dataclass(frozen=True)
class ExpireExchange:
    contract_id: str


@dataclass(frozen=True)
class ExchangeCommand:
    id: str
    actor_id: str
    expected_revision: int
    operation: object

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.actor_id.strip() or self.expected_revision < 0:
            raise ValueError("ExchangeCommand 身份或 revision 无效")


@dataclass(frozen=True)
class ExchangeExecution:
    command_id: str
    exchange: ExchangeState
    inventory: InventoryState
    ledger: LedgerState
    contract: ExchangeContract
    events: tuple[RuleEvent, ...]


def _optional(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} 必须包含时区")


__all__ = [
    "CancelExchange",
    "CommitExchange",
    "ExchangeAssetOffer",
    "ExchangeCommand",
    "ExchangeContract",
    "ExchangeExecution",
    "ExchangeQuote",
    "ExchangeQuoteLine",
    "ExchangeState",
    "ExchangeStatus",
    "ExpireExchange",
    "OpenExchange",
    "SettleExchange",
]
