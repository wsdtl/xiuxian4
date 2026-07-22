"""构筑试炼二级组件命令。"""

from __future__ import annotations

from launch.adapter import Depends

from ..command import GameCommand, HelpSpec
from ..dependencies import current_character
from . import service


@GameCommand.handler(
    cmd="构筑试炼",
    help=HelpSpec(
        category="战斗与社交",
        summary="查看单体、群体和持久三种无损构筑试炼",
        usage=("构筑试炼",),
        side_effect="只展示模式，不改变角色状态",
        order=40,
    ),
)
async def view_trials() -> None:
    """展示三个固定模式及其直接开始按钮。"""

    await service.view_trials()


@GameCommand.handler(
    cmd="开始试炼",
    help=HelpSpec(
        category="战斗与社交",
        summary="用当前配装和伙伴运行一次固定种子试炼",
        usage=("开始试炼 单体", "开始试炼 群体", "开始试炼 持久"),
        side_effect="只新增公开战报，不消耗资源，也不发放收益",
        order=50,
    ),
)
async def start_trial(
    message: str = "",
    current=Depends(current_character),
) -> None:
    """执行指定模式并返回紧凑摘要和完整战报。"""

    await service.start_trial(message, current)


__all__ = []
