"""彩票系统二级组件命令。"""

from __future__ import annotations

from launch.adapter import Depends

from ..command import GameCommand
from ..dependencies import current_character
from . import service


@GameCommand.handler(cmd="彩票")
async def lottery(current=Depends(current_character)) -> None:
    await service.lottery(current)


@GameCommand.handler(cmd="购票")
async def purchase(message: str = "", current=Depends(current_character)) -> None:
    await service.purchase(message, current)


@GameCommand.handler(cmd="中奖记录")
async def winner_history(current=Depends(current_character)) -> None:
    await service.winner_history(current)


__all__ = []
