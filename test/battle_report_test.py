"""统一战报压缩、幂等、公开读取和保留期测试。"""

from __future__ import annotations

import ast
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from importlib import import_module
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory

from fastapi import FastAPI
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game.core.gameplay import ExecutionPhase, HEALTH_CURRENT, RuleEvent  # noqa: E402
from game.core.persistence import BattleReportStore, SqliteDatabase  # noqa: E402
from game.app import build_game_services, install_game_services, restore_game_services  # noqa: E402
from game.cmd import router as game_router  # noqa: E402
from game.content.world_skins.cultivation import (  # noqa: E402
    CULTIVATION_SKIN_ID,
    CULTIVATION_SKIN_VERSION,
)
from game.features.battle_report import BattleReportService  # noqa: E402
from game.rules.battle_report import (  # noqa: E402
    BattleReportDraft,
    BattleReportFrameDraft,
    BattleReportParticipantDraft,
    BattleReportRoundStateDraft,
    BattleReportSegmentDraft,
    BattleReportSummary,
    BattleReportTurnStateDraft,
    BattleReportTransitionDraft,
    StoredBattleEvent,
    KNOWN_BATTLE_EVENT_KINDS,
)


_event_text = import_module("game.cmd.战报.site")._event_text


NOW = datetime(2026, 7, 19, 12, tzinfo=timezone.utc)


def main() -> None:
    _assert_all_current_events_are_rendered()
    with TemporaryDirectory() as directory:
        database = SqliteDatabase(Path(directory) / "battle-report.db")
        database.initialize()
        service = BattleReportService(database, BattleReportStore(database))
        first = _draft("segment-1", "第一战", NOW)
        reference = service.capture(first)
        replayed = service.capture(first)
        assert replayed == reference

        second = replace(
            _draft("segment-2", "第二战", NOW + timedelta(minutes=10)),
            summary=BattleReportSummary("探险战报", "2胜 0负", ("完成批次: 2",)),
        )
        second_reference = service.capture(second)
        assert second_reference == reference

        full = service.load_public(reference.share_id, logical_time=NOW + timedelta(days=6))
        assert full is not None and full.detail_available
        assert [item.segment_id for item in full.segments] == ["segment-1", "segment-2"]
        assert full.summary.outcome == "2胜 0负"
        assert full.segments[0].participants[0].key == "p0"
        assert full.segments[0].events[1].source == "p0"
        assert full.segments[0].participants[0].abilities == ("ability.test",)
        assert full.segments[0].participants[0].effects == {
            "effect.weapon.shared_charge": 2,
            "effect.weapon.shared_mark": 1,
        }
        assert full.segments[0].final_participants[0].health == 750
        assert len(full.segments[0].round_states) == 1
        assert len(full.segments[0].turn_states) == 1
        assert full.segments[0].round_states[0].participants[0].cooldowns == {
            "ability.test": 2
        }
        transitions = full.segments[0].transitions
        assert len(transitions) == 2
        assert transitions[0].before is None
        assert transitions[0].after.status == "active"
        assert transitions[1].actor_key == "p0"
        assert transitions[1].ability_id == "ability.test"
        assert transitions[1].decision_rule_id == "ai.test.rule"
        assert transitions[1].requested_selector_id == "target.enemy"
        assert transitions[1].requested_target_keys == ("p1",)
        assert transitions[1].resolved_target_keys == ("p1",)
        assert transitions[1].before.revision == 1
        assert transitions[1].after.status == "finished"
        assert transitions[1].after.inactive_keys == ("p1",)

        services = build_game_services(
            database_path=database.path,
            identity_secret="battle-report-test-secret",
        )
        previous = install_game_services(services)
        try:
            app = FastAPI()
            app.include_router(game_router)
            with TestClient(app) as client:
                response = client.get(f"/battle/{reference.share_id}")
                assert response.status_code == 200
                assert "第一战" in response.text and "受到 100 点伤害" in response.text
                assert "初始效果" in response.text and "初始战斗快照" in response.text
                assert "战斗结束状态" in response.text and "结束效果" in response.text
                assert "动作前完整状态" in response.text and "动作后完整状态" in response.text
                assert "实际目标 山魈" in response.text
                assert "正面:" in response.text and "负面:" in response.text
                assert "character-private-id" not in response.text
                assert "enemy-private-id" not in response.text
                assert client.get("/battle/not-found").status_code == 404
        finally:
            restore_game_services(previous)

        connection = sqlite3.connect(database.path)
        row = connection.execute(
            "SELECT uncompressed_bytes, compressed_bytes FROM battle_report"
        ).fetchone()
        count = connection.execute("SELECT COUNT(*) FROM battle_report_segment").fetchone()[0]
        connection.close()
        assert count == 2
        assert row[0] > 0 and row[1] > 0 and row[1] < row[0]

        summary = service.load_public(
            reference.share_id,
            logical_time=NOW + timedelta(days=8),
        )
        assert summary is not None and not summary.detail_available
        assert summary.segments == ()
        removed_details, removed_reports = service.cleanup(
            logical_time=NOW + timedelta(days=8)
        )
        assert removed_details == 2 and removed_reports == 0
        assert service.cleanup(logical_time=NOW + timedelta(days=8)) == (0, 0)

        assert service.load_public(
            reference.share_id,
            logical_time=NOW + timedelta(days=31),
        ) is None
        assert service.cleanup(logical_time=NOW + timedelta(days=31)) == (0, 1)

    print("battle report tests passed")


