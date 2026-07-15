"""角色二级组件命令。"""

from __future__ import annotations

from launch.adapter import Depends

from ..command import GameCommand
from ..dependencies import current_character, current_character_overview
from . import service


@GameCommand.handler(cmd="创建角色", access="public")
async def create_character(message: str = "") -> None:
    """创建当前消息发送者的角色。"""

    await service.create_character(message)


@GameCommand.handler(cmd="我的角色", access="public")
async def view_character(
    overview=Depends(current_character_overview),
) -> None:
    """查看当前消息发送者的角色状态。"""

    await service.view_character(overview)


@GameCommand.handler(cmd="心情")
async def mood(
    message: str = "",
    current=Depends(current_character),
) -> None:
    """查看或修改彩色人物头开关。"""

    await service.mood(message, current)


__all__ = []
