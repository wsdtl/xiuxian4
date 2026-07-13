"""协议和具体玩法无关的版本化掉落与保底底座。"""

LOOT_FOUNDATION_VERSION = "loot.foundation.v1"

from .engine import LootEngine
from .models import (
    LOOT_CHANCE_SCALE,
    LOOT_MODIFIER_SCALE,
    LootAward,
    LootCatalog,
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

__all__ = [
    "LOOT_CHANCE_SCALE",
    "LOOT_FOUNDATION_VERSION",
    "LOOT_MODIFIER_SCALE",
    "LootAward",
    "LootCatalog",
    "LootDecision",
    "LootEngine",
    "LootEntry",
    "LootExecution",
    "LootGroup",
    "LootGroupMode",
    "LootPityDefinition",
    "LootRollCommand",
    "LootRollReceipt",
    "LootState",
    "LootTableDefinition",
]
