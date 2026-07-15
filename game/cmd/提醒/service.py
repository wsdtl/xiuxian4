"""全局提醒组件的只读查询与消息正文。"""

from __future__ import annotations

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from game.app import (
    CurrentCharacterResult,
    PlayerReminderDetailsResult,
    current_game_services,
)
from game.core.gameplay import ActionRecord, NotificationEntry
from launch import C, config, logger
from message import DocumentMessage, M
from message.schema import FieldSeparator

from ..reply import send_game_reply
from ..reply_intents import reply_intents


async def view_notifications(current: CurrentCharacterResult) -> None:
    """读取并展示未读通知，不自动标记已读。"""

    result = await _load_details(current)
    await send_game_reply(_notifications_message(result))


async def view_pending_actions(current: CurrentCharacterResult) -> None:
    """读取并展示已经完成但尚未领取的行动。"""

    result = await _load_details(current)
    await send_game_reply(_pending_actions_message(result))


async def _load_details(
    current: CurrentCharacterResult,
) -> PlayerReminderDetailsResult:
    if current.status != "ok" or current.character is None:
        return PlayerReminderDetailsResult(current.status)
    try:
        return await asyncio.to_thread(
            current_game_services().load_player_reminder_details,
            current.character,
            logical_time=_now(),
        )
    except Exception as exc:
        logger.opt(colors=True, exception=exc).error(
            C.join(
                C.fail("玩家提醒明细执行失败"),
                C.kv("character", current.character.id),
            )
        )
        return PlayerReminderDetailsResult("failed")


def _notifications_message(result: PlayerReminderDetailsResult) -> DocumentMessage:
    if result.status != "ok" or result.details is None:
        return _unavailable_message("未读通知")
    details = result.details
    builder = M.document().section("未读通知", icon="notice")
    if not details.notifications:
        return builder.line("暂无未读通知").build()
    builder.field("数量", len(details.notifications))
    for index, entry in enumerate(details.notifications, start=1):
        parts = [f"[{index}] {_notification_title(entry)}", FieldSeparator(), M.em(_time(entry.created_at))]
        if entry.action is not None and entry.action.kind_id in reply_intents:
            parts.extend(
                (
                    FieldSeparator(),
                    reply_intents.link(
                        "处理",
                        entry.action.kind_id,
                        entry.action.payload,
                    ),
                )
            )
        builder.line(*parts)
    return builder.build()


def _pending_actions_message(result: PlayerReminderDetailsResult) -> DocumentMessage:
    if result.status != "ok" or result.details is None:
        return _unavailable_message("待领取")
    details = result.details
    builder = M.document().section("待领取", icon="reward")
    if not details.pending_actions:
        return builder.line("暂无待领取行动").build()
    builder.field("数量", len(details.pending_actions))
    for index, record in enumerate(details.pending_actions, start=1):
        builder.line(
            f"[{index}] {_action_title(record)}",
            FieldSeparator(),
            M.em(_time(record.completes_at)),
        )
    return builder.build()


def _notification_title(entry: NotificationEntry) -> str:
    return _projected_name(entry.kind_id, "系统通知")


def _action_title(record: ActionRecord) -> str:
    return _projected_name(record.definition_id, "待领取行动")


def _projected_name(definition_id: str, fallback: str) -> str:
    try:
        return current_game_services().content.projector.name(definition_id)
    except KeyError:
        return fallback


def _unavailable_message(title: str) -> DocumentMessage:
    return (
        M.document()
        .section(title, icon="notice")
        .line("当前没有读取到提醒状态，请稍后重试")
        .build()
    )


def _time(value: datetime) -> str:
    return value.astimezone(ZoneInfo(config.project.timezone)).strftime("%m-%d %H:%M")


def _now() -> datetime:
    return datetime.now(ZoneInfo(config.project.timezone))


__all__ = ["view_notifications", "view_pending_actions"]
