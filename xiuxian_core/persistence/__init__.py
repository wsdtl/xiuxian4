"""协议和具体玩法无关的持久化联合事务基础设施。"""

PERSISTENCE_FOUNDATION_VERSION = "persistence.foundation.v1"

from .codec import StructuredJsonCodec
from .content import ContentActivation, ContentActivationStore
from .cycles import (
    CycleCursor,
    CycleWorkItem,
    CycleWorkStatus,
    PersistentCycleService,
    cycle_transaction_id,
)
from .inscriptions import PersistedInscriptionService
from .errors import (
    AggregateNotFound,
    ConcurrencyConflict,
    ContentActivationMismatch,
    CorruptPersistenceData,
    PersistenceError,
    SchemaVersionError,
    TransactionMismatch,
)
from .rewards import (
    PendingRuleEvent,
    PersistedRewardSettlementService,
    RewardSettlementStorageKeys,
)
from .snapshots import (
    ACTION_AGGREGATE,
    CHARACTER_AGGREGATE,
    INVENTORY_AGGREGATE,
    INSCRIPTION_PREFERENCE_AGGREGATE,
    LEDGER_AGGREGATE,
    REWARD_CLAIM_AGGREGATE,
    WEAPON_AGGREGATE,
    SnapshotRepository,
    gameplay_snapshot_codec,
)
from .sqlite import (
    AggregateSnapshotRow,
    CommittedTransactionRow,
    ContentActivationRow,
    CycleCursorRow,
    CycleWorkItemRow,
    OutboxEventRow,
    PERSISTENCE_SCHEMA_VERSION,
    SNAPSHOT_CODEC_VERSION,
    SqliteDatabase,
    SqliteUnitOfWork,
)

__all__ = [
    "ACTION_AGGREGATE",
    "AggregateNotFound",
    "AggregateSnapshotRow",
    "CHARACTER_AGGREGATE",
    "CommittedTransactionRow",
    "ConcurrencyConflict",
    "ContentActivation",
    "ContentActivationMismatch",
    "ContentActivationRow",
    "ContentActivationStore",
    "CycleCursor",
    "CycleCursorRow",
    "CycleWorkItem",
    "CycleWorkItemRow",
    "CycleWorkStatus",
    "CorruptPersistenceData",
    "INVENTORY_AGGREGATE",
    "INSCRIPTION_PREFERENCE_AGGREGATE",
    "LEDGER_AGGREGATE",
    "OutboxEventRow",
    "PERSISTENCE_FOUNDATION_VERSION",
    "PERSISTENCE_SCHEMA_VERSION",
    "PendingRuleEvent",
    "PersistentCycleService",
    "PersistedRewardSettlementService",
    "PersistedInscriptionService",
    "PersistenceError",
    "REWARD_CLAIM_AGGREGATE",
    "RewardSettlementStorageKeys",
    "SNAPSHOT_CODEC_VERSION",
    "SchemaVersionError",
    "SnapshotRepository",
    "SqliteDatabase",
    "SqliteUnitOfWork",
    "StructuredJsonCodec",
    "TransactionMismatch",
    "WEAPON_AGGREGATE",
    "gameplay_snapshot_codec",
    "cycle_transaction_id",
]
