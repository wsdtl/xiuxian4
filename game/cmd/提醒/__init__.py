"""全局提醒与待领取汇总命令。"""

from __future__ import annotations

from launch.adapter import Depends

from ..command import GameCommand
from ..dependencies import current_character
from ..reply_intents import (
    NOTIFICATIONS_INTENT,
    PENDING_ACTIONS_INTENT,
)
from . import service


@GameCommand.handler(cmd="notifications", intent_ids=(NOTIFICATIONS_INTENT,))
async def view_notifications(current=Depends(current_character)) -> None:
    """查看当前账号的有效未读通知。"""

    await service.view_notifications(current)


@GameCommand.handler(cmd="pending_actions", intent_ids=(PENDING_ACTIONS_INTENT,))
async def view_pending_actions(current=Depends(current_character)) -> None:
    """查看当前角色已经完成但尚未领取的行动。"""

    await service.view_pending_actions(current)


__all__ = []
