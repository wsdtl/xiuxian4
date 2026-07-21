"""跨界灾厄二级组件命令和公共活动入口。"""

from __future__ import annotations

from launch.adapter import Depends

from ..command import GameCommand, HelpSpec
from ..dependencies import current_character
from ..reply_intents import DIMENSIONAL_DISASTER_INTENT, reply_intents
from . import jobs as jobs  # noqa: F401
from . import service


reply_intents.register_command(DIMENSIONAL_DISASTER_INTENT, "跨界灾厄")


@GameCommand.handler(
    cmd="跨界灾厄",
    help=HelpSpec(
        category="战斗与社交",
        summary="查看当前降临或最近一次跨界灾厄",
        usage=("跨界灾厄",),
        order=40,
    ),
)
async def view_disaster(current=Depends(current_character)) -> None:
    """查看当前降临或最近一次跨界灾厄。"""

    await service.view_disaster(current)


@GameCommand.handler(
    cmd="讨伐灾厄",
    help=HelpSpec(
        category="战斗与社交",
        summary="使用当前真实角色和配装讨伐灾厄",
        usage=("讨伐灾厄",),
        side_effect="消耗本期可用讨伐次数并记录贡献",
        order=50,
    ),
)
async def challenge_disaster(current=Depends(current_character)) -> None:
    """使用当前真实配装和角色状态进行一次讨伐。"""

    await service.challenge_disaster(current)


@GameCommand.handler(
    cmd="灾厄排行",
    help=HelpSpec(
        category="战斗与社交",
        summary="查看当前或最近灾厄的贡献排行",
        usage=("灾厄排行",),
        order=60,
    ),
)
async def disaster_ranking(current=Depends(current_character)) -> None:
    """查看当前或最近灾厄的贡献排行。"""

    await service.disaster_ranking(current)


__all__ = []
