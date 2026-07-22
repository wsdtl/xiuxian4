"""Web 游戏台命令与 HTTP 组件。"""

from __future__ import annotations

from ..command import GameCommand, HelpSpec
from . import entry, runtime
from .site import router


@GameCommand.handler(
    cmd="web",
    access="public",
    help=HelpSpec(
        category="角色",
        summary="打开受密码保护的 Web 游戏台",
        usage=("web",),
        order=10,
    ),
)
async def web_console() -> None:
    await entry.show_entry()


__all__ = ["router"]