def _assert_all_current_events_are_rendered() -> None:
    paths = (ROOT / "game").rglob("*.py")
    discovered: set[str] = {"combat.damage.dealt", "combat.damage.prevented"}
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "EffectFact"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                _add_battle_event(discovered, node.args[0].value)
            if isinstance(node.func, ast.Attribute) and node.func.attr == "from_context":
                for keyword in node.keywords:
                    if (
                        keyword.arg == "kind"
                        and isinstance(keyword.value, ast.Constant)
                        and isinstance(keyword.value.value, str)
                    ):
                        _add_battle_event(discovered, keyword.value.value)
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "_effect_mutation_event"
                and len(node.args) > 4
                and isinstance(node.args[4], ast.Constant)
                and isinstance(node.args[4].value, str)
            ):
                _add_battle_event(discovered, node.args[4].value)
    assert discovered == KNOWN_BATTLE_EVENT_KINDS
    view = _FallbackView()
    for kind in sorted(KNOWN_BATTLE_EVENT_KINDS):
        text = _event_text(
            StoredBattleEvent(
                kind,
                "p0",
                "p1",
                "effect.test",
                NOW,
                {},
            ),
            {"p0": "甲", "p1": "乙"},
            view,
        )
        assert text and "未命名战斗事件" not in text, kind


def _add_battle_event(discovered: set[str], value: str) -> None:
    if value.startswith(("ability.", "combat.", "effect.", "resource.", "trigger.")):
        discovered.add(value)


class _FallbackProjector:
    @staticmethod
    def name(_content_id: str) -> str:
        raise KeyError


class _FallbackView:
    projector = _FallbackProjector()


