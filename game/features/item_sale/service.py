"""在同一工作单元内扣除战利品并向角色钱包入账。"""

from datetime import datetime

from game.core.gameplay import (
    ConsumeStack,
    InventoryState,
    InventoryTransaction,
    IssueFunds,
    LedgerAccountKind,
    LedgerState,
    LedgerTransaction,
    RuleContext,
    Ruleset,
    SeededRandomSource,
)
from game.rules.character import PRIMARY_LEDGER_ID
from game.rules.item import ITEM_SALE_RULESET_VERSION, quote_trophy_sale

from .models import ItemSaleResult, ItemSaleStorageKinds


class ItemSaleFeature:
    """执行系统固定价收购，不包含命令和展示。"""

    def __init__(
        self,
        database,
        snapshots,
        item_catalog,
        inventory_engine,
        ledger_engine,
        storage: ItemSaleStorageKinds,
    ) -> None:
        self.database = database
        self.snapshots = snapshots
        self.item_catalog = item_catalog
        self.inventory_engine = inventory_engine
        self.ledger_engine = ledger_engine
        self.storage = storage

    def sell_trophies(
        self,
        character_id: str,
        *,
        logical_time: datetime,
    ) -> ItemSaleResult:
        with self.database.unit_of_work() as uow:
            inventory = self.snapshots.require(
                uow,
                self.storage.inventory,
                character_id,
                InventoryState,
            )
            quote = quote_trophy_sale(inventory, self.item_catalog, character_id)
            if not quote.lines:
                return ItemSaleResult("empty", quote)
            ledger = self.snapshots.require(
                uow,
                self.storage.ledger,
                PRIMARY_LEDGER_ID,
                LedgerState,
            )
            issuer = next(
                account
                for account in ledger.accounts.values()
                if account.kind is LedgerAccountKind.ISSUER
                and account.currency_id == quote.currency_id
            )
            wallet = next(
                account
                for account in ledger.accounts.values()
                if account.kind is LedgerAccountKind.STANDARD
                and account.owner_kind == "owner.character"
                and account.owner_id == character_id
                and account.currency_id == quote.currency_id
            )
            context = _context(quote.id, logical_time)
            inventory_outcome = self.inventory_engine.execute(
                InventoryTransaction(
                    f"{quote.id}:inventory",
                    character_id,
                    "inventory.sell_trophies",
                    tuple(
                        ConsumeStack(line.asset_id, line.quantity)
                        for line in quote.lines
                    ),
                ),
                state=inventory,
                context=context,
            )
            if inventory_outcome.failure or inventory_outcome.value is None:
                raise RuntimeError(
                    inventory_outcome.failure.message
                    if inventory_outcome.failure
                    else "战利品扣除失败"
                )
            ledger_outcome = self.ledger_engine.execute(
                LedgerTransaction(
                    f"{quote.id}:ledger",
                    character_id,
                    "economy.sell_trophies",
                    (IssueFunds(issuer.id, wallet.id, quote.total_amount),),
                    expected_revisions={
                        issuer.id: issuer.revision,
                        wallet.id: wallet.revision,
                    },
                    metadata={"quote_id": quote.id},
                ),
                state=ledger,
                context=context,
            )
            if ledger_outcome.failure or ledger_outcome.value is None:
                raise RuntimeError(
                    ledger_outcome.failure.message
                    if ledger_outcome.failure
                    else "战利品入账失败"
                )
            self.snapshots.update(
                uow,
                self.storage.inventory,
                character_id,
                inventory,
                inventory_outcome.value.state,
                logical_time,
            )
            self.snapshots.update(
                uow,
                self.storage.ledger,
                PRIMARY_LEDGER_ID,
                ledger,
                ledger_outcome.value.state,
                logical_time,
            )
            uow.commit()
            return ItemSaleResult("sold", quote)


def _context(trace_id: str, logical_time: datetime) -> RuleContext:
    return RuleContext(
        trace_id,
        ITEM_SALE_RULESET_VERSION,
        Ruleset("ruleset.standard"),
        logical_time,
        SeededRandomSource(trace_id),
    )


__all__ = ["ItemSaleFeature"]
