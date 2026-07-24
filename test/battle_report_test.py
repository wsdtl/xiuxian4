"""统一战报压缩、幂等、公开读取和保留期测试。"""

from __future__ import annotations

import ast
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
PREVIEW_ROOT = ROOT / "design" / "previews"
if str(PREVIEW_ROOT) not in sys.path:
    sys.path.insert(0, str(PREVIEW_ROOT))

from game.core.gameplay import ExecutionPhase, HEALTH_CURRENT, RuleEvent  # noqa: E402
from game.core.persistence import BattleReportStore, SqliteDatabase  # noqa: E402
from game.app import build_game_services, install_game_services, restore_game_services  # noqa: E402
from game.cmd import router as game_router  # noqa: E402
from game.content.world_skins.cultivation import (  # noqa: E402
    CULTIVATION_SKIN_ID,
    CULTIVATION_SKIN_VERSION,
)
from game.features.battle_report import (  # noqa: E402
    BATTLE_EVENT_PRESENTATIONS,
    PUBLIC_BATTLE_REPORT_SCHEMA,
    PUBLIC_BATTLE_REPORT_VERSION,
    BattleReportService,
    present_battle_event,
)
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
from generate_battle_report_preview import (  # noqa: E402
    build_preview_document,
)


NOW = datetime.now(timezone.utc).replace(microsecond=0)


def main() -> None:
    _assert_all_current_events_are_rendered()
    _assert_production_preview()
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
            app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
            with TestClient(app) as client:
                response = client.get(f"/battle/{reference.share_id}")
                assert response.status_code == 200
                assert "/static/battle-report/style.css" in response.text
                assert "/static/battle-report/app.js" in response.text
                assert 'script type="module"' in response.text
                script_response = client.get("/static/battle-report/app.js")
                assert script_response.status_code == 200
                script = script_response.text
                timeline_response = client.get("/static/battle-report/timeline.js")
                ui_response = client.get("/static/battle-report/ui.js")
                assert timeline_response.status_code == 200
                assert ui_response.status_code == 200
                timeline_script = timeline_response.text
                ui_script = ui_response.text
                assert 'const MODE_OPTIONS' in script
                assert 'action === "mode"' in script
                assert 'action === "segment"' in script
                assert 'action === "snapshot"' in script
                assert 'action === "participant-disclosure"' in script
                assert 'action === "filter"' in script
                assert 'label: "战斗记录"' in script
                assert 'label: "全部事件"' in script
                assert 'label: "原始"' not in timeline_script
                assert 'compactNarrative' not in timeline_script
                assert 'export function renderRawDataAccess' in timeline_script
                assert 'details.addEventListener("toggle"' in timeline_script
                assert 'const state' not in timeline_script
                assert 'document.querySelector("#reportRoot")' not in timeline_script
                assert 'export function node' in ui_script
                assert 'const state' not in ui_script
                assert 'function updateSegmentView()' in script
                assert 'function updateSnapshotView()' in script
                snapshot_update = script.split(
                    'function updateSnapshotView()', 1
                )[1].split('function updateFilterView()', 1)[0]
                assert 'replaceRegion(root, ".summary-panel"' not in snapshot_update
                assert 'replaceRegion(root, ".participant-stack"' in snapshot_update
                assert 'disclosure.querySelector(".participant-disclosure-title span")' in snapshot_update
                assert 'function updateParticipantDisclosure()' in script
                assert 'content.toggleAttribute("inert", !state.participantExpanded)' in script
                assert 'function updateFilterView()' in script
                assert 'function selectSegment(index)' in script
                assert 'const many = segments.length > 6' in script
                assert 'select.dataset.action = "segment-select"' in script
                assert 'segmentStepButton("上一片段"' in script
                assert 'segmentStepButton("下一片段"' in script
                combined_script = script + timeline_script + ui_script
                assert 'document.startViewTransition' not in combined_script
                assert 'transitionView' not in combined_script
                assert script.count('renderReport();') == 1
                style_response = client.get("/static/battle-report/style.css")
                assert style_response.status_code == 200
                assert 'prefers-reduced-motion' in style_response.text
                assert 'scrollbar-width: none' in style_response.text
                assert '.participant-stack {' in style_response.text
                assert 'overflow: visible' in style_response.text
                assert '.timeline-panel {' in style_response.text
                assert 'font-family: var(--display-font)' not in style_response.text
                assert '.segment-tabs.many-segments .segment-picker' in style_response.text
                assert 'view-transition' not in style_response.text
                assert '--stagger' not in style_response.text
                assert "borrowed_edge" not in combined_script
                assert "deferred_echo" not in combined_script

                data_response = client.get(f"/battle/{reference.share_id}/data")
                assert data_response.status_code == 200
                payload = data_response.json()
                assert payload["schema"] == PUBLIC_BATTLE_REPORT_SCHEMA
                assert payload["version"] == PUBLIC_BATTLE_REPORT_VERSION
                assert payload["summary"]["title"] == "探险战报"
                segment = payload["detail"]["segments"][0]
                assert segment["title"] == "第一战"
                assert segment["initial_participants"][0]["effects"][0]["polarity"]
                turn = segment["timeline"][1]
                assert "受到 100 点伤害" in turn["events"][0]["text"]
                assert turn["before"]["title"] == "动作前完整状态"
                assert turn["after"]["title"] == "动作后完整状态"
                assert any(
                    fact["label"] == "实际目标" and fact["value"] == ["山魈"]
                    for fact in turn["facts"]
                )
                assert "character-private-id" not in data_response.text
                assert "enemy-private-id" not in data_response.text
                assert client.get("/battle/not-found").status_code == 404
                assert client.get("/battle/not-found/data").status_code == 404
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