def _draft(segment_id: str, title: str, logical_time: datetime) -> BattleReportDraft:
    events = (
        RuleEvent(
            kind="combat.round.started",
            source_id="battle-private-id",
            target_id="character-private-id",
            subject_id="combat.round",
            trace_id="private-trace-id",
            rule_version="rule.test.v1",
            ruleset_id="ruleset.standard",
            logical_time=logical_time,
            values={"round": 1},
            phase=ExecutionPhase.PREPARE,
        ),
        RuleEvent(
            kind="combat.turn.started",
            source_id="character-private-id",
            target_id="character-private-id",
            subject_id="combat.turn",
            trace_id="private-trace-id",
            rule_version="rule.test.v1",
            ruleset_id="ruleset.standard",
            logical_time=logical_time,
            values={"round": 1, "turn": 1},
            phase=ExecutionPhase.PREPARE,
        ),
        *tuple(
        RuleEvent(
            kind="resource.changed",
            source_id="character-private-id",
            target_id="enemy-private-id",
            subject_id=HEALTH_CURRENT,
            trace_id="private-trace-id",
            rule_version="rule.test.v1",
            ruleset_id="ruleset.standard",
            logical_time=logical_time,
            values={"delta": -100 - index, "current": 900 - index},
            phase=ExecutionPhase.RESOLVE,
        )
        for index in range(40)
        ),
    )
    initial_participants = (
        BattleReportParticipantDraft(
            "character-private-id",
            "问道客",
            "player",
            1000,
            1000,
            100,
            100,
            attributes={"combat.attack": 100},
            resources={"health.current": 1000},
            abilities=("ability.test",),
            effects={
                "effect.weapon.shared_charge": 2,
                "effect.weapon.shared_mark": 1,
            },
            effect_remaining_turns={
                "effect.weapon.shared_charge": (3,),
                "effect.weapon.shared_mark": (2,),
            },
            cooldowns={"ability.test": 2},
            triggers=("trigger.test",),
        ),
        BattleReportParticipantDraft(
            "enemy-private-id", "山魈", "enemy", 1000, 1000
        ),
    )
    final_participants = (
        replace(
            initial_participants[0],
            health=750,
            resources={"health.current": 750},
            effects={},
            effect_remaining_turns={},
            cooldowns={},
        ),
        replace(initial_participants[1], health=0, resources={"health.current": 0}),
    )
    return BattleReportDraft(
        report_id="battle-report:exploration:session-private-id",
        mode_id="battle.mode.exploration",
        presentation_skin_id=CULTIVATION_SKIN_ID,
        presentation_skin_version=CULTIVATION_SKIN_VERSION,
        content_fingerprint="content-fingerprint",
        summary=BattleReportSummary("探险战报", "1胜 0负", ("完成批次: 1",)),
        segment=BattleReportSegmentDraft(
            segment_id,
            title,
            initial_participants,
            events,
            "胜利",
            logical_time,
            logical_time,
            final_participants=final_participants,
            round_states=(BattleReportRoundStateDraft(1, initial_participants),),
            turn_states=(
                BattleReportTurnStateDraft(
                    1,
                    1,
                    "character-private-id",
                    initial_participants,
                ),
            ),
            transitions=(
                BattleReportTransitionDraft(
                    sequence=0,
                    kind="start",
                    subject_id="battle.transition.start",
                    before=None,
                    after=BattleReportFrameDraft(
                        logical_time=logical_time,
                        round_number=1,
                        turn_number=0,
                        status="active",
                        revision=0,
                        current_actor_entity_id="character-private-id",
                        turn_order_entity_ids=(
                            "character-private-id",
                            "enemy-private-id",
                        ),
                        inactive_entity_ids=(),
                        winning_team_ids=(),
                        action_progress={"character-private-id": 0.2},
                        participants=initial_participants,
                    ),
                    events=events[:2],
                ),
                BattleReportTransitionDraft(
                    sequence=1,
                    kind="turn",
                    subject_id="battle.transition.turn",
                    before=BattleReportFrameDraft(
                        logical_time=logical_time,
                        round_number=1,
                        turn_number=0,
                        status="active",
                        revision=1,
                        current_actor_entity_id="character-private-id",
                        turn_order_entity_ids=(
                            "character-private-id",
                            "enemy-private-id",
                        ),
                        inactive_entity_ids=(),
                        winning_team_ids=(),
                        action_progress={"character-private-id": 0.2},
                        participants=initial_participants,
                    ),
                    after=BattleReportFrameDraft(
                        logical_time=logical_time,
                        round_number=1,
                        turn_number=1,
                        status="finished",
                        revision=2,
                        current_actor_entity_id=None,
                        turn_order_entity_ids=(
                            "character-private-id",
                            "enemy-private-id",
                        ),
                        inactive_entity_ids=("enemy-private-id",),
                        winning_team_ids=("player",),
                        action_progress={"character-private-id": 1.0},
                        participants=final_participants,
                    ),
                    events=events[2:],
                    actor_entity_id="character-private-id",
                    action_id="action:test:1",
                    ability_id="ability.test",
                    decision_rule_id="ai.test.rule",
                    requested_selector_id="target.enemy",
                    requested_target_ids=("enemy-private-id",),
                    resolved_target_ids=("enemy-private-id",),
                    action_parameters={"power": 1.5},
                    action_context_tags=("scene.test",),
                ),
            ),
        ),
    )


if __name__ == "__main__":
    main()
