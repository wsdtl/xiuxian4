"""彩票玩法持久状态的结构化白名单。"""

from game.rules.lottery import LotteryRound, LotteryState, LotteryTicket, LotteryWinner


def lottery_codec_registrations() -> tuple[tuple[str, type[object]], ...]:
    return (
        ("game.lottery.ticket.v1", LotteryTicket),
        ("game.lottery.winner.v1", LotteryWinner),
        ("game.lottery.round.v1", LotteryRound),
        ("game.lottery.state.v1", LotteryState),
    )


__all__ = ["lottery_codec_registrations"]
