"""所有正式命令共享的无业务语义工具。"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from game.app import CurrentCharacterResult
from launch import config


def current_character_value(current: CurrentCharacterResult):
    """从角色依赖结果中取出角色；失败和未建档统一返回 None。"""

    return current.character if current.status == "ok" else None


def command_time() -> datetime:
    """返回命令层统一使用的带时区逻辑时间。"""

    return datetime.now(ZoneInfo(config.project.timezone))


__all__ = ["command_time", "current_character_value"]
