"""无损切磋二级组件命令。"""

from __future__ import annotations

from launch.adapter import Depends

from ..command import GameCommand, HelpSpec
from ..dependencies import current_character
from . import service


@GameCommand.handler(
    cmd="切磋",
    help=HelpSpec(
        category="战斗与社交",
        summary="向指定玩家发起一场无损自动战斗",
        usage=("切磋 玩家",),
        side_effect="只生成战斗结果和公开战报，不改变双方资源与资产",
        order=10,
    ),
)
async def challenge(
    message: str = "",
    current=Depends(current_character),
) -> None:
    """向指定玩家发起一份十分钟内有效的切磋请求。"""

    await service.challenge(message, current)


@GameCommand.handler(
    cmd="接受切磋",
    help=HelpSpec(
        category="战斗与社交",
        summary="接受属于当前角色的有效切磋请求",
        usage=("接受切磋 请求编号",),
        side_effect="接受后立即完成一场无损战斗",
        order=20,
    ),
)
async def accept(
    message: str = "",
    current=Depends(current_character),
) -> None:
    """应战并立即完成一场无损自动战斗。"""

    await service.accept(message, current)


@GameCommand.handler(
    cmd="拒绝切磋",
    help=HelpSpec(
        category="战斗与社交",
        summary="拒绝属于当前角色的切磋请求",
        usage=("拒绝切磋 请求编号",),
        order=30,
    ),
)
async def reject(
    message: str = "",
    current=Depends(current_character),
) -> None:
    """拒绝属于当前角色的待处理切磋请求。"""

    await service.reject(message, current)


__all__ = []
