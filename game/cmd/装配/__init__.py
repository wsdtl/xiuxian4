"""装配二级组件命令。"""

from __future__ import annotations

from launch.adapter import Depends

from ..command import GameCommand
from ..dependencies import current_character
from . import service


@GameCommand.handler(cmd="装配")
async def loadout(current=Depends(current_character)) -> None:
    """查看当前槽位与可装备候选。"""

    await service.view_loadout(current)


@GameCommand.handler(cmd="装备")
async def equip(
    message: str = "",
    current=Depends(current_character),
) -> None:
    """把指定永久编号的武器或装备装入当前配装。"""

    await service.equip(message, current)


@GameCommand.handler(cmd="卸下")
async def unequip(
    message: str = "",
    current=Depends(current_character),
) -> None:
    """卸下当前配装的指定槽位。"""

    await service.unequip(message, current)


@GameCommand.handler(cmd="配装")
async def presets(
    message: str = "",
    current=Depends(current_character),
) -> None:
    """查看或激活零至五号配装。"""

    await service.presets(message, current)


__all__ = []
