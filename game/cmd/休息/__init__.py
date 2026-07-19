"""休息二级组件命令。"""

from __future__ import annotations

from launch.adapter import Depends

from ..command import GameCommand
from ..dependencies import current_character
from . import jobs as jobs  # noqa: F401
from . import service


@GameCommand.handler(cmd="休息")
async def rest(current=Depends(current_character)) -> None:
    """直接开始或续接休息。"""

    await service.start(current)


@GameCommand.handler(cmd="结束休息")
async def stop_rest(current=Depends(current_character)) -> None:
    """结算累计有效时间并结束休息。"""

    await service.stop(current)


__all__ = []
