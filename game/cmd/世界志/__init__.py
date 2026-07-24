"""世界志查看与重读命令。"""

from __future__ import annotations

from launch.adapter import Depends

from ..command import GameCommand, HelpSpec
from ..dependencies import current_character_overview
from . import service


@GameCommand.handler(
    cmd="世界志",
    help=HelpSpec(
        category="世界",
        summary="随行纪进度查看各世界逐步显露的历史与隐秘",
        usage=("世界志", "世界志 世界名称", "世界志 世界名称 记录序号"),
        order=77,
    ),
)
async def world_lore(
    message: str = "",
    overview=Depends(current_character_overview),
) -> None:
    await service.view_world_lore(message, overview)


__all__ = []
