"""正式游戏命令可复用的公共依赖。"""

from __future__ import annotations

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from game.app import (
    CharacterOverviewResult,
    CurrentCharacterResult,
    current_game_services,
    message_identity_evidence,
)
from game.core.account import IdentityEvidence
from launch import C, config, logger
from launch.adapter import Depends, MessageIdentity


def current_identity_evidence(message_identity: MessageIdentity) -> IdentityEvidence:
    """把当前驱动器已经规整的身份转换成游戏身份凭据。"""

    return message_identity_evidence(
        message_identity,
        logical_time=datetime.now(ZoneInfo(config.project.timezone)),
    )


async def current_character(
    evidence: IdentityEvidence = Depends(current_identity_evidence),
) -> CurrentCharacterResult:
    """读取当前角色；单条消息内由依赖注入器自动缓存。"""

    try:
        return await asyncio.to_thread(
            current_game_services().load_current_character,
            evidence,
        )
    except Exception as exc:
        logger.opt(colors=True, exception=exc).error(
            C.join(C.fail("当前角色依赖执行失败"), C.kv("evidence", evidence.id))
        )
        return CurrentCharacterResult("failed")


async def current_character_overview(
    current: CurrentCharacterResult = Depends(current_character),
) -> CharacterOverviewResult:
    """按需读取角色详情，不让普通角色依赖连带读取全部领域。"""

    if current.status != "ok" or current.character is None:
        return CharacterOverviewResult(current.status)
    try:
        return await asyncio.to_thread(
            current_game_services().load_character_overview,
            current.character,
        )
    except Exception as exc:
        logger.opt(colors=True, exception=exc).error(
            C.join(
                C.fail("角色详情依赖执行失败"),
                C.kv("character", current.character.id),
            )
        )
        return CharacterOverviewResult("failed")


__all__ = [
    "current_character",
    "current_character_overview",
    "current_identity_evidence",
]
