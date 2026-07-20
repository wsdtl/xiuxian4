"""装配二级组件命令。"""

from __future__ import annotations

from launch.adapter import Depends

from ..command import GameCommand, HelpSpec
from ..dependencies import current_character
from . import service


@GameCommand.handler(
    cmd="装配",
    help=HelpSpec(
        category="资产",
        summary="查看当前配装槽位和可装备候选",
        usage=("装配",),
        order=60,
    ),
)
async def loadout(current=Depends(current_character)) -> None:
    """查看当前槽位与可装备候选。"""

    await service.view_loadout(current)


@GameCommand.handler(
    cmd="装备",
    help=HelpSpec(
        category="资产",
        summary="把指定武器或装备装入当前配装",
        usage=("装备 物品编号",),
        side_effect="物品会绑定到当前配装，不能被其他配装重复引用",
        order=70,
    ),
)
async def equip(
    message: str = "",
    current=Depends(current_character),
) -> None:
    """把指定永久编号的武器或装备装入当前配装。"""

    await service.equip(message, current)


@GameCommand.handler(
    cmd="卸下",
    help=HelpSpec(
        category="资产",
        summary="卸下当前配装的指定部位",
        usage=("卸下 部位",),
        order=80,
    ),
)
async def unequip(
    message: str = "",
    current=Depends(current_character),
) -> None:
    """卸下当前配装的指定槽位。"""

    await service.unequip(message, current)


@GameCommand.handler(
    cmd="配装",
    help=HelpSpec(
        category="资产",
        summary="查看或激活零至五号配装",
        usage=("配装", "配装 编号"),
        side_effect="切换后后续战斗和装备操作使用目标配装",
        order=90,
    ),
)
async def presets(
    message: str = "",
    current=Depends(current_character),
) -> None:
    """查看或激活零至五号配装。"""

    await service.presets(message, current)


__all__ = []
