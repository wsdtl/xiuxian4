"""首个修仙世界的 QQ 与本地命令入口。"""

from __future__ import annotations

from datetime import datetime
from threading import Lock
from zoneinfo import ZoneInfo

from launch import OnEvent, config
from launch.adapter import Depends, manager
from launch.adapter.local import LocalCommandEvent, LocalEventHandler
from launch.adapter.local.manager import current_event as current_local_event
from launch.adapter.qq.depends import current_qq_event
from launch.adapter.qq.event import QqMessageEvent
from launch.adapter.qq.handler import QqEventHandler
from message import Action, M
from xiuxian_core.account import (
    ExternalIdentity,
    IdentityEvidence,
    build_qq_identity_evidence,
)
from xiuxian_core.gameplay import RuleContext, Ruleset, SeededRandomSource
from xiuxian_core.persistence import SqliteDatabase
from xiuxian_game import GameApplication, GameViolation, assemble_first_world
from xiuxian_game.world import (
    CHARACTER_TEMPLATE_ID,
    CURRENCY_ID,
    HERB_ITEM_ID,
    STARTER_WEAPON_ITEM_ID,
    TRIAL_EXPERIENCE_REWARD,
    TRIAL_HERB_REWARD,
    TRIAL_STONE_REWARD,
    WORLD_SKIN_ID,
)


COMMANDS = ("开始修仙", "状态", "纳戒", "行动", "领取", "装备武器")
_application: GameApplication | None = None
_application_lock = Lock()


def game_application() -> GameApplication:
    global _application
    if _application is None:
        with _application_lock:
            if _application is None:
                _application = GameApplication(
                    SqliteDatabase(
                        config.database.path,
                        busy_timeout_ms=config.database.busy_timeout_ms,
                    ),
                    assemble_first_world(),
                )
    return _application


def set_game_application_for_test(application: GameApplication | None) -> None:
    """测试使用临时数据库替换组件组合根。"""

    global _application
    _application = application


@OnEvent.connect(priority=100)
def initialize_first_world() -> None:
    game_application().initialize(logical_time=_logical_time())


def _current_local_event() -> LocalCommandEvent:
    event = current_local_event.get()
    if event is None:
        raise RuntimeError("当前消息不是本地驱动事件")
    return event


@QqEventHandler.handler(cmd=COMMANDS, priority=500, block=True)
async def qq_first_world_command(
    client_id: str,
    cmd: str,
    qq_event: QqMessageEvent = Depends(current_qq_event),
) -> None:
    now = _logical_time()
    evidence = build_qq_identity_evidence(
        bot_app_id=config.raw.get("QQ_BOT_APP_ID", ""),
        event_id=qq_event.event_id or qq_event.message_id,
        logical_time=now,
        conversation_type="group" if qq_event.is_group else "private",
        actor_openid=qq_event.actor_openid,
        user_openid=qq_event.user_openid,
        member_openid=qq_event.member_openid,
        group_openid=qq_event.group_openid,
    )
    await _dispatch(cmd, client_id, evidence, now)


@LocalEventHandler.handler(cmd=COMMANDS, priority=500, block=True)
async def local_first_world_command(
    client_id: str,
    cmd: str,
    local_event: LocalCommandEvent = Depends(_current_local_event),
) -> None:
    now = _logical_time()
    identity = ExternalIdentity(
        "platform.local",
        "xiuxian4.local",
        "identity.local_user",
        "",
        client_id,
    )
    evidence = IdentityEvidence(
        f"local:{local_event.event_id}",
        identity,
        (),
        "identity.local_event",
        now,
    )
    await _dispatch(cmd, client_id, evidence, now)


async def _dispatch(
    command: str,
    client_id: str,
    evidence: IdentityEvidence,
    logical_time: datetime,
) -> None:
    application = game_application()
    application.initialize(logical_time=logical_time)
    try:
        entry = application.enter_world(
            evidence,
            logical_time=logical_time,
            create_player=command == "开始修仙",
        )
        context = _rule_context(entry.account_id, command, evidence.id, logical_time)
        if command == "开始修仙":
            message = _entry_message(entry.created)
        elif command == "状态":
            message = _status_message(application.status(entry.account_id))
        elif command == "纳戒":
            message = _inventory_message(application.status(entry.account_id))
        elif command == "行动":
            message = _trial_message(
                application.begin_trial(entry.account_id, context=context)
            )
        elif command == "领取":
            message = _claim_message(
                application.claim_trial(entry.account_id, context=context)
            )
        else:
            message = _equip_message(
                application.equip_starter_weapon(entry.account_id, context=context)
            )
    except GameViolation as exc:
        message = _failure_message(exc)
    await manager.send(message, client_id)


