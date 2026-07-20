"""伙伴命令通过本地驱动器完成玩家闭环的巡检。"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game.app import build_game_services, install_game_services, restore_game_services  # noqa: E402
from game.cmd import 伙伴 as companion_component  # noqa: E402,F401
from game.cmd import 物品 as item_component  # noqa: E402,F401
from game.cmd import 装配 as loadout_component  # noqa: E402,F401
from game.cmd import 角色 as character_component  # noqa: E402,F401
from game.content import COMPANION_SANCTUARY_ITEM_ID  # noqa: E402
from game.core.gameplay import (  # noqa: E402
    GrantStack,
    InventoryState,
    InventoryTransaction,
    RuleContext,
    Ruleset,
    SeededRandomSource,
    SourceReceipt,
)
from game.core.persistence import CHARACTER_AGGREGATE, INVENTORY_AGGREGATE  # noqa: E402
from game.rules.item import asset_reference  # noqa: E402
from launch.adapter.local import LocalEventHandler, dispatch  # noqa: E402
from launch.adapter.qq import QqEventHandler  # noqa: E402


TIMEZONE = ZoneInfo("Asia/Shanghai")


def main() -> None:
    asyncio.run(_main())
    print("companion command tests passed")


async def _main() -> None:
    public_commands = (
        "伙伴",
        "伙伴出战",
        "伙伴休战",
        "伙伴秘境",
        "秘境追踪",
        "放弃秘境",
        "放生",
    )
    for command in public_commands:
        assert len(LocalEventHandler.exact_rules[command]) == 1
        assert len(QqEventHandler.exact_rules[command]) == 1

    with TemporaryDirectory() as directory:
        services = build_game_services(
            database_path=Path(directory) / "companion-command.db",
            identity_secret="companion-command-secret",
        )
        services.database.initialize()
        previous = install_game_services(services)
        try:
            await LocalEventHandler.run()
            await _dispatch("创建角色 观界客", "companion-create")
            with services.database.unit_of_work(write=False) as uow:
                row = uow.connection.execute(
                    "SELECT aggregate_id FROM aggregate_snapshot WHERE aggregate_kind = ?",
                    (CHARACTER_AGGREGATE,),
                ).fetchone()
            character = services.characters.load_character(str(row[0])) if row else None
            assert character is not None
            reference = _grant_key(services, character.id)

            nacre = await _dispatch("纳戒", "companion-nacre")
            assert "万灵引" in nacre.replies[0].message.content

            opened = await _dispatch(f"使用 {reference}", "companion-open")
            opened_message = opened.replies[0].message
            assert "万灵秘境已开启" in opened_message.content
            assert len(opened_message.actions) == 3
            assert {action.data for action in opened_message.actions} == {
                "秘境追踪 1",
                "秘境追踪 2",
                "秘境追踪 3",
            }

            sanctuary = await _dispatch("伙伴秘境", "companion-sanctuary")
            assert "等待选择" in sanctuary.replies[0].message.content

            hunted = await _dispatch("秘境追踪 1", "companion-hunt")
            hunted_message = hunted.replies[0].message
            assert "捕获成功" in hunted_message.content
            assert "查看完整战报" in hunted_message.content
            assert hunted_message.actions[0].data == "伙伴出战 C1"

            roster = await _dispatch("伙伴", "companion-roster")
            assert "C1" in roster.replies[0].message.content
            detail = await _dispatch("伙伴 C1", "companion-detail")
            assert "资质" in detail.replies[0].message.content
            assert "战斗特性" in detail.replies[0].message.content

            bound = await _dispatch("伙伴出战 C1", "companion-bind")
            assert "随当前配装出战" in bound.replies[0].message.content
            await _dispatch("配装 1", "companion-preset-one")
            transfer = await _dispatch("伙伴出战 C1", "companion-transfer-preview")
            transfer_action = transfer.replies[0].message.actions[0]
            assert transfer_action.data.startswith("companion_bind_transfer_confirm C1 ")
            transferred = await _dispatch(transfer_action.data, "companion-transfer-confirm")
            assert "随当前配装出战" in transferred.replies[0].message.content

            unbound = await _dispatch("伙伴休战", "companion-unbind")
            assert "已离开当前配装" in unbound.replies[0].message.content

            release_preview = await _dispatch("放生 C1", "companion-release-preview")
            release_action = release_preview.replies[0].message.actions[0]
            assert release_action.data.startswith("companion_release_confirm C1 ")
            released = await _dispatch(release_action.data, "companion-release-confirm")
            assert "已离开名册" in released.replies[0].message.content
            final_roster = services.companions.view(character.id, logical_time=_now()).roster
            assert not final_roster.instances
            assert final_roster.captured_definition_ids
        finally:
            restore_game_services(previous)


async def _dispatch(command: str, event_id: str):
    return await dispatch(
        client_id="companion-player",
        raw_message=command,
        sender_name="观界客",
        event_id=event_id,
    )


def _grant_key(services, character_id: str) -> str:
    with services.database.unit_of_work() as uow:
        inventory = services.companions.snapshots.require(
            uow,
            INVENTORY_AGGREGATE,
            character_id,
            InventoryState,
        )
        container = next(
            value for value in inventory.containers.values() if value.kind == "container.special"
        )
        context = RuleContext(
            "grant-companion-command-key",
            "test.companion.command.v1",
            Ruleset("ruleset.test.companion.command"),
            _now(),
            SeededRandomSource("grant-companion-command-key"),
        )
        outcome = services.inventory_engine.execute(
            InventoryTransaction(
                "grant-companion-command-key",
                character_id,
                "test.grant",
                (
                    GrantStack(
                        "stack:companion-command-key",
                        COMPANION_SANCTUARY_ITEM_ID,
                        container.id,
                        1,
                        SourceReceipt(
                            "grant-companion-command-key",
                            "source.test",
                            "companion-key",
                            _now(),
                        ),
                    ),
                ),
            ),
            state=inventory,
            context=context,
        )
        assert outcome.ok and outcome.value is not None, outcome.failure
        next_inventory = outcome.value.state
        services.companions.snapshots.update(
            uow,
            INVENTORY_AGGREGATE,
            character_id,
            inventory,
            next_inventory,
            _now(),
        )
        uow.commit()
    return asset_reference(
        next_inventory,
        next_inventory.stacks["stack:companion-command-key"],
        services.content.catalog.items,
    )


def _now() -> datetime:
    return datetime.now(TIMEZONE)


if __name__ == "__main__":
    main()
