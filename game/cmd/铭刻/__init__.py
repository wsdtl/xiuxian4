"""铭刻二级组件命令。"""

from __future__ import annotations

from launch.adapter import Depends

from ..command import GameCommand, HelpSpec
from ..dependencies import current_character
from ..reply_intents import reply_intents
from . import service


INSCRIPTION_CONFIRM_ASSET_INTENT = "inscription.confirm_asset"
INSCRIPTION_CONFIRM_ABILITY_INTENT = "inscription.confirm_ability"

reply_intents.register(
    INSCRIPTION_CONFIRM_ASSET_INTENT,
    lambda payload: "inscription_confirm_asset " + " ".join(
        str(payload[key]) for key in ("medium", "target", "name")
    ),
)
reply_intents.register(
    INSCRIPTION_CONFIRM_ABILITY_INTENT,
    lambda payload: "inscription_confirm_ability " + " ".join(
        str(payload[key]) for key in ("medium", "weapon", "ability", "name")
    ),
)


@GameCommand.handler(
    cmd="铭刻",
    help=HelpSpec(
        category="资产",
        summary="查看铭刻入口或预览资产名称铭刻",
        usage=("铭刻", "铭刻 铭刻之羽编号 物品编号 新名称"),
        side_effect="确认后消耗唯一铭刻之羽并覆盖资产展示名",
        order=100,
    ),
)
async def inscription(
    message: str = "",
    current=Depends(current_character),
) -> None:
    """查看铭刻入口或预览资产名称铭刻。"""

    await service.inscription(message, current)


@GameCommand.handler(
    cmd="铭刻能力",
    help=HelpSpec(
        category="资产",
        summary="预览武器自带能力的铭刻名称",
        usage=("铭刻能力 铭刻之羽编号 武器编号 能力编号 新名称",),
        side_effect="确认后消耗唯一铭刻之羽并覆盖能力展示名",
        order=110,
    ),
)
async def inscription_ability(
    message: str = "",
    current=Depends(current_character),
) -> None:
    """预览武器自带能力铭刻。"""

    await service.inscription_ability(message, current)


@GameCommand.handler(
    cmd="铭刻原名",
    help=HelpSpec(
        category="角色",
        summary="查看或切换铭刻后的完整原名展示",
        usage=("铭刻原名", "铭刻原名 开启", "铭刻原名 关闭"),
        order=60,
    ),
)
async def inscription_original_name(
    message: str = "",
    current=Depends(current_character),
) -> None:
    """查看或修改铭刻完整原名展示偏好。"""

    await service.inscription_original_name(message, current)


@GameCommand.handler(cmd="inscription_confirm_asset", hidden=True)
async def confirm_asset_inscription(
    message: str = "",
    current=Depends(current_character),
) -> None:
    """处理资产铭刻确认按钮。"""

    await service.confirm_asset_inscription(message, current)


@GameCommand.handler(cmd="inscription_confirm_ability", hidden=True)
async def confirm_ability_inscription(
    message: str = "",
    current=Depends(current_character),
) -> None:
    """处理武器能力铭刻确认按钮。"""

    await service.confirm_ability_inscription(message, current)


__all__ = []
