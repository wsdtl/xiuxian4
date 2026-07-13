"""Gameplay 领域快照的白名单编解码与类型化聚合仓储。"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, TypeVar

from ..gameplay.actions import (
    ActionRecord,
    ActionResult,
    ActionSlotKind,
    ActionSnapshot,
    ActionState,
    ActionStatus,
)
from ..gameplay.character import CharacterState, CharacterStatus, ProgressionState
from ..gameplay.economy import (
    AppliedLedgerTransaction,
    FundHold,
    JournalEntry,
    LedgerAccount,
    LedgerAccountKind,
    LedgerPosting,
    LedgerState,
)
from ..gameplay.events import RuleEvent
from ..gameplay.inventory import (
    AssetReservation,
    InventoryState,
    ItemAssetKind,
    ItemContainer,
    ItemInstance,
    ItemStack,
    ProvenanceLot,
    ReservationMode,
    SourceReceipt,
)
from ..gameplay.inscription import (
    AssetInscriptionTarget,
    InscriptionData,
    InscriptionMediumData,
    InscriptionPreference,
    InscriptionReceipt,
    WeaponAbilityInscriptionTarget,
)
from ..gameplay.phases import ExecutionPhase
from ..gameplay.rewards import (
    RewardClaimRecord,
    RewardClaimState,
    RewardDisposition,
    RewardLine,
    RewardReceipt,
)
from ..gameplay.tags import Tag, TagSet
from ..gameplay.weapon import WeaponState

from .codec import StructuredJsonCodec
from .errors import CorruptPersistenceData
from .sqlite import SNAPSHOT_CODEC_VERSION, SqliteUnitOfWork


INVENTORY_AGGREGATE = "snapshot.inventory"
LEDGER_AGGREGATE = "snapshot.ledger"
CHARACTER_AGGREGATE = "snapshot.character"
WEAPON_AGGREGATE = "snapshot.weapon"
REWARD_CLAIM_AGGREGATE = "snapshot.reward_claim"
INSCRIPTION_PREFERENCE_AGGREGATE = "snapshot.inscription_preference"
ACTION_AGGREGATE = "snapshot.action"

StateT = TypeVar("StateT")


def gameplay_snapshot_codec(
    extra_registrations: Iterable[tuple[str, type[object]]] = (),
) -> StructuredJsonCodec:
    """创建核心快照 codec，并允许组合根在冻结前追加业务聚合类型。"""

    codec = StructuredJsonCodec()
    registrations = (
        ("gameplay.tag", Tag),
        ("gameplay.tag_set", TagSet),
        ("action.slot_kind", ActionSlotKind),
        ("action.status", ActionStatus),
        ("action.snapshot", ActionSnapshot),
        ("action.result", ActionResult),
        ("action.record", ActionRecord),
        ("action.state", ActionState),
        ("inventory.asset_kind", ItemAssetKind),
        ("inventory.reservation_mode", ReservationMode),
        ("inventory.source_receipt", SourceReceipt),
        ("inventory.provenance_lot", ProvenanceLot),
        ("inventory.item_stack", ItemStack),
        ("inventory.item_instance", ItemInstance),
        ("inventory.item_container", ItemContainer),
        ("inventory.asset_reservation", AssetReservation),
        ("inventory.state", InventoryState),
        ("inscription.asset_target", AssetInscriptionTarget),
        ("inscription.weapon_ability_target", WeaponAbilityInscriptionTarget),
        ("inscription.data", InscriptionData),
        ("inscription.medium_data", InscriptionMediumData),
        ("inscription.preference", InscriptionPreference),
        ("inscription.receipt", InscriptionReceipt),
        ("economy.account_kind", LedgerAccountKind),
        ("economy.account", LedgerAccount),
        ("economy.fund_hold", FundHold),
        ("economy.posting", LedgerPosting),
        ("economy.journal_entry", JournalEntry),
        ("economy.applied_transaction", AppliedLedgerTransaction),
        ("economy.state", LedgerState),
        ("character.status", CharacterStatus),
        ("character.progression_state", ProgressionState),
        ("character.state", CharacterState),
        ("weapon.state", WeaponState),
        ("reward.disposition", RewardDisposition),
        ("reward.line", RewardLine),
        ("reward.receipt", RewardReceipt),
        ("reward.claim_record", RewardClaimRecord),
        ("reward.claim_state", RewardClaimState),
        ("rule.execution_phase", ExecutionPhase),
        ("rule.event", RuleEvent),
    )
    for type_id, value_type in registrations:
        codec.register(type_id, value_type)
    for type_id, value_type in extra_registrations:
        codec.register(type_id, value_type)
    codec.freeze()
    return codec


class SnapshotRepository:
    """只负责类型化快照读写；事务范围由外部工作单元控制。"""

    def __init__(self, codec: StructuredJsonCodec | None = None) -> None:
        self.codec = codec or gameplay_snapshot_codec()

    def load(
        self,
        uow: SqliteUnitOfWork,
        aggregate_kind: str,
        aggregate_id: str,
        expected_type: type[StateT],
    ) -> StateT | None:
        row = uow.load_snapshot(aggregate_kind, aggregate_id)
        if row is None:
            return None
        if row.codec_version != SNAPSHOT_CODEC_VERSION:
            raise CorruptPersistenceData(
                f"快照 codec 版本不匹配：需要 {SNAPSHOT_CODEC_VERSION}，当前 {row.codec_version}"
            )
        value = self.codec.loads(row.payload, expected_type)
        revision = getattr(value, "revision", None)
        if revision != row.revision:
            raise CorruptPersistenceData(
                f"快照行 revision 与负载不一致：{aggregate_kind}/{aggregate_id}"
            )
        return value

    def require(
        self,
        uow: SqliteUnitOfWork,
        aggregate_kind: str,
        aggregate_id: str,
        expected_type: type[StateT],
    ) -> StateT:
        value = self.load(uow, aggregate_kind, aggregate_id, expected_type)
        if value is None:
            from .errors import AggregateNotFound

            raise AggregateNotFound(f"缺少聚合快照：{aggregate_kind}/{aggregate_id}")
        return value

    def insert(
        self,
        uow: SqliteUnitOfWork,
        aggregate_kind: str,
        aggregate_id: str,
        value: object,
        logical_time: datetime,
    ) -> None:
        _require_aware(logical_time)
        revision = _revision_of(value)
        uow.insert_snapshot(
            aggregate_kind,
            aggregate_id,
            revision,
            self.codec.dumps(value),
            logical_time.isoformat(),
        )

    def update(
        self,
        uow: SqliteUnitOfWork,
        aggregate_kind: str,
        aggregate_id: str,
        previous: object,
        current: object,
        logical_time: datetime,
    ) -> None:
        _require_aware(logical_time)
        previous_revision = _revision_of(previous)
        current_revision = _revision_of(current)
        uow.compare_and_swap_snapshot(
            aggregate_kind,
            aggregate_id,
            previous_revision,
            current_revision,
            self.codec.dumps(current),
            logical_time.isoformat(),
        )


def _revision_of(value: object) -> int:
    revision = getattr(value, "revision", None)
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        raise TypeError(f"持久化聚合缺少有效 revision：{type(value).__name__}")
    return revision


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("持久化逻辑时间必须包含时区")


__all__ = [
    "ACTION_AGGREGATE",
    "CHARACTER_AGGREGATE",
    "INVENTORY_AGGREGATE",
    "INSCRIPTION_PREFERENCE_AGGREGATE",
    "LEDGER_AGGREGATE",
    "REWARD_CLAIM_AGGREGATE",
    "SnapshotRepository",
    "WEAPON_AGGREGATE",
    "gameplay_snapshot_codec",
]
