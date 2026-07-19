"""无损切磋二级组件命令。"""

from __future__ import annotations

from launch.adapter import Depends

from ..command import GameCommand
from ..dependencies import current_character
from . import service


@GameCommand.handler(cmd="切磋")
async def challenge(
    message: str = "",
    current=Depends(current_character),
) -> None:
    """向指定玩家发起一份十分钟内有效的切磋请求。"""

    await service.challenge(message, current)


@GameCommand.handler(cmd="接受切磋")
async def accept(
    message: str = "",
    current=Depends(current_character),
) -> None:
    """应战并立即完成一场无损自动战斗。"""

    await service.accept(message, current)


@GameCommand.handler(cmd="拒绝切磋")
async def reject(
    message: str = "",
    current=Depends(current_character),
) -> None:
    """拒绝属于当前角色的待处理切磋请求。"""

    await service.reject(message, current)


__all__ = []
