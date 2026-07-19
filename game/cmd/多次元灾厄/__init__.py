"""多次元灾厄二级组件命令和全服活动入口。"""

from __future__ import annotations

from launch.adapter import Depends

from ..command import GameCommand
from ..dependencies import current_character
from ..reply_intents import DIMENSIONAL_DISASTER_INTENT, reply_intents
from . import jobs as jobs  # noqa: F401
from . import service


reply_intents.register_command(DIMENSIONAL_DISASTER_INTENT, "多次元灾厄")


@GameCommand.handler(cmd="多次元灾厄")
async def view_disaster(current=Depends(current_character)) -> None:
    """查看当前降临或最近一次多次元灾厄。"""

    await service.view_disaster(current)


@GameCommand.handler(cmd="讨伐灾厄")
async def challenge_disaster(current=Depends(current_character)) -> None:
    """使用当前真实配装和角色状态进行一次讨伐。"""

    await service.challenge_disaster(current)


@GameCommand.handler(cmd="灾厄排行")
async def disaster_ranking(current=Depends(current_character)) -> None:
    """查看当前或最近灾厄的贡献排行。"""

    await service.disaster_ranking(current)


__all__ = []
