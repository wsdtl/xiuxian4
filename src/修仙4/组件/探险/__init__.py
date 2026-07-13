"""探险与恢复的 QQ 与本地命令入口。"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from launch.adapter import Depends, manager
from launch.adapter.local import LocalCommandEvent, LocalEventHandler
from launch.adapter.local.manager import current_event as current_local_event
from launch.adapter.qq.depends import current_qq_event
from launch.adapter.qq.event import QqMessageEvent
from launch.adapter.qq.handler import QqEventHandler
from message import Action, M
from xiuxian_core.account import IdentityEvidence
from xiuxian_core.gameplay import RuleContext, Ruleset, SeededRandomSource
from src.修仙4.业务 import AdventureViolation, GameViolation
from src.修仙4.业务.adventure import ActivityView
from src.修仙4.业务.world import (
    EXPLORATION_ACTION_ID,
    HERB_ITEM_ID,
    RECOVERY_ACTION_ID,
    WORLD_SKIN_ID,
)

from src.修仙4.组件.运行时 import (
    game_application,
    local_identity_evidence,
    logical_time,
    qq_identity_evidence,
)


COMMANDS = ("探险列表", "探险", "探险状态", "结束探险", "休息", "结束休息")
router = APIRouter()


def _current_local_event() -> LocalCommandEvent:
    event = current_local_event.get()
    if event is None:
        raise RuntimeError("当前消息不是本地驱动事件")
    return event


@QqEventHandler.handler(cmd=COMMANDS, priority=500, block=True)
async def qq_adventure_command(
    client_id: str,
    cmd: str,
    message: str = "",
    qq_event: QqMessageEvent = Depends(current_qq_event),
) -> None:
    now = logical_time()
    await _dispatch(
        cmd,
        message,
        client_id,
        qq_identity_evidence(qq_event, now),
        now,
    )


@LocalEventHandler.handler(cmd=COMMANDS, priority=500, block=True)
async def local_adventure_command(
    client_id: str,
    cmd: str,
    message: str = "",
    local_event: LocalCommandEvent = Depends(_current_local_event),
) -> None:
    now = logical_time()
    await _dispatch(
        cmd,
        message,
        client_id,
        local_identity_evidence(local_event, client_id, now),
        now,
    )


async def _dispatch(
    command: str,
    argument: str,
    client_id: str,
    evidence: IdentityEvidence,
    now: datetime,
) -> None:
    application = game_application()
    try:
        entry = application.enter_world(
            evidence,
            logical_time=now,
            create_player=False,
        )
        context = _rule_context(entry.account_id, command, evidence.id, now)
        if command == "探险列表":
            reply = _locations_message()
        elif command == "探险":
            requested = argument.strip()
            expected = _name(EXPLORATION_ACTION_ID)
            if requested and requested != expected:
                raise AdventureViolation("adventure.location_unknown", "当前没有这个探险地点")
            reply = _exploration_started_message(
                application.adventure.start_exploration(entry.account_id, context=context)
            )
        elif command == "探险状态":
            reply = _status_message(
                application.adventure.activities(entry.account_id, logical_time=now)
            )
        elif command == "结束探险":
            reply = _exploration_claimed_message(
                application.adventure.claim_exploration(entry.account_id, context=context)
            )
        elif command == "休息":
            reply = _recovery_started_message(
                application.adventure.start_recovery(entry.account_id, context=context)
            )
        else:
            reply = _recovery_claimed_message(
                application.adventure.claim_recovery(entry.account_id, context=context)
            )
    except (AdventureViolation, GameViolation) as exc:
        reply = _failure_message(exc)
    await manager.send(reply, client_id)


def _locations_message():
    return (
        M.document()
        .header("探险地点")
        .section(_name(EXPLORATION_ACTION_ID), icon="explore")
        .row(("耗时", "1 分钟"), ("消耗", "精神 10"))
        .line("雾气绕竹，林中有妖影守着清露草。")
        .actions(
            (
                Action("explore", f"探险 {_name(EXPLORATION_ACTION_ID)}", f"探险 {_name(EXPLORATION_ACTION_ID)}"),
                Action("status", "探险状态", "探险状态", style="secondary"),
            )
        )
        .build()
    )


def _exploration_started_message(result):
    builder = (
        M.document()
        .header("开始探险")
        .section(_name(EXPLORATION_ACTION_ID), icon="explore")
        .row(("状态", "继续进行" if result.replayed else "已出发"), ("剩余", _duration(result.activity.remaining_seconds)))
        .row(("精神", f"{result.spirit}/{result.maximum_spirit}"), ("行动", "主行动"))
        .action(Action("status", "探险状态", "探险状态"))
    )
    return builder.build()


def _status_message(activities: tuple[ActivityView, ...]):
    builder = M.document().header("行动状态")
    if not activities:
        return (
            builder.section("当前", icon="status")
            .line("没有正在进行或待领取的行动。")
            .actions(
                (
                    Action("locations", "探险列表", "探险列表"),
                    Action("rest", "休息", "休息", style="secondary"),
                )
            )
            .build()
        )
    for activity in activities:
        name = _name(activity.definition_id)
        state = "可结束" if activity.phase == "completed" else "进行中"
        builder.section(name, icon="explore" if activity.definition_id == EXPLORATION_ACTION_ID else "recovery")
        builder.row(("状态", state), ("剩余", _duration(activity.remaining_seconds)))
        if activity.definition_id == EXPLORATION_ACTION_ID:
            builder.action(Action("claim-explore", "结束探险", "结束探险"))
        elif activity.definition_id == RECOVERY_ACTION_ID:
            builder.action(Action("claim-rest", "结束休息", "结束休息"))
    return builder.build()


def _exploration_claimed_message(result):
    return (
        M.document()
        .header("探险归来")
        .section(_name(EXPLORATION_ACTION_ID), icon="reward")
        .field("结果", f"妖影受创 {result.damage}")
        .row(("灵石", f"+{result.stone_reward}"), ("经验", f"+{result.experience_reward}"))
        .field("纳戒获得", f"{_name(HERB_ITEM_ID)} x{result.herb_reward}")
        .actions(
            (
                Action("explore", "再次探险", f"探险 {_name(EXPLORATION_ACTION_ID)}"),
                Action("rest", "休息", "休息", style="secondary"),
            )
        )
        .build()
    )


def _recovery_started_message(result):
    return (
        M.document()
        .header("开始休息")
        .section(_name(RECOVERY_ACTION_ID), icon="recovery")
        .row(("血气缺口", result.missing_health), ("精神缺口", result.missing_spirit))
        .field("剩余", _duration(result.activity.remaining_seconds))
        .action(Action("status", "探险状态", "探险状态"))
        .build()
    )


def _recovery_claimed_message(result):
    return (
        M.document()
        .header("休息结束")
        .section(_name(RECOVERY_ACTION_ID), icon="recovery")
        .row(("血气恢复", f"+{result.restored_health}"), ("精神恢复", f"+{result.restored_spirit}"))
        .row(("血气", f"{result.health}/{result.maximum_health}"), ("精神", f"{result.spirit}/{result.maximum_spirit}"))
        .actions(
            (
                Action("locations", "探险列表", "探险列表"),
                Action("status", "状态", "状态", style="secondary"),
            )
        )
        .build()
    )


def _failure_message(error):
    return (
        M.document()
        .header("行止未成")
        .section("当前不可执行", icon="notice")
        .line(error.message)
        .actions(
            (
                Action("adventure-status", "探险状态", "探险状态"),
                Action("status", "状态", "状态", style="secondary"),
            )
        )
        .build()
    )


def _rule_context(account_id: str, command: str, evidence_id: str, now: datetime) -> RuleContext:
    seed = f"{account_id}|{command}|{evidence_id}"
    return RuleContext(
        evidence_id,
        "rules.first_world.v1",
        Ruleset("ruleset.first_world"),
        now,
        SeededRandomSource(seed),
    )


def _duration(seconds: int) -> str:
    if seconds <= 0:
        return "已到时"
    minutes, remaining = divmod(seconds, 60)
    if minutes and remaining:
        return f"{minutes} 分 {remaining} 秒"
    if minutes:
        return f"{minutes} 分钟"
    return f"{remaining} 秒"


def _name(content_id: str) -> str:
    return game_application().runtime.skins.projector(WORLD_SKIN_ID).name(content_id)


__all__ = ["COMMANDS", "router"]
