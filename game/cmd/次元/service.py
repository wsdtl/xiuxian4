"""角色级世界投影查询与跃迁业务。"""

from __future__ import annotations

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from game.app import CurrentCharacterResult, current_game_services
from game.rules.character import DimensionShiftResult
from launch import C, config, logger
from message import Action, DocumentMessage, M

from ..reply import send_game_reply


async def dimension_shift(
    message: str,
    current: CurrentCharacterResult,
) -> None:
    character = current.character if current.status == "ok" else None
    dimension = current.dimension if current.status == "ok" else None
    if character is None or dimension is None:
        await send_game_reply(_unavailable())
        return
    services = current_game_services()
    requested = str(message or "").strip()
    if not requested:
        await send_game_reply(_worlds_message(dimension.skin_id))
        return
    target = services.world_views.resolve(requested)
    if target is None:
        await send_game_reply(_worlds_message(dimension.skin_id, invalid=True))
        return
    try:
        result = await asyncio.to_thread(
            services.shift_character_dimension,
            character.id,
            target.skin.id,
            logical_time=_now(),
        )
    except Exception as exc:
        logger.opt(colors=True, exception=exc).error(
            C.join(C.fail("角色跃迁失败"), C.kv("character", character.id))
        )
        await send_game_reply(_unavailable())
        return
    await send_game_reply(_result_message(result))


def _worlds_message(current_skin_id: str, *, invalid: bool = False) -> DocumentMessage:
    services = current_game_services()
    current = services.world_views.require(current_skin_id)
    builder = (
        M.document()
        .section("诸天界相", icon="world")
        .field("当前世界", f"{current.skin.icon} {current.skin.name}")
    )
    if invalid:
        builder.line("没有找到这个世界")
    actions = []
    for index, view in enumerate(services.world_views.latest_views(), start=1):
        state = "当前" if view.skin.id == current.skin.id else "可跃迁"
        builder.item(index, f"{view.skin.icon} {view.skin.name} | {state}")
        if view.skin.id != current.skin.id:
            actions.append(
                Action(
                    f"dimension.shift.{view.skin.id}",
                    view.skin.name,
                    f"跃迁 {view.skin.id}",
                    behavior="send",
                )
            )
    return builder.actions(tuple(actions)).build()


def _result_message(result: DimensionShiftResult) -> DocumentMessage:
    services = current_game_services()
    if result.current is None:
        return _unavailable()
    current = services.world_view(result.current)
    if result.status == "main_action_occupied":
        return (
            M.document()
            .section("界标未稳", icon="notice")
            .line("当前正在进行主要行动，结束后才能跃迁")
            .build()
        )
    if result.status == "already_there":
        return (
            M.document()
            .section("次元跃迁", icon="world")
            .field("当前世界", f"{current.skin.icon} {current.skin.name}")
            .line("已经处于这个界相")
            .build()
        )
    if result.status == "shifted" and result.previous_skin_id is not None:
        previous = services.world_views.require(result.previous_skin_id)
        return (
            M.document()
            .section("次元跃迁", icon="world")
            .row(
                ("原世界", f"{previous.skin.icon} {previous.skin.name}"),
                ("当前世界", f"{current.skin.icon} {current.skin.name}"),
            )
            .line("化身、坐标、资产与构筑保持不变")
            .build()
        )
    return _unavailable()


def _unavailable() -> DocumentMessage:
    return (
        M.document()
        .section("次元跃迁", icon="notice")
        .line("当前没有读取到界相状态，请稍后重试")
        .build()
    )


def _now() -> datetime:
    return datetime.now(ZoneInfo(config.project.timezone))


__all__ = ["dimension_shift"]
