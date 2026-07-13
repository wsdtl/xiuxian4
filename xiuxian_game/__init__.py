"""xiuxian4 的具体修仙世界内容与业务闭环。"""

XIUXIAN_GAME_VERSION = "xiuxian-game.v1"

from .models import (
    ClaimResultView,
    EntryResult,
    EquipResultView,
    PendingTrial,
    PlayerProfileState,
    PlayerStatusView,
    TrialResultView,
)
from .service import GameApplication, GameViolation, game_snapshot_repository
from .world import (
    WORLD_PACKAGE_ID,
    WORLD_SKIN_ID,
    assemble_first_world,
    first_world_packages,
)

__all__ = [
    "XIUXIAN_GAME_VERSION",
    "ClaimResultView",
    "EntryResult",
    "EquipResultView",
    "GameApplication",
    "GameViolation",
    "PendingTrial",
    "PlayerProfileState",
    "PlayerStatusView",
    "TrialResultView",
    "WORLD_PACKAGE_ID",
    "WORLD_SKIN_ID",
    "assemble_first_world",
    "first_world_packages",
    "game_snapshot_repository",
]
