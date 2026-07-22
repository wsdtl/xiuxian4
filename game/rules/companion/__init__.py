"""伙伴具体游戏纯规则。"""

from .engine import CompanionEngine, CompanionRuleError
from .growth import CompanionExperienceResult, CompanionGrowthEngine
from .lineup import (
    PlayerBattleLineup,
    PlayerBattleLineupProjector,
    automatic_player_ai_rules,
)
from .models import *
from .models import __all__ as _models_all
from .projection import CompanionCombatProjection, CompanionCombatProjector


__all__ = [
    "CompanionCombatProjection",
    "CompanionCombatProjector",
    "CompanionEngine",
    "CompanionExperienceResult",
    "CompanionGrowthEngine",
    "CompanionRuleError",
    "PlayerBattleLineup",
    "PlayerBattleLineupProjector",
    "automatic_player_ai_rules",
    *_models_all,
]
