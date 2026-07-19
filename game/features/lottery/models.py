"""彩票命令层使用的只读视图。"""

from __future__ import annotations

from dataclasses import dataclass

from game.rules.lottery import LotteryRound, LotteryTicket, LotteryWinner


@dataclass(frozen=True)
class LotteryPlayerView:
    signup_round_day: str
    current_round: LotteryRound | None
    current_ticket: LotteryTicket | None
    due_round: LotteryRound | None
    due_ticket: LotteryTicket | None
    due_winner: LotteryWinner | None
    tax_balance: int


__all__ = ["LotteryPlayerView"]
