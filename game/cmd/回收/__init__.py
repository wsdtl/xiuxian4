"""系统回收二级组件命令。"""

from __future__ import annotations

from launch.adapter import Depends

from ..command import GameCommand, HelpSpec
from ..dependencies import current_character, current_character_overview
from . import service


@GameCommand.handler(
    cmd="回收",
    help=HelpSpec(
        category="资产",
        summary="查看单件武器或装备的系统回收报价",
        usage=("回收 物品编号",),
        side_effect="确认报价后物品销毁并获得对应货币",
        order=120,
    ),
)
async def recycle(message: str = "", overview=Depends(current_character_overview)) -> None:
    await service.recycle_one(message, overview)


@GameCommand.handler(
    cmd="批量回收",
    help=HelpSpec(
        category="资产",
        summary="按部位、品质和等级筛选批量回收",
        usage=("批量回收",),
        side_effect="最终确认后符合筛选的物品会统一销毁",
        order=130,
    ),
)
async def recycle_batch(message: str = "", overview=Depends(current_character_overview)) -> None:
    await service.recycle_batch(message, overview)


@GameCommand.handler(
    cmd="回收战利品",
    help=HelpSpec(
        category="资产",
        summary="一次出售背包中的全部战利品",
        usage=("回收战利品",),
        side_effect="直接销毁全部战利品并按固定价格结算",
        order=140,
    ),
)
async def recycle_trophies(current=Depends(current_character)) -> None:
    await service.recycle_trophies(current)


@GameCommand.handler(cmd="economy_recycle_confirm", hidden=True)
async def confirm_recycle(
    message: str = "",
    overview=Depends(current_character_overview),
) -> None:
    await service.confirm_recycle(message, overview)


__all__ = []
