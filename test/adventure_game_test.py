"""探险消耗、异步到期、奖励与休息恢复闭环测试。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from components.adventure import COMMANDS as ADVENTURE_COMMANDS  # noqa: E402
from components.game_runtime import set_game_application_for_test  # noqa: E402
from launch.adapter.local import LocalEventHandler  # noqa: E402
from launch.adapter.qq.render import render_qq_message  # noqa: E402
from message import render_local_message  # noqa: E402
from xiuxian_core.account import ExternalIdentity, IdentityEvidence  # noqa: E402
from xiuxian_core.gameplay import RuleContext, Ruleset, SeededRandomSource  # noqa: E402
from xiuxian_core.persistence import SqliteDatabase  # noqa: E402
from xiuxian_game import AdventureViolation, GameApplication, assemble_first_world  # noqa: E402


TIME = datetime(2026, 7, 13, 14, 0, tzinfo=ZoneInfo("Asia/Shanghai"))


def main() -> None:
    with TemporaryDirectory() as directory:
        path = Path(directory) / "adventure.db"
        app = GameApplication(SqliteDatabase(path), assemble_first_world())
        app.initialize(logical_time=TIME)
        identity = ExternalIdentity(
            "platform.local",
            "xiuxian4.test",
            "identity.local_user",
            "",
            "adventurer",
        )
        entered = app.enter_world(
            IdentityEvidence("entry", identity, (), "identity.local_event", TIME),
            logical_time=TIME,
        )
        account_id = entered.account_id

        started = app.adventure.start_exploration(
            account_id,
            context=_context(TIME, "explore-start"),
        )
        assert started.spirit == 50 and started.maximum_spirit == 60
        assert started.activity.remaining_seconds == 60
        repeated = app.adventure.start_exploration(
            account_id,
            context=_context(TIME + timedelta(seconds=1), "explore-repeat"),
        )
        assert repeated.replayed and repeated.activity.action_id == started.activity.action_id
        assert app.status(account_id).spirit == 50
        restarted_pending = GameApplication(SqliteDatabase(path), assemble_first_world())
        pending = restarted_pending.adventure.activities(
            account_id,
            logical_time=TIME + timedelta(seconds=30),
        )
        assert len(pending) == 1 and pending[0].remaining_seconds == 30

        try:
            app.adventure.claim_exploration(
                account_id,
                context=_context(TIME + timedelta(seconds=59), "explore-early"),
            )
            raise AssertionError("探险到期前不能领取")
        except AdventureViolation as exc:
            assert exc.code == "adventure.action_not_due"

        claimed = app.adventure.claim_exploration(
            account_id,
            context=_context(TIME + timedelta(seconds=60), "explore-claim"),
        )
        assert claimed.damage == 12
        assert (
            claimed.stone_reward,
            claimed.herb_reward,
            claimed.experience_reward,
        ) == (18, 1, 15)
        assert not app.adventure.activities(
            account_id,
            logical_time=TIME + timedelta(seconds=60),
        )

        recovery = app.adventure.start_recovery(
            account_id,
            context=_context(TIME + timedelta(seconds=61), "recovery-start"),
        )
        assert recovery.missing_health == 0 and recovery.missing_spirit == 10
        try:
            app.adventure.claim_recovery(
                account_id,
                context=_context(TIME + timedelta(seconds=120), "recovery-early"),
            )
            raise AssertionError("休息到期前不能结束")
        except AdventureViolation as exc:
            assert exc.code == "adventure.action_not_due"
        recovered = app.adventure.claim_recovery(
            account_id,
            context=_context(TIME + timedelta(seconds=121), "recovery-claim"),
        )
        assert recovered.restored_spirit == 10 and recovered.spirit == 60
        assert not app.adventure.activities(
            account_id,
            logical_time=TIME + timedelta(seconds=121),
        )

        try:
            app.adventure.start_recovery(
                account_id,
                context=_context(TIME + timedelta(seconds=122), "recovery-full"),
            )
            raise AssertionError("满状态不能开始休息")
        except AdventureViolation as exc:
            assert exc.code == "adventure.recovery_not_needed"

        app.adventure.start_exploration(
            account_id,
            context=_context(TIME + timedelta(seconds=123), "explore-second-start"),
        )
        second_claim = app.adventure.claim_exploration(
            account_id,
            context=_context(TIME + timedelta(seconds=183), "explore-second-claim"),
        )
        assert (
            second_claim.stone_reward,
            second_claim.herb_reward,
            second_claim.experience_reward,
        ) == (18, 1, 15)

        restarted = GameApplication(SqliteDatabase(path), assemble_first_world())
        restored = restarted.status(account_id)
        assert (restored.spirit, restored.stones, restored.herb_quantity, restored.experience) == (
            50,
            36,
            2,
            30,
        )
        connection = sqlite3.connect(path)
        try:
            assert connection.execute(
                "SELECT COUNT(*) FROM committed_transaction"
            ).fetchone()[0] == 2
        finally:
            connection.close()
    _assert_exploration_claim_crash_recovery()
    asyncio.run(_assert_local_component())
    print("adventure game tests passed")


def _context(at: datetime, trace_id: str) -> RuleContext:
    return RuleContext(
        trace_id,
        "rules.first_world.v1",
        Ruleset("ruleset.first_world"),
        at,
        SeededRandomSource(trace_id),
    )


def _assert_exploration_claim_crash_recovery() -> None:
    with TemporaryDirectory() as directory:
        path = Path(directory) / "adventure-crash.db"
        app = GameApplication(SqliteDatabase(path), assemble_first_world())
        app.initialize(logical_time=TIME)
        identity = ExternalIdentity(
            "platform.local",
            "xiuxian4.test",
            "identity.local_user",
            "",
            "crash-adventurer",
        )
        entered = app.enter_world(
            IdentityEvidence("crash-entry", identity, (), "identity.local_event", TIME),
            logical_time=TIME,
        )
        app.adventure.start_exploration(
            entered.account_id,
            context=_context(TIME, "crash-start"),
        )
        claim_action = app.adventure._claim_action

        def fail_after_reward(*_args, **_kwargs):
            raise RuntimeError("injected crash after exploration reward")

        app.adventure._claim_action = fail_after_reward
        try:
            app.adventure.claim_exploration(
                entered.account_id,
                context=_context(TIME + timedelta(seconds=60), "crash-claim"),
            )
            raise AssertionError("故障注入必须中断探险行动清理")
        except RuntimeError as exc:
            assert str(exc) == "injected crash after exploration reward"
        finally:
            app.adventure._claim_action = claim_action
        interrupted = app.status(entered.account_id)
        assert (interrupted.stones, interrupted.herb_quantity, interrupted.experience) == (18, 1, 15)
        pending = app.adventure.activities(
            entered.account_id,
            logical_time=TIME + timedelta(seconds=60),
        )
        assert len(pending) == 1 and pending[0].phase == "completed"
        replayed = app.adventure.claim_exploration(
            entered.account_id,
            context=_context(TIME + timedelta(seconds=61), "crash-retry"),
        )
        assert replayed.replayed
        recovered = app.status(entered.account_id)
        assert (recovered.stones, recovered.herb_quantity, recovered.experience) == (18, 1, 15)
        assert not app.adventure.activities(
            entered.account_id,
            logical_time=TIME + timedelta(seconds=61),
        )


async def _assert_local_component() -> None:
    with TemporaryDirectory() as directory:
        path = Path(directory) / "adventure-component.db"
        app = GameApplication(SqliteDatabase(path), assemble_first_world())
        app.initialize(logical_time=TIME)
        identity = ExternalIdentity(
            "platform.local",
            "xiuxian4.local",
            "identity.local_user",
            "",
            "component-adventurer",
        )
        app.enter_world(
            IdentityEvidence("component-entry", identity, (), "identity.local_event", TIME),
            logical_time=TIME,
        )
        set_game_application_for_test(app)
        await LocalEventHandler.run()
        assert set(ADVENTURE_COMMANDS).issubset(LocalEventHandler.exact_rules)
        locations = await _dispatch_local("探险列表", "component-locations")
        assert "雾竹林" in locations and "精神 10" in locations
        started = await _dispatch_local("探险 雾竹林", "component-start")
        assert "开始探险" in started and "已出发" in started
        status = await _dispatch_local("探险状态", "component-status")
        assert "雾竹林" in status and "进行中" in status
        early = await _dispatch_local("结束探险", "component-early")
        assert "探险尚未结束" in early
        set_game_application_for_test(None)


async def _dispatch_local(command: str, event_id: str) -> str:
    result = await LocalEventHandler.dispatch(
        client_id="component-adventurer",
        raw_message=command,
        event_id=event_id,
    )
    assert result.matched and len(result.replies) == 1
    rendered_qq = render_qq_message(result.replies[0].message)
    assert rendered_qq.kind == "markdown"
    return render_local_message(result.replies[0].message).content


if __name__ == "__main__":
    main()
