"""物品查询与使用二级组件命令。"""

from __future__ import annotations

from launch.adapter import Depends

from ..command import GameCommand, HelpSpec
from ..dependencies import current_character, current_character_overview
from . import service


@GameCommand.handler(
    cmd="纳戒",
    help=HelpSpec(
        category="资产",
        summary="查看恢复药、特殊物品和破境凭证",
        usage=("纳戒", "纳戒 页码"),
        order=10,
    ),
)
async def nacre(
    message: str = "",
    overview=Depends(current_character_overview),
) -> None:
    """分页查看纳戒中的可堆叠物品。"""

    await service.nacre(message, overview)


@GameCommand.handler(
    cmd="武库",
    help=HelpSpec(
        category="资产",
        summary="查看武器与六个装备部位的收藏",
        usage=("武库", "武库 部位", "武库 部位 页码"),
        order=20,
    ),
)
async def armory(
    message: str = "",
    overview=Depends(current_character_overview),
) -> None:
    """查看武器装备部位总览或指定部位。"""

    await service.armory(message, overview)


@GameCommand.handler(
    cmd="背包",
    help=HelpSpec(
        category="资产",
        summary="查看占用背包空间的战利品和经济物资",
        usage=("背包", "背包 页码"),
        order=30,
    ),
)
async def backpack(
    message: str = "",
    overview=Depends(current_character_overview),
) -> None:
    """分页查看占用背包空间的物资。"""

    await service.backpack(message, overview)


@GameCommand.handler(
    cmd="查看",
    help=HelpSpec(
        category="资产",
        summary="查看自己持有的永久编号物品详情",
        usage=("查看 物品编号",),
        order=40,
    ),
)
async def inspect(
    message: str = "",
    overview=Depends(current_character_overview),
) -> None:
    """查看当前角色持有的永久编号物品。"""

    await service.inspect(message, overview)


@GameCommand.handler(
    cmd="使用",
    help=HelpSpec(
        category="资产",
        summary="使用恢复药或特殊物品",
        usage=("使用 物品编号", "使用 物品编号 数量"),
        side_effect="成功后会消耗对应物品",
        order=50,
    ),
)
async def use_item(
    message: str = "",
    current=Depends(current_character),
) -> None:
    """使用当前角色持有的可消耗物品。"""

    await service.use_item(message, current)


__all__ = []
