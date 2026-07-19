"""角色当前界相及跃迁的具体游戏规则。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from game.core.gameplay import RandomSource, StableId, stable_id


CHARACTER_DIMENSION_AGGREGATE = "snapshot.character_dimension"
CHARACTER_DIMENSION_RULE_VERSION = "rules.character_dimension.v1"


@dataclass(frozen=True)
class CharacterDimensionState:
    """角色当前观察的世界皮肤；不复制角色、资产或世界规则状态。"""

    character_id: str
    skin_id: StableId
    arrived_at: datetime
    revision: int = 0

    def __post_init__(self) -> None:
        character_id = str(self.character_id or "").strip()
        if not character_id:
            raise ValueError("角色界相状态缺少 character_id")
        if self.arrived_at.tzinfo is None or self.arrived_at.utcoffset() is None:
            raise ValueError("角色界相抵达时间必须包含时区")
        if self.revision < 0:
            raise ValueError("角色界相 revision 不能小于 0")
        object.__setattr__(self, "character_id", character_id)
        object.__setattr__(self, "skin_id", stable_id(self.skin_id, field="skin id"))


@dataclass(frozen=True)
class DimensionShiftResult:
    status: str
    current: CharacterDimensionState | None = None
    previous_skin_id: StableId | None = None


def assign_initial_dimension(
    character_id: str,
    skin_ids: tuple[StableId, ...],
    *,
    random: RandomSource,
    logical_time: datetime,
) -> CharacterDimensionState:
    """从全部启用世界中做一次可重放的随机降临。"""

    candidates = tuple(sorted(stable_id(value, field="skin id") for value in skin_ids))
    if not candidates:
        raise ValueError("角色创世没有可用世界皮肤")
    return CharacterDimensionState(
        character_id,
        random.choice(candidates),
        logical_time,
    )


def shift_dimension(
    state: CharacterDimensionState,
    target_skin_id: StableId,
    *,
    logical_time: datetime,
) -> DimensionShiftResult:
    """只改变当前界相；相同目标保持幂等。"""

    target = stable_id(target_skin_id, field="skin id")
    if target == state.skin_id:
        return DimensionShiftResult("already_there", state, state.skin_id)
    updated = replace(
        state,
        skin_id=target,
        arrived_at=logical_time,
        revision=state.revision + 1,
    )
    return DimensionShiftResult("shifted", updated, state.skin_id)


__all__ = [
    "CHARACTER_DIMENSION_AGGREGATE",
    "CHARACTER_DIMENSION_RULE_VERSION",
    "CharacterDimensionState",
    "DimensionShiftResult",
    "assign_initial_dimension",
    "shift_dimension",
]
