"""抽奖二级组件命令。"""

from __future__ import annotations

from launch.adapter import Depends

from ..command import GameCommand
from ..dependencies import current_character
from . import service


@GameCommand.handler(cmd="抽奖")
async def draw_once(current=Depends(current_character)) -> None:
    await service.draw(current, 1)


@GameCommand.handler(cmd="十连抽奖")
async def draw_ten(current=Depends(current_character)) -> None:
    await service.draw(current, 10)


@GameCommand.handler(cmd="抽奖奖池")
async def draw_pool(current=Depends(current_character)) -> None:
    await service.pool(current)


@GameCommand.handler(cmd="抽奖记录")
async def draw_history(current=Depends(current_character)) -> None:
    await service.history(current)


__all__ = []
