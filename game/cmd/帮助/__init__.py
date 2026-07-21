"""玩家帮助二级组件命令。"""

from __future__ import annotations

from ..command import GameCommand, HelpSpec
from . import service


@GameCommand.handler(
    cmd="帮助",
    access="public",
    help=HelpSpec(
        category="角色",
        summary="查看公开命令分类、用法和操作影响",
        usage=("帮助", "帮助 分类", "帮助 命令"),
        order=0,
    ),
)
async def help_command(message: str = "") -> None:
    await service.show_help(message)


@GameCommand.handler(
    cmd="归航公约",
    access="public",
    help=HelpSpec(
        category="世界",
        summary="了解归航者共同归属的跨界公约",
        usage=("归航公约",),
        order=0,
    ),
)
async def covenant_command() -> None:
    await service.show_covenant()


__all__ = []
