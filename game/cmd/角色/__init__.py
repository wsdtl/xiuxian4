"""角色二级组件的消息命令注册入口。"""

from __future__ import annotations

from launch.adapter import MessageHandler

from .service import create_character


COMMAND = "创建角色"
COMMAND_METADATA = {"game": {"component": "角色", "access": "public"}}


@MessageHandler.handler(
    cmd=COMMAND,
    priority=100,
    block=True,
    metadata=COMMAND_METADATA,
)
async def create_character_command(message: str = "") -> None:
    """创建当前消息发送者的角色。"""

    await create_character(message)


__all__ = ["COMMAND"]
