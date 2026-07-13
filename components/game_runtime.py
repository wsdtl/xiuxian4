"""修仙业务组件共享的组合根、逻辑时间与身份证据适配。"""

from __future__ import annotations

from datetime import datetime
from threading import Lock
from zoneinfo import ZoneInfo

from launch import config
from launch.adapter.local import LocalCommandEvent
from launch.adapter.qq.event import QqMessageEvent
from xiuxian_core.account import (
    ExternalIdentity,
    IdentityEvidence,
    build_qq_identity_evidence,
)
from xiuxian_core.persistence import SqliteDatabase
from xiuxian_game import GameApplication, assemble_first_world


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
    """测试使用临时数据库替换业务组合根。"""

    global _application
    _application = application


def logical_time() -> datetime:
    return datetime.now(ZoneInfo(config.project.timezone))


def qq_identity_evidence(event: QqMessageEvent, now: datetime) -> IdentityEvidence:
    return build_qq_identity_evidence(
        bot_app_id=config.raw.get("QQ_BOT_APP_ID", ""),
        event_id=event.event_id or event.message_id,
        logical_time=now,
        conversation_type="group" if event.is_group else "private",
        actor_openid=event.actor_openid,
        user_openid=event.user_openid,
        member_openid=event.member_openid,
        group_openid=event.group_openid,
    )


def local_identity_evidence(
    event: LocalCommandEvent,
    client_id: str,
    now: datetime,
) -> IdentityEvidence:
    identity = ExternalIdentity(
        "platform.local",
        "xiuxian4.local",
        "identity.local_user",
        "",
        client_id,
    )
    return IdentityEvidence(
        f"local:{event.event_id}",
        identity,
        (),
        "identity.local_event",
        now,
    )


__all__ = [
    "game_application",
    "local_identity_evidence",
    "logical_time",
    "qq_identity_evidence",
    "set_game_application_for_test",
]
