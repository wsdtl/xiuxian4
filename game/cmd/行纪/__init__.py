"""行纪查询与永久排行命令。"""

from __future__ import annotations

from launch.adapter import Depends

from ..command import GameCommand, HelpSpec
from ..dependencies import current_character_overview
from . import service


@GameCommand.handler(
    cmd="行纪",
    help=HelpSpec(
        category="世界",
        summary="查看各世界与探险区域的永久探索进度",
        usage=("行纪", "行纪 世界名称", "行纪 地点名称"),
        order=75,
    ),
)
async def world_progress(
    message: str = "",
    overview=Depends(current_character_overview),
) -> None:
    await service.view_world_progress(message, overview)


@GameCommand.handler(
    cmd="行纪排行",
    help=HelpSpec(
        category="世界",
        summary="查看永久行纪总榜或单世界前十",
        usage=("行纪排行", "行纪排行 世界名称"),
        order=76,
    ),
)
async def world_progress_ranking(
    message: str = "",
    overview=Depends(current_character_overview),
) -> None:
    await service.view_world_progress_ranking(message, overview)


__all__ = []
