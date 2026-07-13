"""协议和具体玩法无关的持久化联合事务基础设施。"""

PERSISTENCE_FOUNDATION_VERSION = "persistence.foundation.v4"

from .codec import StructuredJsonCodec
from .actions import (
    PersistedActionClaimExecution,
    PersistedActionExecution,
    PersistedActionService,
)
from .activities import PersistedActivityExecution, PersistedActivityService
from .accounts import PersistedAccountService
from .content import ContentActivation, ContentActivationStore
from .cycles import (
    CycleCursor,
    CycleWorkItem,
    CycleWorkStatus,
    PersistentCycleService,
    cycle_transaction_id,
)
from .inscriptions import PersistedInscriptionService
from .item_use import PersistedItemUseService
from .loadouts import PersistedLoadoutExecution, PersistedLoadoutService
from .loot import PersistedLootExecution, PersistedLootService
from .world import PersistedWorldExecution, PersistedWorldService
from .social import PersistedSocialExecution, PersistedSocialService
from .projections import (
    FactJournalService,
    NotificationInboxService,
    ProjectionStore,
    RankingSnapshotStore,
)
from .exchange import PersistedExchangeExecution, PersistedExchangeService
from .grants import PersistedGrantService
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
    ACTIVITY_AGGREGATE,
    CHARACTER_AGGREGATE,
    EXCHANGE_AGGREGATE,
    INVENTORY_AGGREGATE,
    INSCRIPTION_PREFERENCE_AGGREGATE,
    LEDGER_AGGREGATE,
    LOADOUT_AGGREGATE,
    LOOT_AGGREGATE,
    REWARD_CLAIM_AGGREGATE,
    SOCIAL_AGGREGATE,
    WEAPON_AGGREGATE,
    WORLD_AGGREGATE,
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
    "ACTIVITY_AGGREGATE",
    "AggregateNotFound",
    "AggregateSnapshotRow",
    "CHARACTER_AGGREGATE",
    "EXCHANGE_AGGREGATE",
    "FactJournalService",
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
    "LOADOUT_AGGREGATE",
    "LOOT_AGGREGATE",
    "NotificationInboxService",
    "OutboxEventRow",
    "PERSISTENCE_FOUNDATION_VERSION",
    "PERSISTENCE_SCHEMA_VERSION",
    "ProjectionStore",
    "PendingRuleEvent",
    "PersistedAccountService",
    "PersistedActionClaimExecution",
    "PersistedActionExecution",
    "PersistedActionService",
    "PersistedActivityExecution",
    "PersistedActivityService",
    "PersistedExchangeExecution",
    "PersistedExchangeService",
    "PersistentCycleService",
    "PersistedRewardSettlementService",
    "PersistedGrantService",
    "PersistedInscriptionService",
    "PersistedItemUseService",
    "PersistedLoadoutExecution",
    "PersistedLoadoutService",
    "PersistedLootExecution",
    "PersistedLootService",
    "PersistedSocialExecution",
    "PersistedSocialService",
    "PersistedWorldExecution",
    "PersistedWorldService",
    "PersistenceError",
    "REWARD_CLAIM_AGGREGATE",
    "SOCIAL_AGGREGATE",
    "RewardSettlementStorageKeys",
    "RankingSnapshotStore",
    "SNAPSHOT_CODEC_VERSION",
    "SchemaVersionError",
    "SnapshotRepository",
    "SqliteDatabase",
    "SqliteUnitOfWork",
    "StructuredJsonCodec",
    "TransactionMismatch",
    "WEAPON_AGGREGATE",
    "WORLD_AGGREGATE",
    "gameplay_snapshot_codec",
    "cycle_transaction_id",
]
