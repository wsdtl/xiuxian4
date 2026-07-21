"""探险结算向外公开的稳定事实。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from game.core.gameplay import StableId, stable_id


EXPLORATION_VICTORY_FACT_KIND = "exploration.victory.recorded"


@dataclass(frozen=True)
class ExplorationVictoryFact:
    """旁路系统所需的最小胜利事实，不包含任何业务快照。"""

    event_id: str
    character_id: str
    character_name: str
    world_id: StableId
    region_id: StableId
    encounter_kind: str
    resolved_at: datetime

    def __post_init__(self) -> None:
        if not self.event_id.strip() or not self.character_id.strip() or not self.character_name.strip():
            raise ValueError("探险胜利事实缺少身份")
        object.__setattr__(self, "world_id", stable_id(self.world_id, field="world id"))
        object.__setattr__(self, "region_id", stable_id(self.region_id, field="region id"))
        if self.encounter_kind not in {"normal", "elite", "boss"}:
            raise ValueError("探险胜利事实遭遇类型无效")
        if self.resolved_at.tzinfo is None or self.resolved_at.utcoffset() is None:
            raise ValueError("探险胜利事实时间必须包含时区")


__all__ = ["EXPLORATION_VICTORY_FACT_KIND", "ExplorationVictoryFact"]
