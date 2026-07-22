"""Web 游戏台入口命令。"""

from __future__ import annotations

from launch.paths import public_url
from message import Action, M

from ..reply import send_game_reply


async def show_entry() -> None:
    url = public_url("game-console")
    await send_game_reply(
        M.document()
        .section("Web 游戏台", icon="system")
        .line("使用网页账号密码登录后，以归航公约维护员身份进入。")
        .line(M.link("打开 Web 游戏台", url))
        .actions(
            (
                Action(
                    "web_console.open",
                    "打开游戏台",
                    url,
                    behavior="link",
                ),
            )
        )
        .build()
    )


__all__ = ["show_entry"]
