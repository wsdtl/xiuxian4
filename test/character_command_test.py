"""创建角色命令的本地驱动端到端测试。"""

from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
import sys
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game.app import (  # noqa: E402
    build_game_services,
    install_game_services,
    restore_game_services,
)
from game.core.persistence import CHARACTER_AGGREGATE  # noqa: E402
from game.cmd import 角色 as character_component  # noqa: E402
from game.cmd.角色 import COMMAND  # noqa: E402
from launch.adapter.local import LocalEventHandler, dispatch  # noqa: E402
from launch.adapter.qq import QqEventHandler  # noqa: E402
from message import RenderedMessage  # noqa: E402


def main() -> None:
    asyncio.run(_main())
    print("character command tests passed")


async def _main() -> None:
    assert tuple(inspect.signature(character_component.create_character_command).parameters) == (
        "message",
    )
    assert len(LocalEventHandler.exact_rules[COMMAND]) == 1
    assert len(QqEventHandler.exact_rules[COMMAND]) == 1
    with TemporaryDirectory() as directory:
        services = build_game_services(
            database_path=Path(directory) / "character-command.db",
            identity_secret="character-command-test-secret",
        )
        services.database.initialize()
        previous = install_game_services(services)
        try:
            await LocalEventHandler.run()

            created = await dispatch(
                client_id="local-user-a",
                raw_message=f"{COMMAND} 云舟客",
                sender_name="平台昵称甲",
                event_id="local-create-a",
            )
            content = _content(created)
            assert "云舟客 Lv1" in content
            assert "人族" in content and "凡体" in content
            assert "仙京制式剑" in content
            assert "小还丹" in content and "小回灵丹" in content
            assert "太玄仙城" in content
            assert _character_count(services) == 1

            replayed = await dispatch(
                client_id="local-user-a",
                raw_message=f"{COMMAND} 云舟客",
                sender_name="平台昵称甲",
                event_id="local-create-a",
            )
            assert "云舟客 Lv1" in _content(replayed)
            assert _character_count(services) == 1

            existing = await dispatch(
                client_id="local-user-a",
                raw_message=f"{COMMAND} 第二角色",
                sender_name="平台昵称甲",
                event_id="local-create-a-again",
            )
            assert "角色已存在" in _content(existing)
            assert _character_count(services) == 1

            nickname = await dispatch(
                client_id="local-user-b",
                raw_message=COMMAND,
                sender_name="平台昵称乙",
                event_id="local-create-b",
            )
            assert "平台昵称乙 Lv1" in _content(nickname)
            assert _character_count(services) == 2

            missing = await dispatch(
                client_id="local-user-c",
                raw_message=COMMAND,
                sender_name="",
                event_id="local-create-c",
            )
            missing_content = _content(missing)
            assert "需要角色名" in missing_content
            assert "创建角色 名称" in missing_content
            assert missing.replies[0].message.actions[0].behavior == "fill"
            assert _character_count(services) == 2
        finally:
            restore_game_services(previous)


def _content(result) -> str:
    assert result.matched and result.matched_count == 1
    assert len(result.replies) == 1
    message = result.replies[0].message
    assert isinstance(message, RenderedMessage)
    assert message.kind == "markdown"
    return message.content


def _character_count(services) -> int:
    with services.database.unit_of_work(write=False) as uow:
        row = uow.connection.execute(
            "SELECT COUNT(*) FROM aggregate_snapshot WHERE aggregate_kind = ?",
            (CHARACTER_AGGREGATE,),
        ).fetchone()
        return int(row[0])


if __name__ == "__main__":
    main()
