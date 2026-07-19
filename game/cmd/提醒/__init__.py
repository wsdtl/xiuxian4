"""全局提醒与待领取汇总命令。"""

from __future__ import annotations

from base64 import urlsafe_b64encode

from launch.adapter import Depends

from ..command import GameCommand
from ..dependencies import current_character
from ..reply_intents import (
    NOTIFICATIONS_INTENT,
    NOTIFICATION_READ_INTENT,
    PENDING_ACTIONS_INTENT,
    reply_intents,
)
from . import service


reply_intents.register(
    NOTIFICATION_READ_INTENT,
    lambda payload: "notification_read "
    + urlsafe_b64encode(str(payload["notification_id"]).encode("utf-8")).decode("ascii")
    + f" {int(payload['revision'])}",
)


@GameCommand.handler(cmd="notifications", intent_ids=(NOTIFICATIONS_INTENT,))
async def view_notifications(current=Depends(current_character)) -> None:
    """查看当前账号的有效未读通知。"""

    await service.view_notifications(current)


@GameCommand.handler(cmd="pending_actions", intent_ids=(PENDING_ACTIONS_INTENT,))
async def view_pending_actions(current=Depends(current_character)) -> None:
    """查看当前角色已经完成但尚未领取的行动。"""

    await service.view_pending_actions(current)


@GameCommand.handler(cmd="notification_read")
async def mark_notification_read(
    message: str = "",
    current=Depends(current_character),
) -> None:
    """处理通知列表中的单条已读按钮。"""

    await service.mark_notification_read(message, current)


__all__ = []
