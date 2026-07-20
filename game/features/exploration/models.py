"""探险玩法对命令层和装配层公开的稳定模型。"""

from __future__ import annotations

from dataclasses import dataclass

from game.rules.exploration import ExplorationBatchResult, ExplorationState


MAX_CATCH_UP_BATCHES = 144
MAX_DISCOVERABLE_EXPLORATIONS = 1_000


def exploration_battle_report_id(session_id: str) -> str:
    return f"battle-report:{session_id}"


@dataclass(frozen=True)
class ExplorationOperationResult:
    status: str
    state: ExplorationState | None = None
    batches: tuple[ExplorationBatchResult, ...] = ()


@dataclass(frozen=True)
class ExplorationMovementResult:
    status: str
    location_id: str | None = None


@dataclass(frozen=True)
class ExplorationStorageKinds:
    """由组合根注入的持久化聚合类型，不让玩法层导入 SQLite 包。"""

    action: str
    character: str
    inventory: str
    loadout: str
    companion_roster: str
    loot: str
    reward_claim: str
    weapon: str
    world: str


__all__ = [
    "ExplorationMovementResult",
    "ExplorationOperationResult",
    "ExplorationStorageKinds",
    "MAX_CATCH_UP_BATCHES",
    "MAX_DISCOVERABLE_EXPLORATIONS",
    "exploration_battle_report_id",
]
