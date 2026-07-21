"""角色当前真实世界及跃迁的纯规则。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from game.core.gameplay import RandomSource, StableId, stable_id


CHARACTER_WORLD_AGGREGATE = "snapshot.character_world"
CHARACTER_WORLD_RULE_VERSION = "rules.character_world.v2"


@dataclass(frozen=True)
class CharacterWorldState:
    """角色唯一化身当前实际所在的玩法世界。"""

    character_id: str
    world_id: StableId
    arrived_at: datetime
    revision: int = 0

    def __post_init__(self) -> None:
        character_id = str(self.character_id or "").strip()
        if not character_id:
            raise ValueError("角色世界状态缺少 character_id")
        if self.arrived_at.tzinfo is None or self.arrived_at.utcoffset() is None:
            raise ValueError("角色抵达世界时间必须包含时区")
        if self.revision < 0:
            raise ValueError("角色世界状态 revision 不能小于 0")
        object.__setattr__(self, "character_id", character_id)
        object.__setattr__(self, "world_id", stable_id(self.world_id, field="world id"))


@dataclass(frozen=True)
class WorldShiftResult:
    status: str
    current: CharacterWorldState | None = None
    previous_world_id: StableId | None = None


def assign_initial_world(
    character_id: str,
    world_ids: tuple[StableId, ...],
    *,
    random: RandomSource,
    logical_time: datetime,
) -> CharacterWorldState:
    """从全部启用的真实世界中做一次可重放随机降临。"""

    candidates = tuple(stable_id(value, field="world id") for value in world_ids)
    if not candidates:
        raise ValueError("角色创世没有可进入的真实世界")
    return CharacterWorldState(
        character_id,
        random.choice(candidates),
        logical_time,
    )


def shift_world(
    state: CharacterWorldState,
    target_world_id: StableId,
    *,
    logical_time: datetime,
) -> WorldShiftResult:
    """只计算角色世界状态变化；跨空间移动由业务事务协调。"""

    target = stable_id(target_world_id, field="world id")
    if target == state.world_id:
        return WorldShiftResult("already_there", state, state.world_id)
    updated = replace(
        state,
        world_id=target,
        arrived_at=logical_time,
        revision=state.revision + 1,
    )
    return WorldShiftResult("shifted", updated, state.world_id)


__all__ = [
    "CHARACTER_WORLD_AGGREGATE",
    "CHARACTER_WORLD_RULE_VERSION",
    "CharacterWorldState",
    "WorldShiftResult",
    "assign_initial_world",
    "shift_world",
]
