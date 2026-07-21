"""当前世界地图查询命令。"""

from __future__ import annotations

from launch.adapter import Depends

from ..command import GameCommand, HelpSpec
from ..dependencies import current_character_overview
from . import service


@GameCommand.handler(
    cmd="地图",
    help=HelpSpec(
        category="世界",
        summary="查看当前世界全部地点或一处地点的详情",
        usage=("地图", "地图 地点名称"),
        order=70,
    ),
)
async def map_view(
    message: str = "",
    overview=Depends(current_character_overview),
) -> None:
    """展示当前真实世界的地图，不参与地点移动。"""

    await service.view_map(message, overview)


__all__ = []
