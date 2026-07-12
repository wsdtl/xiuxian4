"""一次规则执行的固定阶段。"""

from __future__ import annotations

from enum import IntEnum


class ExecutionPhase(IntEnum):
    """阶段值同时代表执行顺序，不能在具体玩法中重新排列。"""

    PREPARE = 10
    PAY_COST = 20
    SELECT_TARGET = 30
    BEFORE_APPLY = 40
    RESOLVE = 50
    AFTER_APPLY = 60
    TURN_END = 70


__all__ = ["ExecutionPhase"]
