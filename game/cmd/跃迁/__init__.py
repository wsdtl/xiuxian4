"""跃迁命令组件。"""

from __future__ import annotations

from launch.adapter import Depends

from ..command import GameCommand, HelpSpec
from ..dependencies import current_character
from . import service


@GameCommand.handler(
    cmd="跃迁",
    help=HelpSpec(
        category="世界",
        summary="查看当前世界或登录另一个世界",
        usage=("跃迁", "跃迁 世界名称"),
        side_effect="成功跃迁会消耗对应特殊物品，角色和资产保持不变",
        order=10,
    ),
)
async def dimension_shift(
    message: str = "",
    current=Depends(current_character),
) -> None:
    """查看当前真实世界，或在空闲时跃迁至指定世界。"""

    await service.dimension_shift(message, current)


__all__ = []
