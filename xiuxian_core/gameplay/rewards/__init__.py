"""协议、存储和具体玩法无关的统一奖励结算底座。"""

REWARD_FOUNDATION_VERSION = "reward.foundation.v1"

from .engine import RewardSettlementEngine, reward_fingerprint
from .models import (
    CharacterExperienceReward,
    CharacterFeatureReward,
    CharacterProgressionReward,
    CurrencyReward,
    DuplicateUnlockPolicy,
    InstanceItemReward,
    RewardClaimRecord,
    RewardClaimState,
    RewardDisposition,
    RewardExpectations,
    RewardLine,
    RewardReceipt,
    RewardSettlement,
    RewardSettlementExecution,
    RewardSettlementPreview,
    RewardSettlementSnapshot,
    RewardSpec,
    StackItemReward,
    WeaponExperienceReward,
)
from .planning import (
    RewardPlan,
    RewardPlanBuilder,
    RewardPlanner,
    RewardPlannerRegistry,
)

__all__ = [
    "CharacterExperienceReward",
    "CharacterFeatureReward",
    "CharacterProgressionReward",
    "CurrencyReward",
    "DuplicateUnlockPolicy",
    "InstanceItemReward",
    "REWARD_FOUNDATION_VERSION",
    "RewardClaimRecord",
    "RewardClaimState",
    "RewardDisposition",
    "RewardExpectations",
    "RewardLine",
    "RewardPlan",
    "RewardPlanBuilder",
    "RewardPlanner",
    "RewardPlannerRegistry",
    "RewardReceipt",
    "RewardSettlement",
    "RewardSettlementEngine",
    "RewardSettlementExecution",
    "RewardSettlementPreview",
    "RewardSettlementSnapshot",
    "RewardSpec",
    "StackItemReward",
    "WeaponExperienceReward",
    "reward_fingerprint",
]
