"""探险二级组件命令。"""

from __future__ import annotations

from launch.adapter import Depends

from ..command import GameCommand
from ..dependencies import current_character
from . import service


@GameCommand.handler(cmd="探险")
async def exploration(current=Depends(current_character)) -> None:
    """查看当前位置、区域目录与持续探险状态。"""

    await service.view_exploration(current)


@GameCommand.handler(cmd="前往")
async def move(message: str = "", current=Depends(current_character)) -> None:
    """免费前往一处已登记地点。"""

    await service.move(message, current)


@GameCommand.handler(cmd="开始探险")
async def start(current=Depends(current_character)) -> None:
    """在当前位置开始每十分钟结算一次的持续探险。"""

    await service.start(current)


@GameCommand.handler(cmd="停止探险")
async def stop(current=Depends(current_character)) -> None:
    """先补算到期批次，再停止当前探险。"""

    await service.stop(current)


@GameCommand.handler(cmd="探险总结")
async def summary(current=Depends(current_character)) -> None:
    """查看当前或最近一次探险的累计结果。"""

    await service.summary(current)


__all__ = []
