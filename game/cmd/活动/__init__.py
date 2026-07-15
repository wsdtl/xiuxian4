"""全服活动列表与详情的内部入口。"""

from __future__ import annotations

from launch.adapter import Depends

from ..command import GameCommand
from ..dependencies import current_character
from ..reply_intents import (
    WORLD_EVENT_DETAIL_INTENT,
    WORLD_EVENTS_INTENT,
    reply_intents,
)
from . import service


reply_intents.register_command(WORLD_EVENTS_INTENT, "world_events")
reply_intents.register(
    WORLD_EVENT_DETAIL_INTENT,
    lambda payload: f"world_events {payload['instance_id']}",
)


@GameCommand.handler(cmd="world_events")
async def view_world_events(
    message: str = "",
    current=Depends(current_character),
) -> None:
    """查看全部开放活动或指定活动实例详情。"""

    await service.view_world_events(message, current)


__all__ = []
