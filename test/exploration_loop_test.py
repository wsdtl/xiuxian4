"""首版持续探险从内容、持久化到命令注册的闭环巡检。"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game.app import build_game_services  # noqa: E402
from game.features.exploration import exploration_battle_report_id  # noqa: E402
from game.content import build_official_content  # noqa: E402
from game.content.catalog.enemy import (  # noqa: E402
    AWARD_BOSS_TROPHY_ID,
    AWARD_DRAW_TICKET_ID,
    AWARD_ENEMY_TROPHY_ID,
    AWARD_LARGE_HEALTH_MEDICINE_ID,
    AWARD_LARGE_SPIRIT_MEDICINE_ID,
    AWARD_MEDIUM_HEALTH_MEDICINE_ID,
    AWARD_MEDIUM_SPIRIT_MEDICINE_ID,
    AWARD_RANDOM_EQUIPMENT_ID,
    AWARD_RANDOM_WEAPON_ID,
    AWARD_REGION_TROPHY_ID,
    AWARD_SMALL_HEALTH_MEDICINE_ID,
    AWARD_SMALL_SPIRIT_MEDICINE_ID,
    AWARD_WORLD_CURIO_ID,
    ENEMY_LOOT_TABLES,
)
from game.content.catalog.exploration import (  # noqa: E402
    EXPLORATION_BATCH_SECONDS,
    EXPLORATION_REGION_CATALOG,
    REGULAR_EXPLORATION_REGIONS,
    SPECIAL_EXPLORATION_REGIONS,
)
from game.content.catalog.world import (  # noqa: E402
    GREEN_CLOUD_PLAIN_ID,
    STARTING_CITY_ID,
    SUNSET_RIDGE_ID,
)
from game.content.catalog.item import TROPHY_ITEMS  # noqa: E402
from game.core.account import ExternalIdentity, IdentityEvidence  # noqa: E402
from game.core.gameplay import SeededRandomSource  # noqa: E402
from game.rules.encounter import EnemyEncounterGenerator  # noqa: E402
from game.rules.exploration import (  # noqa: E402
    EXPLORATION_AGGREGATE,
    ExplorationBatchPlanner,
    ExplorationEncounterKind,
    ExplorationState,
    ExplorationStatus,
)


TIME = datetime(2026, 7, 18, 8, 0, tzinfo=ZoneInfo("Asia/Shanghai"))


def main() -> None:
    _assert_content()
    _assert_generation()
    _assert_persisted_loop()
    print("exploration loop tests passed")


def _assert_content() -> None:
    content = build_official_content()
    space = content.catalog.world.spaces.require("world_space.primary")
    assert (space.minimum_x, space.minimum_y) == (-100, -100)
    assert (space.maximum_x, space.maximum_y) == (100, 100)
    assert len(EXPLORATION_REGION_CATALOG.definitions()) == 13
    assert len(REGULAR_EXPLORATION_REGIONS) == 10
    assert len(SPECIAL_EXPLORATION_REGIONS) == 3
    assert len(TROPHY_ITEMS) == 180
    assert all(len(region.trophy_item_ids) == 6 for region in EXPLORATION_REGION_CATALOG.definitions())
    assert content.projector.name(SPECIAL_EXPLORATION_REGIONS[0].location_id) == "万剑冢"
    assert content.projector.name(SPECIAL_EXPLORATION_REGIONS[1].location_id) == "天工遗府"
    assert content.projector.name(SPECIAL_EXPLORATION_REGIONS[2].location_id) == "归墟魔渊"
    award_ids = {
        entry.award_id
        for table in ENEMY_LOOT_TABLES
        for group in table.groups
        for entry in group.entries
        if entry.award_id is not None
    }
    assert award_ids == {
        AWARD_BOSS_TROPHY_ID,
        AWARD_DRAW_TICKET_ID,
        AWARD_ENEMY_TROPHY_ID,
        AWARD_LARGE_HEALTH_MEDICINE_ID,
        AWARD_LARGE_SPIRIT_MEDICINE_ID,
        AWARD_MEDIUM_HEALTH_MEDICINE_ID,
        AWARD_MEDIUM_SPIRIT_MEDICINE_ID,
        AWARD_RANDOM_EQUIPMENT_ID,
        AWARD_RANDOM_WEAPON_ID,
        AWARD_REGION_TROPHY_ID,
        AWARD_SMALL_HEALTH_MEDICINE_ID,
        AWARD_SMALL_SPIRIT_MEDICINE_ID,
        AWARD_WORLD_CURIO_ID,
    }


def _assert_generation() -> None:
    content = build_official_content()
    planner = ExplorationBatchPlanner(
        content.exploration_regions,
        EnemyEncounterGenerator(
            content.catalog.enemies,
            content_version=content.catalog.report.content_fingerprint,
        ),
    )
    left = planner.plan(
        session_id="exploration-test",
        batch_index=1,
        region_id=REGULAR_EXPLORATION_REGIONS[0].id,
        character_level=1,
        random=SeededRandomSource("exploration-test"),
    )
    right = planner.plan(
        session_id="exploration-test",
        batch_index=1,
        region_id=REGULAR_EXPLORATION_REGIONS[0].id,
        character_level=1,
        random=SeededRandomSource("exploration-test"),
    )
    assert left == right
    assert left.enemy_level == 1
    if left.encounter_kind is ExplorationEncounterKind.EMPTY:
        assert left.encounter is None
    else:
        assert left.encounter is not None
        assert all(
            enemy.definition_id in REGULAR_EXPLORATION_REGIONS[0].regular_enemy_ids
            or enemy.definition_id in REGULAR_EXPLORATION_REGIONS[0].boss_enemy_ids
            for enemy in left.encounter.enemies
        )


def _assert_persisted_loop() -> None:
    with TemporaryDirectory() as directory:
        path = Path(directory) / "exploration.db"
        services = build_game_services(
            database_path=path,
            identity_secret="exploration-loop-secret",
        )
        services.character_creation.workflow.id_factory = lambda kind: f"{kind}-fixed"
        services.database.initialize()
        evidence = IdentityEvidence(
            "exploration-evidence",
            ExternalIdentity(
                "platform.local",
                "exploration-test",
                "identity.user",
                "private",
                "player-a",
            ),
            (),
            "message.local",
            TIME,
        )
        created = services.create_character(evidence, requested_name="巡山客")
        assert created.status == "created" and created.receipt is not None
        character_id = created.receipt.character.id

        moved = services.exploration.move(
            character_id,
            GREEN_CLOUD_PLAIN_ID,
            logical_time=TIME,
        )
        assert moved.status == "moved"
        started = services.exploration.start(character_id, logical_time=TIME)
        assert started.status == "started" and started.state is not None
        assert started.state.next_batch_at == TIME + timedelta(seconds=EXPLORATION_BATCH_SECONDS)
        blocked = services.exploration.move(
            character_id,
            SUNSET_RIDGE_ID,
            logical_time=TIME,
        )
        assert blocked.status == "exploring"

        settled = services.exploration.settle_due(
            character_id,
            logical_time=TIME + timedelta(seconds=EXPLORATION_BATCH_SECONDS),
        )
        assert len(settled.batches) == 1
        assert settled.state is not None and settled.state.completed_batches == 1
        if settled.batches[0].plan.encounter is not None:
            reference = services.battle_reports.reference(
                exploration_battle_report_id(settled.state.session_id)
            )
            assert reference is not None
            report = services.battle_reports.load_public(
                reference.share_id,
                logical_time=TIME + timedelta(seconds=EXPLORATION_BATCH_SECONDS),
            )
            assert report is not None and report.segments
            assert report.segments[0].round_states
            assert report.segments[0].final_participants
        repeated = services.exploration.settle_due(
            character_id,
            logical_time=TIME + timedelta(seconds=EXPLORATION_BATCH_SECONDS),
        )
        assert repeated.batches == ()
        assert repeated.state == settled.state

        restarted = build_game_services(
            database_path=path,
            identity_secret="exploration-loop-secret",
        )
        restarted.database.initialize()
        loaded = restarted.exploration.load(
            character_id,
            logical_time=TIME + timedelta(seconds=EXPLORATION_BATCH_SECONDS),
        )
        assert loaded.state == settled.state
        assert loaded.batches == ()
        with restarted.database.unit_of_work(write=False) as uow:
            encoded = restarted.character_creation.snapshots.require(
                uow,
                EXPLORATION_AGGREGATE,
                character_id,
                ExplorationState,
            )
        assert encoded == settled.state

        if loaded.state.status is ExplorationStatus.RUNNING:
            stopped = restarted.exploration.stop(character_id, logical_time=TIME + timedelta(minutes=11))
            assert stopped.status == "stopped"
            assert stopped.state is not None and stopped.state.status is ExplorationStatus.STOPPED

        returned = restarted.exploration.move(
            character_id,
            STARTING_CITY_ID,
            logical_time=TIME + timedelta(minutes=12),
        )
        assert returned.status in {"moved", "already_there"}


if __name__ == "__main__":
    main()
