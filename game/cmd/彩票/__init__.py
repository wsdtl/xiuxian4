"""彩票系统二级组件命令。"""

from __future__ import annotations

from launch.adapter import Depends

from ..command import GameCommand, HelpSpec
from ..dependencies import current_character
from . import jobs as jobs  # noqa: F401
from . import service


@GameCommand.handler(
    cmd="彩票",
    help=HelpSpec(
        category="活动",
        summary="查看本期彩票状态、号码和奖池",
        usage=("彩票",),
        order=50,
    ),
)
async def lottery(current=Depends(current_character)) -> None:
    await service.lottery(current)


@GameCommand.handler(
    cmd="购票",
    help=HelpSpec(
        category="活动",
        summary="为本期彩票选择一组号码",
        usage=("购票 六位号码",),
        side_effect="每期每人只能购买一张并支付当期票价",
        order=60,
    ),
)
async def purchase(message: str = "", current=Depends(current_character)) -> None:
    await service.purchase(message, current)


@GameCommand.handler(
    cmd="中奖记录",
    help=HelpSpec(
        category="活动",
        summary="查看近期彩票中奖结果",
        usage=("中奖记录",),
        order=70,
    ),
)
async def winner_history(current=Depends(current_character)) -> None:
    await service.winner_history(current)


__all__ = []
