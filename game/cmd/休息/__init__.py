"""休息二级组件命令。"""

from __future__ import annotations

from launch.adapter import Depends

from ..command import GameCommand
from ..dependencies import current_character
from . import service


@GameCommand.handler(cmd="休息")
async def rest(current=Depends(current_character)) -> None:
    """查看当前休息状态与开始入口。"""

    await service.view(current)


@GameCommand.handler(cmd="rest_start")
async def start_rest(current=Depends(current_character)) -> None:
    """由休息面板按钮开始休息。"""

    await service.start(current)


@GameCommand.handler(cmd="停止休息")
async def stop_rest(current=Depends(current_character)) -> None:
    """结算累计有效时间并停止休息。"""

    await service.stop(current)


__all__ = []
