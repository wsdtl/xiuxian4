"""武器装备珍藏状态的 SQLite 唯一写入口。"""

from __future__ import annotations

from dataclasses import dataclass

from ..gameplay.context import RuleContext
from ..gameplay.errors import RuleFailure, RuleOutcome
from ..gameplay.inventory import (
    InventoryEngine,
    InventoryState,
    InventoryTransaction,
    ProtectAsset,
    UnprotectAsset,
)
from .snapshots import INVENTORY_AGGREGATE, SnapshotRepository
from .sqlite import SqliteDatabase


@dataclass(frozen=True)
class InventoryProtectionExecution:
    asset_id: str
    protected: bool
    changed: bool
    inventory_revision: int


class PersistedInventoryProtectionService:
    """原子更新库存聚合中的珍藏集合，不改写物品实例数据。"""

    def __init__(
        self,
        database: SqliteDatabase,
        engine: InventoryEngine,
        snapshots: SnapshotRepository | None = None,
    ) -> None:
        self.database = database
        self.engine = engine
        self.snapshots = snapshots or SnapshotRepository()

    def set_protected(
        self,
        owner_id: str,
        asset_id: str,
        protected: bool,
        *,
        context: RuleContext,
    ) -> RuleOutcome[InventoryProtectionExecution]:
        if not owner_id.strip() or not asset_id.strip():
            raise ValueError("珍藏操作缺少角色或物品标识")
        with self.database.unit_of_work() as uow:
            previous = self.snapshots.require(
                uow,
                INVENTORY_AGGREGATE,
                owner_id,
                InventoryState,
            )
            instance = previous.instances.get(asset_id)
            if instance is None:
                return RuleOutcome.failed(
                    RuleFailure("inventory.instance_unknown", "只有武器和装备可以加入珍藏")
                )
            definition = self.engine.catalog.require(instance.definition_id)
            if not (
                definition.tags.has("item.weapon")
                or definition.tags.has("item.equipment")
            ):
                return RuleOutcome.failed(
                    RuleFailure("inventory.protection_kind_invalid", "只有武器和装备可以加入珍藏")
                )
            operation = ProtectAsset(asset_id) if protected else UnprotectAsset(asset_id)
            outcome = self.engine.execute(
                InventoryTransaction(
                    context.trace_id,
                    owner_id,
                    "inventory.protect_asset" if protected else "inventory.unprotect_asset",
                    (operation,),
                ),
                state=previous,
                context=context,
            )
            if outcome.failure:
                return RuleOutcome.failed(outcome.failure)
            assert outcome.value is not None
            current = outcome.value.state
            changed = current != previous
            if changed:
                self.snapshots.update(
                    uow,
                    INVENTORY_AGGREGATE,
                    owner_id,
                    previous,
                    current,
                    context.logical_time,
                )
            uow.commit()
            return RuleOutcome.success(
                InventoryProtectionExecution(
                    asset_id,
                    protected,
                    changed,
                    current.revision,
                )
            )


__all__ = ["InventoryProtectionExecution", "PersistedInventoryProtectionService"]
