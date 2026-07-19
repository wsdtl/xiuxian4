"""系统回收二级组件命令。"""

from __future__ import annotations

from launch.adapter import Depends

from ..command import GameCommand
from ..dependencies import current_character, current_character_overview
from . import service


@GameCommand.handler(cmd="回收")
async def recycle(message: str = "", overview=Depends(current_character_overview)) -> None:
    await service.recycle_one(message, overview)


@GameCommand.handler(cmd="批量回收")
async def recycle_batch(message: str = "", overview=Depends(current_character_overview)) -> None:
    await service.recycle_batch(message, overview)


@GameCommand.handler(cmd="回收战利品")
async def recycle_trophies(current=Depends(current_character)) -> None:
    await service.recycle_trophies(current)


@GameCommand.handler(cmd="economy_recycle_confirm")
async def confirm_recycle(
    message: str = "",
    overview=Depends(current_character_overview),
) -> None:
    await service.confirm_recycle(message, overview)


__all__ = []
