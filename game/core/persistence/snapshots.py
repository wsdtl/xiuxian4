"""Gameplay 领域快照的白名单编解码与类型化聚合仓储。"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, TypeVar

from ..account import (
    AccountDirectoryState,
    AccountEvent,
    AccountMutation,
    AccountResolution,
    AccountState,
    AccountStatus,
    AccountStatusTransaction,
    EvidenceRecord,
    ExternalIdentity,
    IdentityBinding,
    IdentityConflict,
    IdentityEvidence,
    UnbindIdentityTransaction,
)
from ..gameplay.activities import (
    ActivityCommand,
    ActivityExecution,
    ActivityInstance,
    ActivityParticipant,
    ActivityRankEntry,
    ActivityState,
    ActivityStatus,
    ActivityTieBreaker,
    CancelActivity,
    CloseActivity,
    CreateActivity,
    FinalizeActivity,
    JoinActivity,
    OpenActivity,
    RecordActivityContribution,
)
from ..gameplay.actions import (
    ActionExecution,
    ActionRecord,
    ActionResult,
    ActionSlotKind,
    ActionSnapshot,
    ActionState,
    ActionStatus,
    ActionTransaction,
    CancelAction,
    ClaimAction,
    CompleteAction,
    InterruptAction,
    StartAction,
)
from ..gameplay.character import (
    CharacterRosterState,
    CharacterState,
    CharacterStatus,
    ProgressionState,
)
from ..gameplay.economy import (
    AppliedLedgerTransaction,
    FundHold,
    JournalEntry,
    LedgerAccount,
    LedgerAccountKind,
    LedgerPosting,
    LedgerState,
)
from ..gameplay.equipment import EquipmentState
from ..gameplay.events import RuleEvent
from ..gameplay.exchange import (
    CancelExchange,
    CommitExchange,
    ExchangeAssetOffer,
    ExchangeCommand,
    ExchangeContract,
    ExchangeExecution,
    ExchangeQuote,
    ExchangeQuoteLine,
    ExchangeState,
    ExchangeStatus,
    ExpireExchange,
    OpenExchange,
    SettleExchange,
)
from ..gameplay.inventory import (
    AssetReservation,
    InventoryState,
    ItemAssetKind,
    ItemContainer,
    ItemInstance,
    ItemStack,
    ItemUseReceipt,
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
from ..gameplay.loadout import (
    ActivateLoadoutPreset,
    DeleteLoadoutPreset,
    EquipAsset,
    LoadoutExecution,
    LoadoutSlotKind,
    LoadoutPreset,
    LoadoutState,
    LoadoutTransaction,
    SaveLoadoutPreset,
    UnequipSlot,
)
from ..gameplay.itemization import (
    GenerationDecision,
    GenerationReceipt,
    ItemRollState,
    ItemizationKind,
    RolledProperty,
)
from ..gameplay.loot import (
    LootAward,
    LootDecision,
    LootEntry,
    LootExecution,
    LootGroup,
    LootGroupMode,
    LootPityDefinition,
    LootRollCommand,
    LootRollReceipt,
    LootState,
    LootTableDefinition,
)
from ..gameplay.phases import ExecutionPhase
from ..gameplay.party import (
    AddPartyMember,
    CreateParty,
    DisbandParty,
    LeaveParty,
    Party,
    PartyAdmissionCommand,
    PartyAdmissionExecution,
    PartyCommand,
    PartyExecution,
    PartyMember,
    PartyState,
    PartyStatus,
    RemovePartyMember,
    SetPartyMemberReady,
    SetPartyMemberSlot,
    TransferPartyLeadership,
)
from ..gameplay.projections import (
    FactRecord,
    NotificationAction,
    NotificationEntry,
    NotificationStatus,
    ProjectionValue,
    RankingCandidate,
    RankingDirection,
    RankingEntry,
    RankingSnapshot,
)
from ..gameplay.rewards import (
    RewardClaimRecord,
    RewardClaimState,
    RewardDisposition,
    RewardLine,
    RewardReceipt,
)
from ..gameplay.social import (
    AddOrganizationContribution,
    AdjustSocialRelation,
    ChangeOrganizationRole,
    CreateOrganization,
    CreateSocialRequest,
    DissolveOrganization,
    JoinOrganization,
    LeaveOrganization,
    Organization,
    OrganizationMember,
    OrganizationStatus,
    RelationOverflowPolicy,
    ResolveSocialRequest,
    SocialCommand,
    SocialExecution,
    SocialRelation,
    SocialRequest,
    SocialRequestStatus,
    SocialState,
    TransferOrganizationLeadership,
)
from ..gameplay.tags import Tag, TagSet
from ..gameplay.weapon import WeaponState
from ..gameplay.valuation import ValueVector
from ..gameplay.world import (
    AddPresence,
    AdjustWorldMeter,
    MeterOverflowPolicy,
    MovePresence,
    ReleaseWorldReservation,
    RemovePresence,
    ReserveWorldPosition,
    WorldExecution,
    WorldPosition,
    WorldPresence,
    WorldReservation,
    WorldScopeKind,
    WorldScopeRef,
    WorldState,
    WorldTopologyKind,
    WorldTransaction,
)

from .codec import StructuredJsonCodec
from .errors import CorruptPersistenceData
from .sqlite import SNAPSHOT_CODEC_VERSION, SqliteUnitOfWork


INVENTORY_AGGREGATE = "snapshot.inventory"
LEDGER_AGGREGATE = "snapshot.ledger"
CHARACTER_AGGREGATE = "snapshot.character"
CHARACTER_ROSTER_AGGREGATE = "snapshot.character_roster"
WEAPON_AGGREGATE = "snapshot.weapon"
REWARD_CLAIM_AGGREGATE = "snapshot.reward_claim"
INSCRIPTION_PREFERENCE_AGGREGATE = "snapshot.inscription_preference"
ACTION_AGGREGATE = "snapshot.action"
LOADOUT_AGGREGATE = "snapshot.loadout"
LOOT_AGGREGATE = "snapshot.loot"
WORLD_AGGREGATE = "snapshot.world"
EXCHANGE_AGGREGATE = "snapshot.exchange"
ACTIVITY_AGGREGATE = "snapshot.activity"
SOCIAL_AGGREGATE = "snapshot.social"
PARTY_AGGREGATE = "snapshot.party"

StateT = TypeVar("StateT")


def gameplay_snapshot_codec(
    extra_registrations: Iterable[tuple[str, type[object]]] = (),
) -> StructuredJsonCodec:
    """创建核心快照 codec，并允许组合根在冻结前追加业务聚合类型。"""

    codec = StructuredJsonCodec()
    registrations = (
        ("account.status", AccountStatus),
        ("account.external_identity", ExternalIdentity),
        ("account.identity_evidence", IdentityEvidence),
        ("account.state", AccountState),
        ("account.identity_binding", IdentityBinding),
        ("account.identity_conflict", IdentityConflict),
        ("account.evidence_record", EvidenceRecord),
        ("account.directory_state", AccountDirectoryState),
        ("account.event", AccountEvent),
        ("account.resolution", AccountResolution),
        ("account.status_transaction", AccountStatusTransaction),
        ("account.unbind_transaction", UnbindIdentityTransaction),
        ("account.mutation", AccountMutation),
        ("activity.status", ActivityStatus),
        ("activity.tie_breaker", ActivityTieBreaker),
        ("activity.participant", ActivityParticipant),
        ("activity.rank_entry", ActivityRankEntry),
        ("activity.instance", ActivityInstance),
        ("activity.state", ActivityState),
        ("activity.create", CreateActivity),
        ("activity.open", OpenActivity),
        ("activity.join", JoinActivity),
        ("activity.contribute", RecordActivityContribution),
        ("activity.close", CloseActivity),
        ("activity.finalize", FinalizeActivity),
        ("activity.cancel", CancelActivity),
        ("activity.command", ActivityCommand),
        ("activity.execution", ActivityExecution),
        ("gameplay.tag", Tag),
        ("gameplay.tag_set", TagSet),
        ("action.slot_kind", ActionSlotKind),
        ("action.status", ActionStatus),
        ("action.start", StartAction),
        ("action.complete", CompleteAction),
        ("action.claim", ClaimAction),
        ("action.cancel", CancelAction),
        ("action.interrupt", InterruptAction),
        ("action.transaction", ActionTransaction),
        ("action.snapshot", ActionSnapshot),
        ("action.result", ActionResult),
        ("action.record", ActionRecord),
        ("action.state", ActionState),
        ("action.execution", ActionExecution),
        ("inventory.asset_kind", ItemAssetKind),
        ("inventory.reservation_mode", ReservationMode),
        ("inventory.source_receipt", SourceReceipt),
        ("inventory.provenance_lot", ProvenanceLot),
        ("inventory.item_stack", ItemStack),
        ("inventory.item_instance", ItemInstance),
        ("inventory.item_container", ItemContainer),
        ("inventory.asset_reservation", AssetReservation),
        ("inventory.state", InventoryState),
        ("inventory.item_use_receipt", ItemUseReceipt),
        ("inscription.asset_target", AssetInscriptionTarget),
        ("inscription.weapon_ability_target", WeaponAbilityInscriptionTarget),
        ("inscription.data", InscriptionData),
        ("inscription.medium_data", InscriptionMediumData),
        ("inscription.preference", InscriptionPreference),
        ("inscription.receipt", InscriptionReceipt),
        ("loadout.slot_kind", LoadoutSlotKind),
        ("loadout.preset", LoadoutPreset),
        ("loadout.equip", EquipAsset),
        ("loadout.unequip", UnequipSlot),
        ("loadout.save_preset", SaveLoadoutPreset),
        ("loadout.delete_preset", DeleteLoadoutPreset),
        ("loadout.activate_preset", ActivateLoadoutPreset),
        ("loadout.transaction", LoadoutTransaction),
        ("loadout.state", LoadoutState),
        ("loadout.execution", LoadoutExecution),
        ("loot.group_mode", LootGroupMode),
        ("loot.entry", LootEntry),
        ("loot.group", LootGroup),
        ("loot.pity_definition", LootPityDefinition),
        ("loot.table_definition", LootTableDefinition),
        ("loot.state", LootState),
        ("loot.command", LootRollCommand),
        ("loot.award", LootAward),
        ("loot.decision", LootDecision),
        ("loot.receipt", LootRollReceipt),
        ("loot.execution", LootExecution),
        ("world.topology_kind", WorldTopologyKind),
        ("world.scope_kind", WorldScopeKind),
        ("world.meter_overflow", MeterOverflowPolicy),
        ("world.position", WorldPosition),
        ("world.scope_ref", WorldScopeRef),
        ("world.presence", WorldPresence),
        ("world.reservation", WorldReservation),
        ("world.state", WorldState),
        ("world.add_presence", AddPresence),
        ("world.move_presence", MovePresence),
        ("world.remove_presence", RemovePresence),
        ("world.reserve_position", ReserveWorldPosition),
        ("world.release_reservation", ReleaseWorldReservation),
        ("world.adjust_meter", AdjustWorldMeter),
        ("world.transaction", WorldTransaction),
        ("world.execution", WorldExecution),
        ("economy.account_kind", LedgerAccountKind),
        ("economy.account", LedgerAccount),
        ("economy.fund_hold", FundHold),
        ("economy.posting", LedgerPosting),
        ("economy.journal_entry", JournalEntry),
        ("economy.applied_transaction", AppliedLedgerTransaction),
        ("economy.state", LedgerState),
        ("character.status", CharacterStatus),
        ("character.progression_state", ProgressionState),
        ("character.roster_state", CharacterRosterState),
        ("character.state", CharacterState),
        ("weapon.state", WeaponState),
        ("equipment.state", EquipmentState),
        ("valuation.value_vector", ValueVector),
        ("itemization.kind", ItemizationKind),
        ("itemization.rolled_property", RolledProperty),
        ("itemization.generation_decision", GenerationDecision),
        ("itemization.generation_receipt", GenerationReceipt),
        ("itemization.roll_state", ItemRollState),
        ("reward.disposition", RewardDisposition),
        ("reward.line", RewardLine),
        ("reward.receipt", RewardReceipt),
        ("reward.claim_record", RewardClaimRecord),
        ("reward.claim_state", RewardClaimState),
        ("social.organization_status", OrganizationStatus),
        ("social.request_status", SocialRequestStatus),
        ("social.relation_overflow", RelationOverflowPolicy),
        ("social.organization_member", OrganizationMember),
        ("social.organization", Organization),
        ("social.request", SocialRequest),
        ("social.relation", SocialRelation),
        ("social.state", SocialState),
        ("social.create_organization", CreateOrganization),
        ("social.join_organization", JoinOrganization),
        ("social.leave_organization", LeaveOrganization),
        ("social.change_role", ChangeOrganizationRole),
        ("social.transfer_leadership", TransferOrganizationLeadership),
        ("social.add_contribution", AddOrganizationContribution),
        ("social.dissolve_organization", DissolveOrganization),
        ("social.create_request", CreateSocialRequest),
        ("social.resolve_request", ResolveSocialRequest),
        ("social.adjust_relation", AdjustSocialRelation),
        ("social.command", SocialCommand),
        ("social.execution", SocialExecution),
        ("party.status", PartyStatus),
        ("party.member", PartyMember),
        ("party.value", Party),
        ("party.state", PartyState),
        ("party.create", CreateParty),
        ("party.add_member", AddPartyMember),
        ("party.remove_member", RemovePartyMember),
        ("party.leave", LeaveParty),
        ("party.transfer_leadership", TransferPartyLeadership),
        ("party.set_ready", SetPartyMemberReady),
        ("party.set_slot", SetPartyMemberSlot),
        ("party.disband", DisbandParty),
        ("party.command", PartyCommand),
        ("party.execution", PartyExecution),
        ("party.admission_command", PartyAdmissionCommand),
        ("party.admission_execution", PartyAdmissionExecution),
        ("rule.execution_phase", ExecutionPhase),
        ("rule.event", RuleEvent),
        ("projection.fact_record", FactRecord),
        ("projection.value", ProjectionValue),
        ("notification.status", NotificationStatus),
        ("notification.action", NotificationAction),
        ("notification.entry", NotificationEntry),
        ("ranking.direction", RankingDirection),
        ("ranking.candidate", RankingCandidate),
        ("ranking.entry", RankingEntry),
        ("ranking.snapshot", RankingSnapshot),
        ("exchange.status", ExchangeStatus),
        ("exchange.quote_line", ExchangeQuoteLine),
        ("exchange.quote", ExchangeQuote),
        ("exchange.asset_offer", ExchangeAssetOffer),
        ("exchange.contract", ExchangeContract),
        ("exchange.state", ExchangeState),
        ("exchange.open", OpenExchange),
        ("exchange.commit", CommitExchange),
        ("exchange.settle", SettleExchange),
        ("exchange.cancel", CancelExchange),
        ("exchange.expire", ExpireExchange),
        ("exchange.command", ExchangeCommand),
        ("exchange.execution", ExchangeExecution),
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
    "ACTIVITY_AGGREGATE",
    "ACTION_AGGREGATE",
    "CHARACTER_AGGREGATE",
    "CHARACTER_ROSTER_AGGREGATE",
    "EXCHANGE_AGGREGATE",
    "INVENTORY_AGGREGATE",
    "INSCRIPTION_PREFERENCE_AGGREGATE",
    "LEDGER_AGGREGATE",
    "LOADOUT_AGGREGATE",
    "LOOT_AGGREGATE",
    "REWARD_CLAIM_AGGREGATE",
    "SOCIAL_AGGREGATE",
    "PARTY_AGGREGATE",
    "SnapshotRepository",
    "WEAPON_AGGREGATE",
    "WORLD_AGGREGATE",
    "gameplay_snapshot_codec",
]
