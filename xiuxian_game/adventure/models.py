"""探险与恢复服务返回的协议中立只读视图。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ActivityView:
    action_id: str
    definition_id: str
    phase: str
    started_at: datetime
    completes_at: datetime
    remaining_seconds: int


@dataclass(frozen=True)
class ExplorationStartView:
    activity: ActivityView
    spirit: int
    maximum_spirit: int
    replayed: bool = False


@dataclass(frozen=True)
class ExplorationClaimView:
    settlement_id: str
    damage: int
    stone_reward: int
    herb_reward: int
    experience_reward: int
    replayed: bool = False


@dataclass(frozen=True)
class RecoveryStartView:
    activity: ActivityView
    missing_health: int
    missing_spirit: int
    replayed: bool = False


@dataclass(frozen=True)
class RecoveryClaimView:
    restored_health: int
    restored_spirit: int
    health: int
    maximum_health: int
    spirit: int
    maximum_spirit: int


__all__ = [
    "ActivityView",
    "ExplorationClaimView",
    "ExplorationStartView",
    "RecoveryClaimView",
    "RecoveryStartView",
]
