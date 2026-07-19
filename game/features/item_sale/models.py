"""物品收购玩法公开模型。"""

from dataclasses import dataclass

from game.rules.item import ItemSaleQuote


@dataclass(frozen=True)
class ItemSaleResult:
    status: str
    quote: ItemSaleQuote


@dataclass(frozen=True)
class ItemSaleStorageKinds:
    inventory: str
    ledger: str


__all__ = ["ItemSaleResult", "ItemSaleStorageKinds"]
