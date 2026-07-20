"""探险二级组件命令。"""

from __future__ import annotations

from launch.adapter import Depends

from ..command import GameCommand, HelpSpec
from ..dependencies import current_character
from . import jobs as jobs  # noqa: F401
from . import service


@GameCommand.handler(
    cmd="探险",
    help=HelpSpec(
        category="行动",
        summary="查看当前位置、区域目录和持续探险状态",
        usage=("探险",),
        order=10,
    ),
)
async def exploration(current=Depends(current_character)) -> None:
    """查看当前位置、区域目录与持续探险状态。"""

    await service.view_exploration(current)


@GameCommand.handler(
    cmd="前往",
    help=HelpSpec(
        category="行动",
        summary="前往当前世界中已经登记的地点",
        usage=("前往 地点名称",),
        side_effect="移动前必须结束正在进行的主要行动",
        order=20,
    ),
)
async def move(message: str = "", current=Depends(current_character)) -> None:
    """免费前往一处已登记地点。"""

    await service.move(message, current)


@GameCommand.handler(
    cmd="开始探险",
    help=HelpSpec(
        category="行动",
        summary="在当前位置开始每十分钟结算一次的探险",
        usage=("开始探险",),
        side_effect="会占用当前主要行动",
        order=30,
    ),
)
async def start(current=Depends(current_character)) -> None:
    """在当前位置开始每十分钟结算一次的持续探险。"""

    await service.start(current)


@GameCommand.handler(
    cmd="停止探险",
    help=HelpSpec(
        category="行动",
        summary="补算已经到期的批次并停止探险",
        usage=("停止探险",),
        side_effect="停止后不再产生新的探险批次",
        order=40,
    ),
)
async def stop(current=Depends(current_character)) -> None:
    """先补算到期批次，再停止当前探险。"""

    await service.stop(current)


@GameCommand.handler(
    cmd="探险总结",
    help=HelpSpec(
        category="行动",
        summary="查看当前或最近一次探险的累计结果",
        usage=("探险总结",),
        order=50,
    ),
)
async def summary(current=Depends(current_character)) -> None:
    """查看当前或最近一次探险的累计结果。"""

    await service.summary(current)


__all__ = []
