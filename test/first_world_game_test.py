"""首个世界内容、玩家闭环、重启恢复与本地命令测试。"""

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

from src.修仙4.组件.入世 import set_game_application_for_test  # noqa: E402
from launch.adapter.local import LocalEventHandler  # noqa: E402
from message import render_local_message  # noqa: E402
from xiuxian_core.account import ExternalIdentity, IdentityEvidence  # noqa: E402
from xiuxian_core.gameplay import RuleContext, Ruleset, SeededRandomSource  # noqa: E402
from xiuxian_core.gameplay.inventory import (  # noqa: E402
    ITEM_ABILITY_COMPONENT_ID,
    ItemAbilityComponent,
)
from xiuxian_core.persistence import SqliteDatabase  # noqa: E402
from src.修仙4.业务 import (  # noqa: E402
    XIUXIAN_GAME_VERSION,
    GameApplication,
    GameViolation,
    assemble_first_world,
)
from src.修仙4.业务.world import HERB_ABILITY_ID, HERB_ITEM_ID, WORLD_SKIN_ID  # noqa: E402


TIME = datetime(2026, 7, 13, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai"))


def main() -> None:
    assert XIUXIAN_GAME_VERSION == "xiuxian-game.v1"
    _assert_world_content()
    _assert_persistent_game_loop()
    _assert_claim_crash_recovery()
    asyncio.run(_assert_local_component_loop())
    print("first world game tests passed")


def _assert_world_content() -> None:
    runtime = assemble_first_world()
    assert len(runtime.report.content_fingerprint) == 64
    assert runtime.skins.skin_ids() == (WORLD_SKIN_ID,)
    projector = runtime.skins.projector(WORLD_SKIN_ID)
    assert projector.name("item.weapon.green_bamboo_sword") == "青竹剑"
    assert projector.name("item.material.clear_dew_herb") == "清露草"
    herb_component = runtime.items.require(HERB_ITEM_ID).component(
        ITEM_ABILITY_COMPONENT_ID,
        ItemAbilityComponent,
    )
    assert herb_component.ability_id == HERB_ABILITY_ID
    assert runtime.abilities.require(HERB_ABILITY_ID)
    assert runtime.cycles.require("cycle.first_world_day")
    assert runtime.actions.require("action.mountain_gate_trial")
    exploration = runtime.actions.require("action.exploration.mist_bamboo_grove")
    assert exploration.metadata["system"] == "exploration"
    assert runtime.actions.require("action.recovery.breathing").metadata["system"] == "recovery"


def _context(trace: str, seed: int) -> RuleContext:
    return RuleContext(
        trace,
        "rules.first_world.v1",
        Ruleset("ruleset.first_world"),
        TIME,
        SeededRandomSource(seed),
    )


def _identity(external_id: str, *, kind="identity.qq_user", scope=""):
    return ExternalIdentity("platform.qq", "bot.test", kind, scope, external_id)


def _assert_persistent_game_loop() -> None:
    with TemporaryDirectory() as directory:
        path = Path(directory) / "first-world.db"
        app = GameApplication(SqliteDatabase(path), assemble_first_world())
        app.initialize(logical_time=TIME)
        user = _identity("user-1")
        member = _identity(
            "member-1",
            kind="identity.qq_group_member",
            scope="group-1",
        )
        group_evidence = IdentityEvidence(
            "qq:group-event",
            member,
            (user,),
            "identity.qq_signed_event",
            TIME,
        )
        entered = app.enter_world(group_evidence, logical_time=TIME)
        assert entered.created
        repeated = app.enter_world(group_evidence, logical_time=TIME)
        assert repeated.account_id == entered.account_id and not repeated.created
        private = app.enter_world(
            IdentityEvidence(
                "qq:private-event",
                user,
                (),
                "identity.qq_signed_event",
                TIME,
            ),
            logical_time=TIME,
            create_player=False,
        )
        assert private.account_id == entered.account_id

        status = app.status(entered.account_id)
        assert status.level == 1 and status.stones == 0
        assert status.equipped_weapon_asset_id is None

        trial = app.begin_trial(
            entered.account_id,
            context=_context("trial-1", 1),
        )
        assert trial.pending.damage == trial.pending.enemy_health
        repeated_trial = app.begin_trial(
            entered.account_id,
            context=_context("trial-repeat", 2),
        )
        assert repeated_trial.replayed and repeated_trial.pending == trial.pending
        mid_restart = GameApplication(SqliteDatabase(path), assemble_first_world())
        mid_restart.initialize(logical_time=TIME)
        assert mid_restart.status(entered.account_id).pending_trial == trial.pending

        claim = app.claim_trial(
            entered.account_id,
            context=_context("claim-1", 3),
        )
        assert (claim.stones, claim.herb_quantity, claim.experience) == (25, 2, 20)
        try:
            app.claim_trial(
                entered.account_id,
                context=_context("claim-repeat", 4),
            )
            raise AssertionError("重复领取必须被拒绝")
        except GameViolation as exc:
            assert exc.code == "game.trial_nothing_to_claim"
        assert app.status(entered.account_id).stones == 25

        equipped = app.equip_starter_weapon(
            entered.account_id,
            context=_context("equip-1", 5),
        )
        assert not equipped.replayed
        assert app.equip_starter_weapon(
            entered.account_id,
            context=_context("equip-repeat", 6),
        ).replayed

        restarted = GameApplication(SqliteDatabase(path), assemble_first_world())
        restarted.initialize(logical_time=TIME)
        restored = restarted.status(entered.account_id)
        assert restored.stones == 25 and restored.herb_quantity == 2
        assert restored.equipped_weapon_asset_id == restored.starter_weapon_asset_id


def _assert_claim_crash_recovery() -> None:
    """奖励已提交但行动未清理时，重试只能重放原奖励。"""

    with TemporaryDirectory() as directory:
        path = Path(directory) / "claim-crash.db"
        app = GameApplication(SqliteDatabase(path), assemble_first_world())
        app.initialize(logical_time=TIME)
        evidence = IdentityEvidence(
            "crash-entry",
            _identity("crash-user"),
            (),
            "identity.qq_signed_event",
            TIME,
        )
        entered = app.enter_world(evidence, logical_time=TIME)
        app.begin_trial(entered.account_id, context=_context("crash-trial", 20))
        mark_claimed = app._mark_trial_claimed

        def fail_after_reward(*_args, **_kwargs):
            raise RuntimeError("injected crash after reward settlement")

        app._mark_trial_claimed = fail_after_reward
        try:
            app.claim_trial(
                entered.account_id,
                context=_context("crash-claim", 21),
            )
            raise AssertionError("故障注入必须中断行动清理")
        except RuntimeError as exc:
            assert str(exc) == "injected crash after reward settlement"
        finally:
            app._mark_trial_claimed = mark_claimed

        interrupted = app.status(entered.account_id)
        assert interrupted.pending_trial is not None
        assert (interrupted.stones, interrupted.herb_quantity, interrupted.experience) == (25, 2, 20)

        replayed = app.claim_trial(
            entered.account_id,
            context=_context("crash-retry", 22),
        )
        assert replayed.replayed
        recovered = app.status(entered.account_id)
        assert recovered.pending_trial is None
        assert (recovered.stones, recovered.herb_quantity, recovered.experience) == (25, 2, 20)

        import sqlite3

        connection = sqlite3.connect(path)
        try:
            committed = connection.execute(
                "SELECT COUNT(*) FROM committed_transaction"
            ).fetchone()[0]
        finally:
            connection.close()
        assert committed == 1


async def _assert_local_component_loop() -> None:
    with TemporaryDirectory() as directory:
        application = GameApplication(
            SqliteDatabase(Path(directory) / "component.db"),
            assemble_first_world(),
        )
        application.initialize(logical_time=TIME)
        set_game_application_for_test(application)
        await LocalEventHandler.run()

        before = await _dispatch("状态", "local-before")
        assert "尚未开始修仙" in before
        started = await _dispatch("开始修仙", "local-start")
        assert "云门初开" in started and "青竹剑" in started
        action = await _dispatch("行动", "local-action")
        assert "山门试炼" in action and "已击破" in action
        claimed = await _dispatch("领取", "local-claim")
        assert "灵石" in claimed and "清露草 x2" in claimed
        duplicate = await _dispatch("领取", "local-claim-repeat")
        assert "当前没有待领取" in duplicate
        equipped = await _dispatch("装备武器", "local-equip")
        assert "装备成功" in equipped
        status = await _dispatch("状态", "local-status")
        assert "青竹剑" in status and "25" in status
        set_game_application_for_test(None)


async def _dispatch(command: str, event_id: str) -> str:
    result = await LocalEventHandler.dispatch(
        client_id="local-player",
        raw_message=command,
        event_id=event_id,
    )
    assert result.matched and len(result.replies) == 1
    rendered = render_local_message(result.replies[0].message)
    return rendered.content


if __name__ == "__main__":
    main()
