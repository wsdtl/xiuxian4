"""物品查询与使用二级组件命令。"""

from __future__ import annotations

from launch.adapter import Depends

from ..command import GameCommand
from ..dependencies import current_character, current_character_overview
from . import service


@GameCommand.handler(cmd="纳戒")
async def nacre(
    message: str = "",
    overview=Depends(current_character_overview),
) -> None:
    """分页查看恢复药和特殊物品。"""

    await service.nacre(message, overview)


@GameCommand.handler(cmd="武库")
async def armory(
    message: str = "",
    overview=Depends(current_character_overview),
) -> None:
    """查看武器装备部位总览或指定部位。"""

    await service.armory(message, overview)


@GameCommand.handler(cmd="背包")
async def backpack(
    message: str = "",
    overview=Depends(current_character_overview),
) -> None:
    """分页查看占用背包空间的物资。"""

    await service.backpack(message, overview)


@GameCommand.handler(cmd="查看")
async def inspect(
    message: str = "",
    overview=Depends(current_character_overview),
) -> None:
    """查看当前角色持有的永久编号物品。"""

    await service.inspect(message, overview)


@GameCommand.handler(cmd="使用")
async def use_item(
    message: str = "",
    current=Depends(current_character),
) -> None:
    """使用当前角色持有的可消耗物品。"""

    await service.use_item(message, current)


__all__ = []
