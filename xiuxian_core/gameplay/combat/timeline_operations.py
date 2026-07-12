"""Effect 向战斗编排层提交的类型化行动指令。"""

from __future__ import annotations

from dataclasses import dataclass

from ..effects import EffectContribution, EffectFact, EffectOperationContext, EffectOperationHandlers
from ..ids import StableId, stable_id


@dataclass(frozen=True)
class RequestExtraTurn:
    id: StableId

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="operation id"))


@dataclass(frozen=True)
class RequestTurnDelay:
    id: StableId
    positions: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="operation id"))
        if self.positions < 1:
            raise ValueError("RequestTurnDelay.positions 必须大于 0")


@dataclass(frozen=True)
class RequestInterrupt:
    id: StableId

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="operation id"))


def register_timeline_operations(handlers: EffectOperationHandlers) -> None:
    def extra_turn(
        operation: RequestExtraTurn,
        _context: EffectOperationContext,
    ) -> EffectContribution:
        return EffectContribution(
            facts=(
                EffectFact(
                    "combat.timeline.extra_turn_requested",
                    "combat.timeline",
                    {"operation_id": operation.id},
                ),
            )
        )

    def delay(
        operation: RequestTurnDelay,
        _context: EffectOperationContext,
    ) -> EffectContribution:
        return EffectContribution(
            facts=(
                EffectFact(
                    "combat.timeline.delay_requested",
                    "combat.timeline",
                    {"operation_id": operation.id, "positions": operation.positions},
                ),
            )
        )

    def interrupt(
        operation: RequestInterrupt,
        _context: EffectOperationContext,
    ) -> EffectContribution:
        return EffectContribution(
            facts=(
                EffectFact(
                    "combat.action.interrupted",
                    "combat.action",
                    {"operation_id": operation.id},
                ),
            )
        )

    handlers.register(RequestExtraTurn, extra_turn)
    handlers.register(RequestTurnDelay, delay)
    handlers.register(RequestInterrupt, interrupt)


__all__ = [
    "RequestExtraTurn",
    "RequestInterrupt",
    "RequestTurnDelay",
    "register_timeline_operations",
]
