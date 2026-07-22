"""统一估价、回收报价、二手挂单与近期交易风险模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Mapping

from game.core.gameplay import ItemInstance, ItemStack, StableId, stable_id


ECONOMY_RULESET_VERSION = "rules.economy.v1"
MARKET_AGGREGATE = "snapshot.market"
MARKET_SCOPE_ID = "market.primary"
PRIMARY_TAX_ACCOUNT_ID = "ledger_account.tax.central"
PRIMARY_TAX_OWNER_ID = "tax.central"


@dataclass(frozen=True)
class GearPriceQuote:
    asset_id: str
    definition_id: StableId
    kind: str
    quality_id: StableId
    slot_id: StableId
    value_score: float
    reference_price: int
    currency_id: StableId
    policy_id: StableId
    policy_version: int

    def __post_init__(self) -> None:
        if not self.asset_id.strip() or self.kind not in {"weapon", "equipment"}:
            raise ValueError("装备参考价缺少资产身份或类型")
        for field_name in ("definition_id", "quality_id", "slot_id", "currency_id", "policy_id"):
            object.__setattr__(
                self,
                field_name,
                stable_id(getattr(self, field_name), field=field_name),
            )
        if self.value_score <= 0 or self.reference_price < 1 or self.policy_version < 1:
            raise ValueError("装备参考价值必须大于 0")


@dataclass(frozen=True)
class MarketPriceQuote:
    """市场统一核算价；实例和堆叠物品共用同一种成交报价。"""

    asset_id: str
    definition_id: StableId
    asset_kind: str
    category: str
    quantity: int
    unit_reference_price: int
    reference_price: int
    currency_id: StableId
    minimum_price_bps: int
    maximum_price_bps: int
    policy_id: StableId
    policy_version: int
    slot_id: str = ""

    def __post_init__(self) -> None:
        if not self.asset_id.strip() or self.asset_kind not in {"instance", "stack"}:
            raise ValueError("市场参考价缺少资产身份或类型")
        if not self.category.strip():
            raise ValueError("市场参考价缺少分类")
        for field_name in ("definition_id", "currency_id", "policy_id"):
            object.__setattr__(
                self,
                field_name,
                stable_id(getattr(self, field_name), field=field_name),
            )
        integers = (
            self.quantity,
            self.unit_reference_price,
            self.reference_price,
            self.minimum_price_bps,
            self.maximum_price_bps,
            self.policy_version,
        )
        if any(isinstance(value, bool) or not isinstance(value, int) for value in integers):
            raise TypeError("市场参考价数值必须是整数")
        if min(self.quantity, self.unit_reference_price, self.reference_price) < 1:
            raise ValueError("市场参考价数量和金额必须大于 0")
        if self.reference_price != self.unit_reference_price * self.quantity:
            raise ValueError("市场参考总价与单价、数量不一致")
        if not 1 <= self.minimum_price_bps <= 10_000:
            raise ValueError("市场最低正常价格比例无效")
        if self.maximum_price_bps < 10_000 or self.policy_version < 1:
            raise ValueError("市场最高正常价格比例或政策版本无效")


@dataclass(frozen=True)
class MarketTaxQuote:
    reference_price: int
    list_price: int
    buyer_total: int
    seller_proceeds: int
    tax_amount: int
    normal_tax_rate_bps: int
    low_price_surcharge: int
    high_price_tax: int
    risk_surcharge: int
    repeated_pair_trades: int
    repeated_asset_trades: int
    policy_id: StableId
    policy_version: int

    def __post_init__(self) -> None:
        values = (
            self.reference_price,
            self.list_price,
            self.buyer_total,
            self.seller_proceeds,
            self.tax_amount,
            self.risk_surcharge,
        )
        if any(value < 0 for value in values) or min(values[:4]) < 1:
            raise ValueError("二手税务报价金额无效")
        if self.buyer_total != self.seller_proceeds + self.tax_amount:
            raise ValueError("二手税务报价拆账不守恒")
        if not 0 <= self.normal_tax_rate_bps <= 10_000:
            raise ValueError("二手常规税率无效")
        object.__setattr__(self, "policy_id", stable_id(self.policy_id, field="policy id"))
        if self.policy_version < 1:
            raise ValueError("二手税务策略版本无效")


@dataclass(frozen=True)
class RecycleQuoteLine:
    asset_id: str
    reference_number: int
    definition_id: StableId
    kind: str
    slot_id: StableId
    quality_id: StableId
    reference_price: int
    recycle_amount: int

    def __post_init__(self) -> None:
        if not self.asset_id.strip() or self.reference_number < 1:
            raise ValueError("回收报价行缺少物品身份")
        for field_name in ("definition_id", "slot_id", "quality_id"):
            object.__setattr__(
                self,
                field_name,
                stable_id(getattr(self, field_name), field=field_name),
            )
        if self.reference_price < 1 or self.recycle_amount < 1:
            raise ValueError("回收报价金额必须大于 0")


@dataclass(frozen=True)
class RecycleQuote:
    id: str
    owner_id: str
    inventory_revision: int
    currency_id: StableId
    lines: tuple[RecycleQuoteLine, ...]
    total_reference_price: int
    total_amount: int
    policy_id: StableId
    policy_version: int
    selection_key: str = ""

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.owner_id.strip() or self.inventory_revision < 0:
            raise ValueError("回收报价缺少身份或库存版本")
        object.__setattr__(self, "currency_id", stable_id(self.currency_id, field="currency id"))
        object.__setattr__(self, "policy_id", stable_id(self.policy_id, field="policy id"))
        if not isinstance(self.selection_key, str):
            raise ValueError("回收报价筛选身份必须是字符串")
        lines = tuple(self.lines)
        if not lines or len({line.asset_id for line in lines}) != len(lines):
            raise ValueError("回收报价必须包含唯一物品")
        if self.total_reference_price != sum(line.reference_price for line in lines):
            raise ValueError("回收参考价合计不一致")
        if self.total_amount != sum(line.recycle_amount for line in lines):
            raise ValueError("回收金额合计不一致")
        object.__setattr__(self, "lines", lines)


@dataclass(frozen=True)
class MarketListing:
    id: str
    number: int
    seller_id: str
    seller_name: str
    seller_wallet_account_id: str
    asset: ItemInstance | ItemStack
    price: MarketPriceQuote | GearPriceQuote
    list_price: int
    reservation_id: str
    opened_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        if not all(
            (
                self.id.strip(),
                self.seller_id.strip(),
                self.seller_name.strip(),
                self.seller_wallet_account_id.strip(),
                self.reservation_id.strip(),
            )
        ):
            raise ValueError("二手挂单缺少身份")
        if self.number < 1 or self.list_price < 1 or self.asset.id != self.price.asset_id:
            raise ValueError("二手挂单编号、价格或物品不一致")
        _aware(self.opened_at, "MarketListing.opened_at")
        _aware(self.expires_at, "MarketListing.expires_at")
        if self.expires_at <= self.opened_at:
            raise ValueError("二手挂单到期时间无效")


@dataclass(frozen=True)
class MarketTradeRecord:
    id: str
    listing_id: str
    asset_id: str
    seller_id: str
    buyer_id: str
    reference_price: int
    list_price: int
    buyer_total: int
    seller_proceeds: int
    tax_amount: int
    settled_at: datetime
    definition_id: str = ""
    asset_kind: str = "instance"
    quantity: int = 1

    def __post_init__(self) -> None:
        if not all(
            (
                self.id.strip(),
                self.listing_id.strip(),
                self.asset_id.strip(),
                self.seller_id.strip(),
                self.buyer_id.strip(),
            )
        ):
            raise ValueError("二手成交记录缺少身份")
        _aware(self.settled_at, "MarketTradeRecord.settled_at")
        if self.buyer_total != self.seller_proceeds + self.tax_amount:
            raise ValueError("二手成交记录拆账不守恒")
        if self.asset_kind not in {"instance", "stack"} or self.quantity < 1:
            raise ValueError("二手成交记录资产类型或数量无效")


@dataclass(frozen=True)
class MarketState:
    scope_id: str = MARKET_SCOPE_ID
    listings: Mapping[str, MarketListing] = field(default_factory=dict)
    recent_trades: tuple[MarketTradeRecord, ...] = ()
    next_listing_number: int = 1
    revision: int = 0

    def __post_init__(self) -> None:
        if not self.scope_id.strip() or self.next_listing_number < 1 or self.revision < 0:
            raise ValueError("二手市场状态身份或版本无效")
        listings = dict(self.listings)
        if any(key != value.id for key, value in listings.items()):
            raise ValueError("二手挂单映射键与 ID 不一致")
        if len({value.number for value in listings.values()}) != len(listings):
            raise ValueError("二手挂单展示编号不能重复")
        object.__setattr__(self, "listings", MappingProxyType(listings))
        object.__setattr__(self, "recent_trades", tuple(self.recent_trades))


def _aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} 必须包含时区")


__all__ = [
    "ECONOMY_RULESET_VERSION",
    "MARKET_AGGREGATE",
    "MARKET_SCOPE_ID",
    "PRIMARY_TAX_ACCOUNT_ID",
    "PRIMARY_TAX_OWNER_ID",
    "GearPriceQuote",
    "MarketPriceQuote",
    "MarketListing",
    "MarketState",
    "MarketTaxQuote",
    "MarketTradeRecord",
    "RecycleQuote",
    "RecycleQuoteLine",
]
