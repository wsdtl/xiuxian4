"""世界志业务的已读状态和查询结果。"""

from __future__ import annotations

from dataclasses import dataclass

from game.content.world_lore import WorldLoreDefinition, WorldLoreRecord
from game.core.gameplay import StableId, stable_id


WORLD_LORE_AGGREGATE = "game.world_lore.state"


@dataclass(frozen=True)
class WorldLoreState:
    character_id: str
    world_id: StableId
    seen_record_ids: tuple[StableId, ...] = ()
    revision: int = 0

    def __post_init__(self) -> None:
        character_id = str(self.character_id or "").strip()
        if not character_id:
            raise ValueError("世界志状态缺少角色 ID")
        seen = tuple(
            stable_id(value, field="world lore record id")
            for value in self.seen_record_ids
        )
        if len(seen) != len(set(seen)):
            raise ValueError("世界志状态存在重复已读记录")
        if self.revision < 0:
            raise ValueError("世界志状态 revision 不能小于 0")
        object.__setattr__(self, "character_id", character_id)
        object.__setattr__(self, "world_id", stable_id(self.world_id, field="world id"))
        object.__setattr__(self, "seen_record_ids", seen)


@dataclass(frozen=True)
class WorldLoreView:
    character_id: str
    definition: WorldLoreDefinition
    percent: int
    available: bool
    unlocked_records: tuple[WorldLoreRecord, ...]
    seen_record_ids: tuple[StableId, ...] = ()

    @property
    def unseen_records(self) -> tuple[WorldLoreRecord, ...]:
        seen = set(self.seen_record_ids)
        return tuple(value for value in self.unlocked_records if value.id not in seen)


@dataclass(frozen=True)
class WorldLoreAcknowledgeResult:
    status: str
    state: WorldLoreState


def world_lore_state_id(character_id: str, world_id: StableId) -> str:
    actor = str(character_id or "").strip()
    if not actor:
        raise ValueError("世界志状态键缺少角色 ID")
    world = stable_id(world_id, field="world id")
    return f"{actor}:{world}"


__all__ = [
    "WORLD_LORE_AGGREGATE",
    "WorldLoreAcknowledgeResult",
    "WorldLoreState",
    "WorldLoreView",
    "world_lore_state_id",
]