def _entry_message(created: bool):
    builder = (
        M.document()
        .header("云门初开")
        .section("入世", icon="world")
        .line("山门玉册已记下你的名字。" if created else "你已在山门玉册之中。")
        .row(("身份", _name(CHARACTER_TEMPLATE_ID)), ("境界", "Lv1"))
        .field("初始武器", _name(STARTER_WEAPON_ITEM_ID))
        .actions(
            (
                Action("status", "状态", "状态"),
                Action("trial", "山门试炼", "行动"),
                Action("equip", "装备青竹剑", "装备武器", style="secondary"),
            )
        )
    )
    return builder.build()


def _status_message(status):
    weapon = "青竹剑" if status.equipped_weapon_asset_id else "尚未装备"
    builder = (
        M.document()
        .header(_name(CHARACTER_TEMPLATE_ID))
        .section("状态", icon="status")
        .row(("境界", f"Lv{status.level}"), ("经验", status.experience))
        .row(
            ("血气", f"{status.health}/{status.maximum_health}"),
            ("灵力", f"{status.spirit}/{status.maximum_spirit}"),
        )
        .row(
            (_name(CURRENCY_ID), status.stones),
            (_name(HERB_ITEM_ID), status.herb_quantity),
        )
        .field("武器", weapon)
    )
    if status.pending_trial:
        builder.note("山门试炼已有结果待领取。")
        builder.action(Action("claim", "领取", "领取"))
    else:
        builder.action(Action("trial", "山门试炼", "行动"))
    builder.actions(
        (
            Action("inventory", "纳戒", "纳戒", style="secondary"),
            Action("equip", "装备武器", "装备武器", style="secondary"),
        )
    )
    return builder.build()


def _inventory_message(status):
    return (
        M.document()
        .header("纳戒")
        .section("资产", icon="inventory")
        .row(
            (_name(CURRENCY_ID), status.stones),
            (_name(HERB_ITEM_ID), status.herb_quantity),
        )
        .field(
            _name(STARTER_WEAPON_ITEM_ID),
            "已装备" if status.equipped_weapon_asset_id else "纳戒中",
        )
        .actions(
            (
                Action("status", "状态", "状态", style="secondary"),
                Action("equip", f"装备{_name(STARTER_WEAPON_ITEM_ID)}", "装备武器"),
            )
        )
        .build()
    )


def _trial_message(result):
    pending = result.pending
    return (
        M.document()
        .header("山门试炼")
        .section("木傀", icon="combat")
        .row(("伤害", pending.damage), ("木傀血气", pending.enemy_health))
        .field("结果", "已击破")
        .actions(
            (
                Action("claim", "领取战利品", "领取"),
                Action("status", "状态", "状态", style="secondary"),
            )
        )
        .build()
    )


def _claim_message(result):
    return (
        M.document()
        .header("山门试炼奖励")
        .section("所得", icon="reward")
        .row(
            (_name(CURRENCY_ID), f"+{TRIAL_STONE_REWARD}"),
            ("经验", f"+{TRIAL_EXPERIENCE_REWARD}"),
        )
        .field("纳戒获得", f"{_name(HERB_ITEM_ID)} x{TRIAL_HERB_REWARD}")
        .row(
            (f"当前{_name(CURRENCY_ID)}", result.stones),
            (_name(HERB_ITEM_ID), result.herb_quantity),
        )
        .actions(
            (
                Action("status", "状态", "状态"),
                Action("trial", "再次试炼", "行动", style="secondary"),
            )
        )
        .build()
    )


def _equip_message(result):
    return (
        M.document()
        .header("武器")
        .section(_name(STARTER_WEAPON_ITEM_ID), icon="weapon")
        .field("状态", "已经装备" if result.replayed else "装备成功")
        .actions(
            (
                Action("status", "状态", "状态"),
                Action("trial", "山门试炼", "行动"),
            )
        )
        .build()
    )


def _failure_message(error: GameViolation):
    builder = (
        M.document()
        .header("山门回音")
        .section("未能完成", icon="notice")
        .line(error.message)
    )
    if error.code == "game.player_not_created":
        builder.action(Action("start", "开始修仙", "开始修仙"))
    else:
        builder.action(Action("status", "状态", "状态", style="secondary"))
    return builder.build()


def _rule_context(
    account_id: str,
    command: str,
    evidence_id: str,
    logical_time: datetime,
) -> RuleContext:
    seed = f"{account_id}|{command}|{evidence_id}"
    return RuleContext(
        evidence_id,
        "rules.first_world.v1",
        Ruleset("ruleset.first_world"),
        logical_time,
        SeededRandomSource(seed),
    )


def _logical_time() -> datetime:
    return datetime.now(ZoneInfo(config.project.timezone))


def _name(content_id: str) -> str:
    return game_application().runtime.skins.projector(WORLD_SKIN_ID).name(content_id)


__all__ = [
    "COMMANDS",
    "game_application",
    "initialize_first_world",
    "set_game_application_for_test",
]