def _assert_production_preview() -> None:
    preview_path = PREVIEW_ROOT / "battle-report-production.html"
    assert preview_path.is_file()
    assert not (PREVIEW_ROOT / "battle-report-humanized.html").exists()
    preview = preview_path.read_text(encoding="utf-8")
    assert "<style" not in preview
    assert "maximum-scale=1, user-scalable=no" in preview
    assert "../../static/battle-report/style.css?v=16" in preview
    assert "../../static/battle-report/app.js?v=16" in preview
    assert 'script type="module"' in preview
    opening = '<script id="battleReportPreviewData" type="application/json">'
    payload = preview.split(opening, 1)[1].split("</script>", 1)[0]
    embedded = json.loads(payload)
    generated = build_preview_document()
    generated["share_id"] = embedded["share_id"]
    assert embedded == generated
    assert embedded["schema"] == PUBLIC_BATTLE_REPORT_SCHEMA
    assert embedded["version"] == PUBLIC_BATTLE_REPORT_VERSION
    assert embedded["mode_id"] == "battle.mode.party_battle"
    assert embedded["detail"]["available"] is True
    assert len(embedded["detail"]["segments"]) >= 1
    assert all(segment["timeline"] for segment in embedded["detail"]["segments"])
    assert {
        "观潮客",
        "砺锋客",
        "司星者",
    }.issubset(
        {
            participant["label"]
            for participant in embedded["detail"]["segments"][0][
                "initial_participants"
            ]
        }
    )
    assert "ability.test" not in payload
    assert "combat.damage.dealt" in payload
    events = [
        event
        for segment in embedded["detail"]["segments"]
        for transition in segment["timeline"]
        for event in transition["events"]
    ]
    phase_events = [
        event for event in events if event["kind"] == "combat.phase.activated"
    ]
    assert phase_events
    assert all(
        event["registered"]
        and "进入新的战斗阶段" in event["text"]
        and "获得" in event["text"]
        and event["raw"]["values"]["behavior_ids"]
        for event in phase_events
    )


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
    assert BATTLE_EVENT_PRESENTATIONS.registered_kinds == KNOWN_BATTLE_EVENT_KINDS
    view = _FallbackView()
    for kind in sorted(KNOWN_BATTLE_EVENT_KINDS):
        event = present_battle_event(
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
        assert event["registered"] is True, kind
        assert event["text"] and event["tone"] != "unknown", kind

    unknown = present_battle_event(
        StoredBattleEvent(
            "combat.future.time_rewind",
            "p0",
            "p1",
            "effect.future.time_rewind",
            NOW,
            {
                "restored_health": 300,
                "state": {"before": 100, "after": 400},
                "operation_id": "private-operation",
            },
        ),
        {"p0": "甲", "p1": "乙"},
        view,
    )
    assert unknown["registered"] is False
    assert unknown["tone"] == "unknown"
    assert unknown["text"].startswith("甲 对 乙 触发未识别的战斗事件")
    assert "combat.future.time_rewind" not in unknown["text"]
    assert "effect.future.time_rewind" not in unknown["text"]
    assert unknown["raw"]["values"]["state"] == {"before": 100, "after": 400}
    assert unknown["raw"]["omitted_private_keys"] == ["operation_id"]
    assert "private-operation" not in str(unknown)

    rejected = present_battle_event(
        StoredBattleEvent(
            "effect.application.rejected",
            "p0",
            "p1",
            "effect.test",
            NOW,
            {"reason": "control_resisted", "chance": 0.5, "roll": 0.8},
        ),
        {"p0": "甲", "p1": "乙"},
        view,
    )
    assert rejected["registered"] is True
    assert rejected["text"] == "乙抵抗了甲施加的效果"

    revived = present_battle_event(
        StoredBattleEvent(
            "combat.target.revived",
            "p0",
            "p1",
            "health.current",
            NOW,
            {"before": 0, "after": 30, "actual": 30},
        ),
        {"p0": "甲", "p1": "乙"},
        view,
    )
    assert revived["registered"] is True
    assert revived["text"] == "甲使乙重新投入战斗"


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
