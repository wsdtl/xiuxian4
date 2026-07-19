"""探险命令通过本地驱动器的最终回复巡检。"""

from __future__ import annotations

import asyncio
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
from game.cmd import 探险 as exploration_component  # noqa: E402,F401
from game.cmd import 回收 as recycle_component  # noqa: E402,F401
from game.cmd import 角色 as character_component  # noqa: E402,F401
from launch.adapter.local import LocalEventHandler, dispatch  # noqa: E402
from launch.adapter.qq import QqEventHandler  # noqa: E402


def main() -> None:
    asyncio.run(_main())
    print("exploration command tests passed")


async def _main() -> None:
    for command in (
        "探险",
        "前往",
        "开始探险",
        "停止探险",
        "探险总结",
        "回收战利品",
    ):
        assert len(LocalEventHandler.exact_rules[command]) == 1
        assert len(QqEventHandler.exact_rules[command]) == 1

    with TemporaryDirectory() as directory:
        services = build_game_services(
            database_path=Path(directory) / "exploration-command.db",
            identity_secret="exploration-command-secret",
        )
        services.database.initialize()
        previous = install_game_services(services)
        try:
            await LocalEventHandler.run()
            await dispatch(
                client_id="exploration-player",
                raw_message="创建角色 巡山客",
                sender_name="巡山客",
                event_id="exploration-create",
            )
            listing = await dispatch(
                client_id="exploration-player",
                raw_message="探险",
                sender_name="巡山客",
                event_id="exploration-list",
            )
            content = listing.replies[0].message.content
            assert listing.replies[0].message.kind == "markdown"
            assert "常规区域" in content and "特殊区域" in content
            assert "青云原" in content and "万剑冢" in content

            moved = await dispatch(
                client_id="exploration-player",
                raw_message="前往 青云原",
                sender_name="巡山客",
                event_id="exploration-move",
            )
            assert "抵达: _青云原_" in moved.replies[0].message.content

            started = await dispatch(
                client_id="exploration-player",
                raw_message="开始探险",
                sender_name="巡山客",
                event_id="exploration-start",
            )
            assert "首次结算" in started.replies[0].message.content
            assert started.replies[0].message.actions[0].data == "停止探险"

            summary = await dispatch(
                client_id="exploration-player",
                raw_message="探险总结",
                sender_name="巡山客",
                event_id="exploration-summary",
            )
            assert "状态: _进行中_" in summary.replies[0].message.content
            assert summary.replies[0].message.actions[0].data == "回收战利品"

            empty_sale = await dispatch(
                client_id="exploration-player",
                raw_message="回收战利品",
                sender_name="巡山客",
                event_id="exploration-empty-sale",
            )
            assert "没有可回收的战利品" in empty_sale.replies[0].message.content
        finally:
            restore_game_services(previous)


if __name__ == "__main__":
    main()
