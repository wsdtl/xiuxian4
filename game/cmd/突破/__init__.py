"""境界突破二级组件。"""

from __future__ import annotations

from launch.adapter import Depends, current_message_context

from ..command import GameCommand, HelpSpec
from ..dependencies import current_character
from . import service


@GameCommand.handler(
    cmd="突破",
    help=HelpSpec(
        category="角色",
        summary="消耗破境凭证突破当前等级关隘",
        usage=("突破",),
        side_effect="成功后消耗一枚破境凭证并恢复血气、灵力",
        order=20,
    ),
)
async def breakthrough(
    current=Depends(current_character),
) -> None:
    """执行一次当前角色的境界突破。"""

    context = current_message_context()
    await service.breakthrough(current, context)


__all__ = []
