"""角色界相查询与跃迁命令。"""

from __future__ import annotations

from launch.adapter import Depends

from ..command import GameCommand
from ..dependencies import current_character
from . import service


@GameCommand.handler(cmd="跃迁")
async def dimension_shift(
    message: str = "",
    current=Depends(current_character),
) -> None:
    """查看当前界相，或在空闲时跃迁至指定世界。"""

    await service.dimension_shift(message, current)


__all__ = []
