"""持久化结构版本、联合提交、CAS、防重与 Outbox 测试。"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from xiuxian_core.gameplay.rewards import (  # noqa: E402
    CharacterFeatureReward,
    CurrencyReward,
    RewardExpectations,
    RewardSettlement,
    StackItemReward,
)
from xiuxian_core.persistence import (  # noqa: E402
    ConcurrencyConflict,
    CorruptPersistenceData,
    INVENTORY_AGGREGATE,
    PERSISTENCE_FOUNDATION_VERSION,
    PERSISTENCE_SCHEMA_VERSION,
    PersistedRewardSettlementService,
    RewardSettlementStorageKeys,
    SchemaVersionError,
    SnapshotRepository,
    SqliteDatabase,
    TransactionMismatch,
)

from reward_settlement_test import (  # noqa: E402
    TIME,
    _complete_settlement,
    _context,
    _environment,
)


def main() -> None:
    _assert_database_schema_rejection()
    with TemporaryDirectory() as directory:
        _assert_atomic_persisted_settlement(Path(directory))
    print("persistence foundation tests passed")


def _assert_database_schema_rejection() -> None:
    with TemporaryDirectory() as directory:
        unknown_path = Path(directory) / "unknown.db"
        connection = sqlite3.connect(unknown_path)
        connection.execute("CREATE TABLE old_game_data(id INTEGER PRIMARY KEY)")
        connection.commit()
        connection.close()
        try:
            SqliteDatabase(unknown_path).initialize()
            raise AssertionError("未知旧数据库不能被静默盖章为新结构")
        except SchemaVersionError:
            pass

        mismatch_path = Path(directory) / "mismatch.db"
        database = SqliteDatabase(mismatch_path)
        database.initialize()
        connection = sqlite3.connect(mismatch_path)
        connection.execute(
            "UPDATE persistence_metadata SET value = ? WHERE key = ?",
            ("999", "schema_version"),
        )
        connection.commit()
        connection.close()
        try:
            database.initialize()
            raise AssertionError("结构版本不匹配时必须拒绝启动")
        except SchemaVersionError:
            pass

        shape_path = Path(directory) / "shape.db"
        shape_database = SqliteDatabase(shape_path)
        shape_database.initialize()
        connection = sqlite3.connect(shape_path)
        connection.execute("DROP INDEX outbox_event_pending_idx")
        connection.commit()
        connection.close()
        try:
            shape_database.initialize()
            raise AssertionError("核心索引损坏时不能只凭版本号启动")
        except SchemaVersionError:
            pass


def _assert_atomic_persisted_settlement(directory: Path) -> None:
    environment = _environment()
    engine = environment["engine"]
    initial = environment["snapshot"]
    keys = RewardSettlementStorageKeys(
        "inventory-account-a",
        "ledger-world-main",
        character_ids=("character-a",),
        weapon_ids=("weapon-a",),
    )
    database = SqliteDatabase(directory / "xiuxian4-test.db")
    database.initialize()
    database.initialize()
    service = PersistedRewardSettlementService(database, engine)
    service.initialize_snapshot(keys, initial, logical_time=TIME)
    assert PERSISTENCE_FOUNDATION_VERSION == "persistence.foundation.v1"
    assert PERSISTENCE_SCHEMA_VERSION == 1
    assert service.load_snapshot(keys, claim_scope_id="account-a") == initial

    settlement = _complete_settlement(initial)
    outcome = service.settle(settlement, keys, context=_context(seed=1_001))
    assert outcome.ok and outcome.value, outcome.failure
    persisted = service.load_snapshot(keys, claim_scope_id="account-a")
    assert persisted == outcome.value.snapshot
    assert persisted.inventory.stacks["ore-reward"].quantity == 5
    assert persisted.ledger.accounts["wallet-a"].balance == 250
    assert persisted.characters["character-a"].revision == 1
    assert persisted.weapons["weapon-a"].revision == 1
    assert persisted.claims.revision == 1

    pending = service.pending_events(limit=100)
    assert len(pending) == len(outcome.value.events)
    assert pending[-1].event.kind == "reward.settlement.completed"
    with database.unit_of_work(write=False) as uow:
        committed = uow.load_transaction(settlement.id)
        assert committed and committed.scope_id == "account-a"
        assert len(uow.pending_outbox(limit=100)) == len(pending)

    replay = service.settle(settlement, keys, context=_context(seed=1_002))
    assert replay.ok and replay.value and replay.value.replayed
    assert service.load_snapshot(keys, claim_scope_id="account-a") == persisted
    assert len(service.pending_events(limit=100)) == len(pending)

    changed = replace(
        settlement,
        rewards=(CurrencyReward("issuer-stone", "wallet-a", 251), *settlement.rewards[1:]),
    )
    try:
        service.settle(changed, keys, context=_context(seed=1_003))
        raise AssertionError("数据库事务 ID 相同但内容不同时必须拒绝")
    except TransactionMismatch:
        pass

    _assert_late_rule_failure_does_not_persist(service, keys, persisted)
    _assert_uncommitted_and_stale_cas_rollback(database, persisted)

    first = pending[0]
    service.mark_event_published(
        first.transaction_id,
        first.sequence,
        published_at=TIME + timedelta(minutes=1),
    )
    assert len(service.pending_events(limit=100)) == len(pending) - 1
    try:
        service.mark_event_published(
            first.transaction_id,
            first.sequence,
            published_at=TIME + timedelta(minutes=2),
        )
        raise AssertionError("同一 Outbox 事件不能重复标记发布")
    except ConcurrencyConflict:
        pass


def _assert_late_rule_failure_does_not_persist(service, keys, before) -> None:
    settlement = RewardSettlement(
        "persisted-reward-fails-late",
        "account-a",
        "account-a",
        "source.quest_reward",
        "quest-persist-invalid",
        (
            StackItemReward(
                "ore-persist-before-failure",
                "item.material.spirit_ore",
                "bag-a",
                3,
            ),
            CurrencyReward("issuer-stone", "wallet-a", 99),
            CharacterFeatureReward("character-a", "feature.unknown"),
        ),
        RewardExpectations(
            before.claims.revision,
            inventory_revision=before.inventory.revision,
            ledger_account_revisions={
                "issuer-stone": before.ledger.accounts["issuer-stone"].revision,
                "wallet-a": before.ledger.accounts["wallet-a"].revision,
            },
            character_revisions={
                "character-a": before.characters["character-a"].revision,
            },
        ),
    )
    pending_before = service.pending_events(limit=100)
    context = _context(seed=1_004)
    checkpoint = context.random.checkpoint()
    failed = service.settle(settlement, keys, context=context)
    assert failed.failure and failed.failure.code == "character.feature_unknown"
    assert service.load_snapshot(keys, claim_scope_id="account-a") == before
    assert service.pending_events(limit=100) == pending_before
    assert context.random.checkpoint() == checkpoint
    with service.database.unit_of_work(write=False) as uow:
        assert uow.load_transaction(settlement.id) is None


def _assert_uncommitted_and_stale_cas_rollback(database, persisted) -> None:
    repository = SnapshotRepository()
    candidate = replace(persisted.inventory, revision=persisted.inventory.revision + 1)
    with database.unit_of_work() as uow:
        repository.update(
            uow,
            INVENTORY_AGGREGATE,
            "inventory-account-a",
            persisted.inventory,
            candidate,
            TIME,
        )
        # 不调用 commit，退出上下文必须回滚。
    with database.unit_of_work(write=False) as uow:
        current = repository.require(
            uow,
            INVENTORY_AGGREGATE,
            "inventory-account-a",
            type(persisted.inventory),
        )
        assert current == persisted.inventory

    stale = replace(persisted.inventory, revision=persisted.inventory.revision + 1)
    try:
        with database.unit_of_work() as uow:
            uow.compare_and_swap_snapshot(
                INVENTORY_AGGREGATE,
                "inventory-account-a",
                999,
                1_000,
                repository.codec.dumps(stale),
                TIME.isoformat(),
            )
        raise AssertionError("旧 revision 条件更新必须失败")
    except ConcurrencyConflict:
        pass

    with database.unit_of_work() as uow:
        row = uow.require_snapshot(INVENTORY_AGGREGATE, "inventory-account-a")
        uow.connection.execute(
            "UPDATE aggregate_snapshot SET payload = ? WHERE aggregate_kind = ? AND aggregate_id = ?",
            ('{"format":"structured-json.v1","value":{"$type":"unknown.type"}}', INVENTORY_AGGREGATE, "inventory-account-a"),
        )
        try:
            repository.require(
                uow,
                INVENTORY_AGGREGATE,
                "inventory-account-a",
                type(persisted.inventory),
            )
            raise AssertionError("未知持久化类型不能被动态导入")
        except CorruptPersistenceData:
            pass
        # 未提交，损坏注入也必须回滚；row 只用于确认原记录存在。
        assert row.revision == persisted.inventory.revision


if __name__ == "__main__":
    main()
