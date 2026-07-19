"""彩票轮次、号码和中奖结果的不可变模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping


LOTTERY_RULESET_VERSION = "rules.lottery.v1"


@dataclass(frozen=True)
class LotteryTicket:
    character_id: str
    character_name: str
    number: str

    def __post_init__(self) -> None:
        if not self.character_id.strip() or not self.character_name.strip():
            raise ValueError("彩票号码缺少角色身份")
        if len(self.number) != 6 or not self.number.isdigit():
            raise ValueError("彩票号码必须是六位数字")


@dataclass(frozen=True)
class LotteryWinner:
    character_id: str
    character_name: str
    number: str
    tier: str
    rank: int
    distance: int
    amount: int

    def __post_init__(self) -> None:
        if not self.character_id.strip() or not self.character_name.strip():
            raise ValueError("彩票中奖记录缺少角色身份")
        if len(self.number) != 6 or not self.number.isdigit():
            raise ValueError("中奖号码必须是六位数字")
        if self.rank < 1 or self.distance < 0 or self.amount < 1:
            raise ValueError("彩票中奖记录数值无效")


@dataclass(frozen=True)
class LotteryRound:
    round_day: str
    status: str = "pending"
    tickets: Mapping[str, LotteryTicket] = field(default_factory=dict)
    winning_number: str = ""
    pool_amount: int = 0
    payout_amount: int = 0
    winners: tuple[LotteryWinner, ...] = ()
    reason: str = ""

    def __post_init__(self) -> None:
        if not self.round_day.strip():
            raise ValueError("彩票轮次缺少日期")
        if self.status not in {"pending", "opened", "skipped"}:
            raise ValueError("彩票轮次状态无效")
        tickets = dict(self.tickets)
        if any(key != value.character_id for key, value in tickets.items()):
            raise ValueError("彩票号码映射键与角色 id 不一致")
        if len({value.number for value in tickets.values()}) != len(tickets):
            raise ValueError("同一彩票轮次不能重复使用号码")
        if self.winning_number and (
            len(self.winning_number) != 6 or not self.winning_number.isdigit()
        ):
            raise ValueError("彩票开奖号必须是六位数字")
        if self.pool_amount < 0 or self.payout_amount < 0:
            raise ValueError("彩票金额不能小于 0")
        if self.payout_amount > self.pool_amount:
            raise ValueError("彩票支出不能超过本期开奖池")
        object.__setattr__(self, "tickets", MappingProxyType(tickets))
        object.__setattr__(self, "winners", tuple(self.winners))


@dataclass(frozen=True)
class LotteryState:
    scope_id: str = "lottery.primary"
    rounds: Mapping[str, LotteryRound] = field(default_factory=dict)
    revision: int = 0

    def __post_init__(self) -> None:
        if not self.scope_id.strip() or self.revision < 0:
            raise ValueError("彩票状态身份或版本无效")
        rounds = dict(self.rounds)
        if any(key != value.round_day for key, value in rounds.items()):
            raise ValueError("彩票轮次映射键与轮次日期不一致")
        object.__setattr__(self, "rounds", MappingProxyType(rounds))


__all__ = [
    "LOTTERY_RULESET_VERSION",
    "LotteryRound",
    "LotteryState",
    "LotteryTicket",
    "LotteryWinner",
]
