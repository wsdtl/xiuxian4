"""次元灾厄共享血量、挑战次数和结算进度的纯状态变换。"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from game.content.catalog.disaster import DIMENSIONAL_DISASTER_DAILY_ATTEMPTS

from .models import (
    DimensionalDisasterOutcome,
    DimensionalDisasterState,
    DimensionalDisasterStatus,
    DisasterChallengeReceipt,
)


def record_disaster_challenge(
    state: DimensionalDisasterState,
    receipt: DisasterChallengeReceipt,
) -> DimensionalDisasterState:
    if receipt.event_id != state.event_id:
        raise ValueError("挑战回执不属于当前次元灾厄")
    if state.status is not DimensionalDisasterStatus.OPEN:
        raise ValueError("次元灾厄已经停止接受挑战")
    if state.outcome is not DimensionalDisasterOutcome.NONE:
        raise ValueError("次元灾厄已经产生结局")
    previous = state.challenge_receipts.get(receipt.operation_id)
    if previous is not None:
        if previous != receipt and previous.as_replay() != receipt:
            raise ValueError("同一灾厄挑战操作对应不同回执")
        return state
    attempts = {
        character_id: dict(days)
        for character_id, days in state.attempts_by_day.items()
    }
    days = attempts.setdefault(receipt.character_id, {})
    current_attempts = int(days.get(receipt.business_day, 0))
    if current_attempts >= DIMENSIONAL_DISASTER_DAILY_ATTEMPTS:
        raise ValueError("当前业务日的灾厄挑战次数已经用完")
    days[receipt.business_day] = current_attempts + 1
    expected_health = max(0, state.current_health - receipt.damage)
    if (
        receipt.shared_health_before != state.current_health
        or receipt.shared_health_after != expected_health
    ):
        raise ValueError("灾厄挑战回执与当前共享血量不一致")
    receipts = dict(state.challenge_receipts)
    receipts[receipt.operation_id] = receipt
    defeated = expected_health == 0
    return replace(
        state,
        current_health=expected_health,
        attempts_by_day=attempts,
        challenge_receipts=receipts,
        outcome=(
            DimensionalDisasterOutcome.DEFEATED
            if defeated
            else DimensionalDisasterOutcome.NONE
        ),
        defeated_at=receipt.resolved_at if defeated else None,
        revision=state.revision + 1,
    )


def begin_disaster_settlement(
    state: DimensionalDisasterState,
    *,
    logical_time: datetime,
    feather_owner_id: str | None = None,
) -> DimensionalDisasterState:
    if state.status is not DimensionalDisasterStatus.OPEN:
        return state
    if logical_time < state.closes_at:
        raise ValueError("次元灾厄尚未到达结算时间")
    outcome = state.outcome
    if outcome is DimensionalDisasterOutcome.NONE:
        outcome = DimensionalDisasterOutcome.ESCAPED
    owner = str(feather_owner_id or "").strip() or None
    if outcome is not DimensionalDisasterOutcome.DEFEATED and owner is not None:
        raise ValueError("未击破的次元灾厄不能产生铭刻之羽")
    asset_id = f"asset:inscription_feather:{state.event_id}" if owner else None
    return replace(
        state,
        outcome=outcome,
        status=DimensionalDisasterStatus.SETTLING,
        feather_owner_id=owner,
        feather_asset_id=asset_id,
        revision=state.revision + 1,
    )


def mark_disaster_rewarded(
    state: DimensionalDisasterState,
    character_id: str,
) -> DimensionalDisasterState:
    if state.status is not DimensionalDisasterStatus.SETTLING:
        raise ValueError("次元灾厄不在奖励结算阶段")
    normalized = str(character_id or "").strip()
    if not normalized or normalized in state.rewarded_character_ids:
        return state
    return replace(
        state,
        rewarded_character_ids=state.rewarded_character_ids | {normalized},
        revision=state.revision + 1,
    )


def close_disaster(state: DimensionalDisasterState) -> DimensionalDisasterState:
    if state.status is not DimensionalDisasterStatus.SETTLING:
        raise ValueError("次元灾厄尚未完成结算准备")
    return replace(
        state,
        status=DimensionalDisasterStatus.CLOSED,
        revision=state.revision + 1,
    )


__all__ = [
    "begin_disaster_settlement",
    "close_disaster",
    "mark_disaster_rewarded",
    "record_disaster_challenge",
]
