"""彩票周期、环形号码和奖池规则。"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from game.content.catalog.economy import (
    LOTTERY_CENTRAL_SUBSIDY_MULTIPLIER,
    LOTTERY_CENTRAL_SUBSIDY_RATE,
    LOTTERY_MIN_PARTICIPANTS,
    LOTTERY_POOL_MAX,
    LOTTERY_TICKET_PRICE,
)


DRAW_HOUR = 21
DRAW_MINUTE = 0
DRAW_POOL_MAX = LOTTERY_POOL_MAX
DRAW_MIN_PARTICIPANTS = LOTTERY_MIN_PARTICIPANTS


def signup_round_day(current: datetime, timezone: str) -> str:
    local = current.astimezone(ZoneInfo(timezone))
    day = local.date()
    if local.hour >= DRAW_HOUR:
        day += timedelta(days=1)
    return day.isoformat()


def due_round_day(current: datetime, timezone: str) -> str:
    local = current.astimezone(ZoneInfo(timezone))
    day = local.date()
    if local.hour < DRAW_HOUR:
        day -= timedelta(days=1)
    return day.isoformat()


def round_draw_at(round_day: str, timezone: str) -> datetime:
    return datetime.combine(
        date.fromisoformat(round_day),
        time(DRAW_HOUR, DRAW_MINUTE),
        tzinfo=ZoneInfo(timezone),
    )


def pool_breakdown(balance: int, participant_count: int) -> tuple[int, int, int]:
    """返回售票基础池、中央补贴和可实际支出的总奖池。"""

    available = max(0, int(balance))
    count = max(0, int(participant_count))
    base = count * LOTTERY_TICKET_PRICE
    if base <= 0:
        return 0, 0, 0
    funded_base = min(base, DRAW_POOL_MAX)
    if available < funded_base:
        return base, 0, min(available, DRAW_POOL_MAX)
    subsidy = min(
        int(available * LOTTERY_CENTRAL_SUBSIDY_RATE),
        base * LOTTERY_CENTRAL_SUBSIDY_MULTIPLIER,
        available - funded_base,
        max(0, DRAW_POOL_MAX - funded_base),
    )
    return base, subsidy, funded_base + subsidy


def estimated_pool(balance: int, participant_count: int) -> int:
    return pool_breakdown(balance, participant_count)[2]


def circular_distance(number: str, winning_number: str) -> int:
    difference = abs(int(number) - int(winning_number))
    return min(difference, 1_000_000 - difference)


def prize_tiers(participant_count: int) -> tuple[tuple[str, int, float], ...]:
    count = max(0, int(participant_count))
    if count < DRAW_MIN_PARTICIPANTS:
        return ()
    if count <= 3:
        return (("一等奖", 1, 1.00),)
    if count <= 10:
        return (("一等奖", 1, 0.60), ("二等奖", min(3, count - 1), 0.40))
    return (
        ("一等奖", 1, 0.50),
        ("二等奖", min(3, count - 1), 0.30),
        ("三等奖", min(10, count - 4), 0.20),
    )


__all__ = [
    "DRAW_HOUR",
    "DRAW_MIN_PARTICIPANTS",
    "DRAW_MINUTE",
    "DRAW_POOL_MAX",
    "circular_distance",
    "due_round_day",
    "estimated_pool",
    "pool_breakdown",
    "prize_tiers",
    "round_draw_at",
    "signup_round_day",
]
