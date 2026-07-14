"""账号角色目录与角色初始快照的 SQLite 原子登记。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from hashlib import sha256
from typing import Protocol

from ..gameplay.character import CharacterRosterState, CharacterState
from ..gameplay.context import RuleContext
from ..gameplay.economy import LedgerState
from ..gameplay.inventory import InventoryState
from ..gameplay.loadout import LoadoutState
from ..gameplay.world import WorldState

from .errors import (
    AggregateNotFound,
    ConcurrencyConflict,
    CorruptPersistenceData,
    TransactionMismatch,
)
from .snapshots import (
    CHARACTER_AGGREGATE,
    CHARACTER_ROSTER_AGGREGATE,
    INVENTORY_AGGREGATE,
    LEDGER_AGGREGATE,
    LOADOUT_AGGREGATE,
    WORLD_AGGREGATE,
    SnapshotRepository,
    gameplay_snapshot_codec,
)
from .sqlite import SqliteDatabase


@dataclass(frozen=True)
class PersistedCharacterRegistration:
    character: CharacterState
    roster: CharacterRosterState
    replayed: bool = False


class PersistedCharacterService:
    """原子登记角色，并按配置限制每个账号拥有的角色数量。"""

    def __init__(
        self,
        database: SqliteDatabase,
        *,
        maximum_characters_per_account: int = 1,
        snapshots: SnapshotRepository | None = None,
    ) -> None:
        if maximum_characters_per_account < 1:
            raise ValueError("账号角色数量上限必须大于 0")
        self.database = database
        self.maximum_characters_per_account = maximum_characters_per_account
        self.snapshots = snapshots or SnapshotRepository()

    def register(
        self,
        character: CharacterState,
        *,
        transaction_id: str,
        logical_time: datetime,
    ) -> PersistedCharacterRegistration:
        _aware(logical_time)
        transaction_id = str(transaction_id or "").strip()
        if not transaction_id:
            raise ValueError("角色登记缺少 transaction_id")
        fingerprint = self._fingerprint(character)
        with self.database.unit_of_work() as uow:
            previous = uow.load_transaction(transaction_id)
            if previous is not None:
                if (
                    previous.fingerprint != fingerprint
                    or previous.scope_id != character.account_id
                ):
                    raise TransactionMismatch("同一角色登记事务对应不同内容")
                replayed_character = self.snapshots.codec.loads(
                    previous.receipt_payload,
                    CharacterState,
                )
                replayed_roster = self.snapshots.require(
                    uow,
                    CHARACTER_ROSTER_AGGREGATE,
                    character.account_id,
                    CharacterRosterState,
                )
                return PersistedCharacterRegistration(
                    replayed_character,
                    replayed_roster,
                    True,
                )

            account = uow.connection.execute(
                "SELECT status FROM account_record WHERE account_id = ?",
                (character.account_id,),
            ).fetchone()
            if account is None:
                raise AggregateNotFound(f"角色登记引用未知账号：{character.account_id}")
            if str(account["status"]) != "active":
                raise ConcurrencyConflict("非活跃账号不能登记角色")

            roster = self.snapshots.load(
                uow,
                CHARACTER_ROSTER_AGGREGATE,
                character.account_id,
                CharacterRosterState,
            )
            if roster is None:
                updated_roster = CharacterRosterState(
                    character.account_id,
                    (character.id,),
                )
                self.snapshots.insert(
                    uow,
                    CHARACTER_ROSTER_AGGREGATE,
                    character.account_id,
                    updated_roster,
                    logical_time,
                )
            else:
                if character.id in roster.character_ids:
                    raise ConcurrencyConflict(f"角色已经登记：{character.id}")
                if len(roster.character_ids) >= self.maximum_characters_per_account:
                    raise ConcurrencyConflict(
                        "账号角色数量已达上限："
                        f"{self.maximum_characters_per_account}"
                    )
                updated_roster = replace(
                    roster,
                    character_ids=(*roster.character_ids, character.id),
                    revision=roster.revision + 1,
                )
                self.snapshots.update(
                    uow,
                    CHARACTER_ROSTER_AGGREGATE,
                    character.account_id,
                    roster,
                    updated_roster,
                    logical_time,
                )

            self.snapshots.insert(
                uow,
                CHARACTER_AGGREGATE,
                character.id,
                character,
                logical_time,
            )
            receipt = PersistedCharacterRegistration(character, updated_roster)
            uow.insert_transaction(
                transaction_id,
                fingerprint,
                character.account_id,
                self.snapshots.codec.dumps(character),
                logical_time.isoformat(),
            )
            uow.commit()
            return receipt

    def character_ids_for(self, account_id: str) -> tuple[str, ...]:
        with self.database.unit_of_work(write=False) as uow:
            roster = self.snapshots.load(
                uow,
                CHARACTER_ROSTER_AGGREGATE,
                str(account_id or "").strip(),
                CharacterRosterState,
            )
            return roster.character_ids if roster is not None else ()

    def load_character(self, character_id: str) -> CharacterState | None:
        with self.database.unit_of_work(write=False) as uow:
            return self.snapshots.load(
                uow,
                CHARACTER_AGGREGATE,
                str(character_id or "").strip(),
                CharacterState,
            )

    def load_for_account(self, account_id: str) -> CharacterState | None:
        account_id = str(account_id or "").strip()
        with self.database.unit_of_work(write=False) as uow:
            roster = self.snapshots.load(
                uow,
                CHARACTER_ROSTER_AGGREGATE,
                account_id,
                CharacterRosterState,
            )
            if roster is None or not roster.character_ids:
                return None
            if len(roster.character_ids) != 1:
                raise CorruptPersistenceData(
                    f"单角色服务读取到多个角色：{account_id}"
                )
            return self.snapshots.require(
                uow,
                CHARACTER_AGGREGATE,
                roster.character_ids[0],
                CharacterState,
            )

    def _fingerprint(self, character: CharacterState) -> str:
        payload = self.snapshots.codec.dumps(character)
        value = (
            f"character-register.v1\0{self.maximum_characters_per_account}\0{payload}"
        )
        return sha256(value.encode("utf-8")).hexdigest()


class CharacterCreationWorkflow(Protocol):
    """持久化层调用的创世协议；具体游戏在外部实现全部规则选择。"""

    def codec_registrations(self) -> tuple[tuple[str, type[object]], ...]: ...
    def transaction_id(self, request: object) -> str: ...
    def account_id(self, request: object) -> str: ...
    def fingerprint(self, request: object) -> str: ...
    def receipt_type(self) -> type[object]: ...
    def mark_replayed(self, receipt: object) -> object: ...
    def ledger_aggregate_id(self) -> str: ...
    def world_aggregate_id(self) -> str: ...
    def prepare(
        self,
        request: object,
        *,
        existing_character_ids: tuple[str, ...],
        ledger: LedgerState | None,
        world: WorldState | None,
        context: RuleContext,
    ) -> object: ...
    def character(self, prepared: object) -> CharacterState: ...
    def inventory_id(self, prepared: object) -> str: ...
    def inventory(self, prepared: object) -> InventoryState: ...
    def loadout(self, prepared: object) -> LoadoutState: ...
    def ledger(self, prepared: object) -> LedgerState: ...
    def world(self, prepared: object) -> WorldState: ...
    def extra_snapshots(
        self,
        prepared: object,
    ) -> tuple[tuple[str, str, object], ...]: ...
    def build_receipt(
        self,
        request: object,
        prepared: object,
        roster: CharacterRosterState,
    ) -> object: ...


class PersistedCharacterCreationService:
    """在一个写事务中提交工作流给出的全部角色初态。"""

    def __init__(
        self,
        database: SqliteDatabase,
        workflow: CharacterCreationWorkflow,
        *,
        maximum_characters_per_account: int = 1,
        snapshots: SnapshotRepository | None = None,
    ) -> None:
        if maximum_characters_per_account < 1:
            raise ValueError("账号角色数量上限必须大于 0")
        self.database = database
        self.workflow = workflow
        self.maximum_characters_per_account = maximum_characters_per_account
        self.snapshots = snapshots or SnapshotRepository(
            gameplay_snapshot_codec(workflow.codec_registrations())
        )

    def create(self, request: object, *, context: RuleContext) -> object:
        _aware(context.logical_time)
        transaction_id = self.workflow.transaction_id(request)
        account_id = self.workflow.account_id(request)
        fingerprint = self.workflow.fingerprint(request)
        with self.database.unit_of_work() as uow:
            previous = uow.load_transaction(transaction_id)
            if previous is not None:
                if previous.scope_id != account_id or previous.fingerprint != fingerprint:
                    raise TransactionMismatch("同一角色创世事务对应不同请求")
                receipt = self.snapshots.codec.loads(
                    previous.receipt_payload,
                    self.workflow.receipt_type(),
                )
                return self.workflow.mark_replayed(receipt)

            account = uow.connection.execute(
                "SELECT status FROM account_record WHERE account_id = ?",
                (account_id,),
            ).fetchone()
            if account is None:
                raise AggregateNotFound(f"角色创世引用未知账号：{account_id}")
            if str(account["status"]) != "active":
                raise ConcurrencyConflict("非活跃账号不能创建角色")

            roster = self.snapshots.load(
                uow,
                CHARACTER_ROSTER_AGGREGATE,
                account_id,
                CharacterRosterState,
            )
            existing_ids = roster.character_ids if roster is not None else ()
            if len(existing_ids) >= self.maximum_characters_per_account:
                raise ConcurrencyConflict(
                    f"账号角色数量已达上限：{self.maximum_characters_per_account}"
                )
            ledger_id = self.workflow.ledger_aggregate_id()
            world_id = self.workflow.world_aggregate_id()
            current_ledger = self.snapshots.load(
                uow, LEDGER_AGGREGATE, ledger_id, LedgerState
            )
            current_world = self.snapshots.load(
                uow, WORLD_AGGREGATE, world_id, WorldState
            )
            prepared = self.workflow.prepare(
                request,
                existing_character_ids=existing_ids,
                ledger=current_ledger,
                world=current_world,
                context=context,
            )
            character = self.workflow.character(prepared)
            if character.account_id != account_id:
                raise ValueError("角色创世工作流返回了其他账号的角色")
            if roster is None:
                next_roster = CharacterRosterState(account_id, (character.id,))
                self.snapshots.insert(
                    uow,
                    CHARACTER_ROSTER_AGGREGATE,
                    account_id,
                    next_roster,
                    context.logical_time,
                )
            else:
                next_roster = replace(
                    roster,
                    character_ids=(*roster.character_ids, character.id),
                    revision=roster.revision + 1,
                )
                self.snapshots.update(
                    uow,
                    CHARACTER_ROSTER_AGGREGATE,
                    account_id,
                    roster,
                    next_roster,
                    context.logical_time,
                )

            inventory_id = self.workflow.inventory_id(prepared)
            self.snapshots.insert(
                uow, CHARACTER_AGGREGATE, character.id, character, context.logical_time
            )
            self.snapshots.insert(
                uow,
                INVENTORY_AGGREGATE,
                inventory_id,
                self.workflow.inventory(prepared),
                context.logical_time,
            )
            self.snapshots.insert(
                uow,
                LOADOUT_AGGREGATE,
                character.id,
                self.workflow.loadout(prepared),
                context.logical_time,
            )
            self._write_shared_snapshot(
                uow,
                LEDGER_AGGREGATE,
                ledger_id,
                current_ledger,
                self.workflow.ledger(prepared),
                context.logical_time,
            )
            self._write_shared_snapshot(
                uow,
                WORLD_AGGREGATE,
                world_id,
                current_world,
                self.workflow.world(prepared),
                context.logical_time,
            )
            reserved = {
                (CHARACTER_AGGREGATE, character.id),
                (INVENTORY_AGGREGATE, inventory_id),
                (LOADOUT_AGGREGATE, character.id),
                (LEDGER_AGGREGATE, ledger_id),
                (WORLD_AGGREGATE, world_id),
            }
            for aggregate_kind, aggregate_id, value in self.workflow.extra_snapshots(prepared):
                key = (aggregate_kind, aggregate_id)
                if key in reserved:
                    raise ValueError("角色创世附加快照与标准快照冲突")
                reserved.add(key)
                self.snapshots.insert(
                    uow, aggregate_kind, aggregate_id, value, context.logical_time
                )

            receipt = self.workflow.build_receipt(request, prepared, next_roster)
            uow.insert_transaction(
                transaction_id,
                fingerprint,
                account_id,
                self.snapshots.codec.dumps(receipt),
                context.logical_time.isoformat(),
            )
            uow.commit()
            return receipt

    def _write_shared_snapshot(
        self,
        uow,
        aggregate_kind: str,
        aggregate_id: str,
        previous: object | None,
        current: object,
        logical_time: datetime,
    ) -> None:
        if previous is None:
            self.snapshots.insert(
                uow, aggregate_kind, aggregate_id, current, logical_time
            )
        else:
            self.snapshots.update(
                uow, aggregate_kind, aggregate_id, previous, current, logical_time
            )


def _aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("角色登记逻辑时间必须包含时区")


__all__ = [
    "CharacterCreationWorkflow",
    "PersistedCharacterCreationService",
    "PersistedCharacterRegistration",
    "PersistedCharacterService",
]
