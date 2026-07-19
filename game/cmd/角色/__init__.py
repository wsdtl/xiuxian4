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


@GameCommand.handler(cmd="我的角色")
async def view_character(
    overview=Depends(current_character_overview),
) -> None:
    """查看当前消息发送者的角色状态。"""

    await service.view_character(overview)


@GameCommand.handler(cmd="战斗面板")
async def view_combat_panel(
    overview=Depends(current_character_overview),
) -> None:
    """查看当前配装真正生效的全部战斗数据。"""

    await service.view_combat_panel(overview)


@GameCommand.handler(cmd="心情")
async def mood(
    message: str = "",
    current=Depends(current_character),
) -> None:
    """查看或修改彩色人物头开关。"""

    await service.mood(message, current)


@GameCommand.handler(cmd="自动用药")
async def auto_medicine(
    message: str = "",
    current=Depends(current_character),
) -> None:
    """查看或修改探险自动用药开关。"""

    await service.auto_medicine(message, current)


__all__ = []
