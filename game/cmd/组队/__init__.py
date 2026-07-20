"""队伍二级组件命令。"""

from __future__ import annotations

from launch.adapter import Depends

from ..command import GameCommand, HelpSpec
from ..dependencies import current_character
from . import service


@GameCommand.handler(
    cmd="组队",
    help=HelpSpec(
        category="战斗与社交",
        summary="查看当前队伍、成员准备状态和队伍邀请",
        usage=("组队",),
        order=40,
    ),
)
async def view(current=Depends(current_character)) -> None:
    await service.view(current)


@GameCommand.handler(
    cmd="创建队伍",
    help=HelpSpec(
        category="战斗与社交",
        summary="创建一支最多三人的轻量队伍",
        usage=("创建队伍",),
        side_effect="创建者成为队长；队伍暂不参与任何多人战斗",
        order=50,
    ),
)
async def create(current=Depends(current_character)) -> None:
    await service.create(current)


@GameCommand.handler(
    cmd="邀请组队",
    help=HelpSpec(
        category="战斗与社交",
        summary="邀请指定玩家加入当前队伍",
        usage=("邀请组队 玩家",),
        side_effect="邀请十分钟内有效，只有队长可以邀请",
        order=60,
    ),
)
async def invite(message: str = "", current=Depends(current_character)) -> None:
    await service.invite(message, current)


@GameCommand.handler(
    cmd="接受组队",
    help=HelpSpec(
        category="战斗与社交",
        summary="接受属于当前角色的队伍邀请",
        usage=("接受组队 请求编号",),
        order=70,
    ),
)
async def accept(message: str = "", current=Depends(current_character)) -> None:
    await service.accept(message, current)


@GameCommand.handler(
    cmd="拒绝组队",
    help=HelpSpec(
        category="战斗与社交",
        summary="拒绝属于当前角色的队伍邀请",
        usage=("拒绝组队 请求编号",),
        order=80,
    ),
)
async def reject(message: str = "", current=Depends(current_character)) -> None:
    await service.reject(message, current)


@GameCommand.handler(
    cmd="退出队伍",
    help=HelpSpec(
        category="战斗与社交",
        summary="退出当前队伍",
        usage=("退出队伍",),
        side_effect="队长必须先转让队长或解散队伍",
        order=90,
    ),
)
async def leave(current=Depends(current_character)) -> None:
    await service.leave(current)


@GameCommand.handler(
    cmd="请离队伍",
    help=HelpSpec(
        category="战斗与社交",
        summary="由队长移除一名队伍成员",
        usage=("请离队伍 玩家",),
        order=100,
    ),
)
async def kick(message: str = "", current=Depends(current_character)) -> None:
    await service.kick(message, current)


@GameCommand.handler(
    cmd="转让队长",
    help=HelpSpec(
        category="战斗与社交",
        summary="把队长身份交给当前队伍成员",
        usage=("转让队长 玩家",),
        order=110,
    ),
)
async def transfer(message: str = "", current=Depends(current_character)) -> None:
    await service.transfer(message, current)


@GameCommand.handler(
    cmd="解散队伍",
    help=HelpSpec(
        category="战斗与社交",
        summary="解散当前队伍",
        usage=("解散队伍",),
        side_effect="只有队长可以解散，队伍成员关系会立即结束",
        order=120,
    ),
)
async def disband(current=Depends(current_character)) -> None:
    await service.preview_disband(current)


@GameCommand.handler(cmd="party_disband_confirm", hidden=True)
async def confirm_disband(
    message: str = "",
    current=Depends(current_character),
) -> None:
    await service.confirm_disband(message, current)


@GameCommand.handler(
    cmd="准备",
    help=HelpSpec(
        category="战斗与社交",
        summary="将自己标记为已准备",
        usage=("准备",),
        order=130,
    ),
)
async def ready(current=Depends(current_character)) -> None:
    await service.set_ready(current, True)


@GameCommand.handler(
    cmd="取消准备",
    help=HelpSpec(
        category="战斗与社交",
        summary="取消自己的队伍准备状态",
        usage=("取消准备",),
        order=140,
    ),
)
async def unready(current=Depends(current_character)) -> None:
    await service.set_ready(current, False)


__all__ = []
