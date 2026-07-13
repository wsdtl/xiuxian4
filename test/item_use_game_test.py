"""第一世界清露草获得、使用、权限和重启重放组合测试。"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from xiuxian_core.account import ExternalIdentity, IdentityEvidence  # noqa: E402
from xiuxian_core.gameplay import RuleContext, Ruleset, SeededRandomSource  # noqa: E402
from xiuxian_core.gameplay.character import SPIRIT_CURRENT  # noqa: E402
from xiuxian_core.persistence import SqliteDatabase  # noqa: E402
from xiuxian_game import GameApplication, GameViolation, assemble_first_world  # noqa: E402
from xiuxian_game.world import (  # noqa: E402
    HERB_ABILITY_ID,
    HERB_ITEM_ID,
    HERB_SPIRIT_RESTORE,
)


TIME = datetime(2026, 7, 13, 21, 0, tzinfo=ZoneInfo("Asia/Shanghai"))


def main() -> None:
    with TemporaryDirectory() as directory:
        _assert_first_world_item_use(Path(directory) / "item-use-game.db")
    print("item use game tests passed")


def _context(at: datetime, trace_id: str) -> RuleContext:
    return RuleContext(
        trace_id,
        "rules.first_world.v1",
        Ruleset("ruleset.first_world"),
        at,
        SeededRandomSource(trace_id),
    )


def _identity(name: str, at: datetime) -> IdentityEvidence:
    identity = ExternalIdentity(
        "platform.local",
        "xiuxian4.item-use-test",
        "identity.local_user",
        "",
        name,
    )
    return IdentityEvidence(
        f"identity:{name}",
        identity,
        (),
        "identity.local_event",
        at,
    )


def _assert_first_world_item_use(path: Path) -> None:
    app = GameApplication(SqliteDatabase(path), assemble_first_world())
    app.initialize(logical_time=TIME)
    entered = app.enter_world(_identity("player-a", TIME), logical_time=TIME)
    account_id = entered.account_id
    other = app.enter_world(_identity("player-b", TIME), logical_time=TIME)

    assert not app.usable_items(account_id, logical_time=TIME)
    try:
        app.use_item(
            account_id,
            HERB_ITEM_ID,
            context=_context(TIME, "use-before-reward"),
        )
        raise AssertionError("没有清露草时不能使用")
    except GameViolation as exc:
        assert exc.code == "game.item_unavailable"

    app.adventure.start_exploration(
        account_id,
        context=_context(TIME, "exploration-for-herb"),
    )
    app.adventure.claim_exploration(
        account_id,
        context=_context(TIME + timedelta(minutes=1), "claim-herb"),
    )
    status = app.status(account_id)
    assert status.spirit == 50 and status.herb_quantity == 1
    usable = app.usable_items(account_id, logical_time=TIME + timedelta(minutes=1))
    assert len(usable) == 1
    assert usable[0].definition_id == HERB_ITEM_ID
    assert usable[0].ability_id == HERB_ABILITY_ID
    assert (usable[0].quantity, usable[0].available_quantity, usable[0].asset_count) == (
        1,
        1,
        1,
    )

    try:
        app.use_item(
            account_id,
            HERB_ITEM_ID,
            target_account_id=other.account_id,
            context=_context(TIME + timedelta(minutes=1), "forbidden-other-target"),
        )
        raise AssertionError("普通物品入口不能越权指定其他玩家")
    except GameViolation as exc:
        assert exc.code == "game.item_target_forbidden"
    assert app.status(account_id).herb_quantity == 1

    use_context = _context(TIME + timedelta(minutes=1, seconds=1), "use-clear-dew-herb")
    used = app.use_item(account_id, HERB_ITEM_ID, context=use_context)
    assert used.item_definition_id == HERB_ITEM_ID
    assert used.ability_id == HERB_ABILITY_ID
    assert used.consumed_quantity == 1 and not used.replayed
    assert used.resource_changes[used.target_character_id][SPIRIT_CURRENT] == HERB_SPIRIT_RESTORE
    status = app.status(account_id)
    assert status.spirit == 60 and status.herb_quantity == 0
    assert not app.usable_items(
        account_id,
        logical_time=TIME + timedelta(minutes=1, seconds=1),
    )

    restarted = GameApplication(SqliteDatabase(path), assemble_first_world())
    restarted.initialize(logical_time=TIME + timedelta(minutes=1, seconds=2))
    replayed = restarted.use_item(
        account_id,
        HERB_ITEM_ID,
        context=_context(TIME + timedelta(minutes=1, seconds=2), "use-clear-dew-herb"),
    )
    assert replayed.replayed
    assert replayed.resource_changes == used.resource_changes
    status = restarted.status(account_id)
    assert status.spirit == 60 and status.herb_quantity == 0

    restarted.begin_trial(
        account_id,
        context=_context(TIME + timedelta(minutes=2), "trial-for-full-spirit-herbs"),
    )
    restarted.claim_trial(
        account_id,
        context=_context(TIME + timedelta(minutes=2), "claim-full-spirit-herbs"),
    )
    before = restarted.status(account_id)
    assert before.spirit == 60 and before.herb_quantity == 2
    try:
        restarted.use_item(
            account_id,
            HERB_ITEM_ID,
            context=_context(TIME + timedelta(minutes=2, seconds=1), "use-at-full-spirit"),
        )
        raise AssertionError("满精神时不能浪费清露草")
    except GameViolation as exc:
        assert exc.code == "ability.target_condition_failed"
    after = restarted.status(account_id)
    assert after.spirit == before.spirit
    assert after.herb_quantity == before.herb_quantity


if __name__ == "__main__":
    main()
