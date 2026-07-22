"""Web 游戏台生命周期注册。"""

from __future__ import annotations

from launch import C, OnEvent, logger
from launch.message_events import subscribe_message_events, unsubscribe_message_events

from .console import service


@OnEvent.connect(priority=180)
async def start_web_console() -> None:
    if not service.auth.configured:
        logger.opt(colors=True).info(C.warn("Web 游戏台未配置，消息服务保持关闭"))
        return
    await service.start()
    subscribe_message_events(service.handle_event)
    logger.opt(colors=True).info(C.ok("Web 游戏台消息服务已启动"))


@OnEvent.disconnect(priority=180)
async def stop_web_console() -> None:
    unsubscribe_message_events(service.handle_event)
    await service.shutdown()
    logger.opt(colors=True).info(C.warn("Web 游戏台消息服务已关闭"))


__all__ = []
