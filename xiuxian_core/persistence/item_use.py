"""物品扣除、角色资源变化、防重回执与 Outbox 的 SQLite 联合提交。"""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256

from ..gameplay.context import RuleContext
from ..gameplay.errors import RuleOutcome
from ..gameplay.inventory import (
    CharacterItemUse,
    CharacterItemUseEngine,
    ItemUseReceipt,
    item_use_fingerprint,
)
from ..gameplay.character import CharacterState
from ..gameplay.inventory import InventoryState
from .errors import TransactionMismatch
from .snapshots import CHARACTER_AGGREGATE, INVENTORY_AGGREGATE, SnapshotRepository
from .sqlite import SqliteDatabase


class PersistedItemUseService:
    """物品使用的唯一数据库写入口。"""

    def __init__(
        self,
        database: SqliteDatabase,
        engine: CharacterItemUseEngine,
        snapshots: SnapshotRepository | None = None,
    ) -> None:
        self.database = database
        self.engine = engine
        self.snapshots = snapshots or SnapshotRepository()

    def use(
        self,
        command: CharacterItemUse,
        *,
        inventory_id: str,
        context: RuleContext,
    ) -> RuleOutcome[ItemUseReceipt]:
        if not inventory_id.strip():
            raise ValueError("inventory_id 不能为空")
        checkpoint = context.random.checkpoint()
        try:
            with self.database.unit_of_work() as uow:
                fingerprint = _persistence_fingerprint(command, inventory_id)
                committed = uow.load_transaction(command.id)
                if committed is not None:
                    if (
                        committed.fingerprint != fingerprint
                        or committed.scope_id != command.actor_id
                    ):
                        raise TransactionMismatch(
                            f"同一物品使用事务 ID 对应不同内容：{command.id}"
                        )
                    receipt = self.snapshots.codec.loads(
                        committed.receipt_payload,
                        ItemUseReceipt,
                    )
                    return RuleOutcome.success(replace(receipt, replayed=True))

                inventory = self.snapshots.require(
                    uow,
                    INVENTORY_AGGREGATE,
                    inventory_id,
                    InventoryState,
                )
                character_ids = tuple(dict.fromkeys((command.actor_id, command.target_id)))
                characters = {
                    character_id: self.snapshots.require(
                        uow,
                        CHARACTER_AGGREGATE,
                        character_id,
                        CharacterState,
                    )
                    for character_id in character_ids
                }
                outcome = self.engine.execute(
                    command,
                    inventory=inventory,
                    characters=characters,
                    context=context,
                )
                if outcome.failure:
                    return RuleOutcome.failed(outcome.failure)
                assert outcome.value is not None

                if outcome.value.inventory != inventory:
                    self.snapshots.update(
                        uow,
                        INVENTORY_AGGREGATE,
                        inventory_id,
                        inventory,
                        outcome.value.inventory,
                        context.logical_time,
                    )
                for character_id, previous in characters.items():
                    current = outcome.value.characters[character_id]
                    if current != previous:
                        self.snapshots.update(
                            uow,
                            CHARACTER_AGGREGATE,
                            character_id,
                            previous,
                            current,
                            context.logical_time,
                        )
                timestamp = context.logical_time.isoformat()
                uow.insert_transaction(
                    command.id,
                    fingerprint,
                    command.actor_id,
                    self.snapshots.codec.dumps(outcome.value.receipt),
                    timestamp,
                )
                for sequence, event in enumerate(outcome.value.events):
                    uow.append_outbox(
                        command.id,
                        sequence,
                        event.kind,
                        self.snapshots.codec.dumps(event),
                        timestamp,
                    )
                uow.commit()
                return RuleOutcome.success(outcome.value.receipt)
        except Exception:
            context.random.restore(checkpoint)
            raise


def _persistence_fingerprint(command: CharacterItemUse, inventory_id: str) -> str:
    payload = f"{item_use_fingerprint(command)}|{inventory_id}"
    return sha256(payload.encode("utf-8")).hexdigest()


__all__ = ["PersistedItemUseService"]
