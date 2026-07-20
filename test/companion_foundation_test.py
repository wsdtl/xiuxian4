"""伙伴内容、随机生成、名册、配装独占和战斗投影测试。"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
import sys
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game.content import (  # noqa: E402
    COMPANION_CATALOG,
    CULTIVATION_SKIN_ID,
    LOADOUT_PRESET_IDS,
    build_official_content,
)
from game.rules.companion import (  # noqa: E402
    COMPANION_APTITUDE_IDS,
    CompanionCombatProjector,
    CompanionEngine,
    CompanionRosterState,
    CompanionRuleError,
    CompanionSanctuaryStatus,
)
from game.core.gameplay import SeededRandomSource, TagSet  # noqa: E402


NOW = datetime(2026, 7, 20, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))


def main() -> None:
    content = build_official_content(CULTIVATION_SKIN_ID)
    engine = CompanionEngine(COMPANION_CATALOG)
    roster = CompanionRosterState("character-a")
    first = engine.open_sanctuary(
        roster,
        None,
        session_id="sanctuary-a",
        world_skin_id=CULTIVATION_SKIN_ID,
        character_level=37,
        logical_time=NOW,
        random=SeededRandomSource("sanctuary-a"),
    )
    replay = engine.open_sanctuary(
        roster,
        None,
        session_id="sanctuary-a",
        world_skin_id=CULTIVATION_SKIN_ID,
        character_level=37,
        logical_time=NOW,
        random=SeededRandomSource("sanctuary-a"),
    )
    assert first == replay
    assert len(first.traces) == 3
    assert len({value.definition_id for value in first.traces}) == 3
    assert all(value.level == 37 for value in first.traces)
    for trace in first.traces:
        assert set(trace.aptitudes) == set(COMPANION_APTITUDE_IDS)
        assert sum(trace.aptitudes.values()) == COMPANION_CATALOG.balance.aptitude_budgets[
            trace.quality_id
        ]

    selected = engine.select_trace(first, 2, logical_time=NOW)
    assert selected.status is CompanionSanctuaryStatus.TRACKING
    assert engine.select_trace(selected, 2, logical_time=NOW) == selected
    _fails(
        "companion.trace_locked",
        lambda: engine.select_trace(selected, 1, logical_time=NOW),
    )

    trace = selected.selected_trace()
    assert trace is not None
    projection = CompanionCombatProjector(
        content.catalog,
        content.companions,
    ).project(
        trace,
        entity_id="trace-target",
        context_tags=TagSet.of("scene.companion_sanctuary"),
    )
    assert projection.entity.id == "trace-target"
    assert projection.entity.tags.has("entity.companion")
    assert "ability.basic_attack" in projection.entity.abilities
    assert len(projection.ai_rules) >= 3

    next_roster, captured, companion = engine.capture(
        roster,
        selected,
        logical_time=NOW,
    )
    assert companion.reference == "C1"
    assert captured.status is CompanionSanctuaryStatus.CAPTURED
    assert next_roster.by_reference("c1") == companion
    assert companion.definition_id in next_roster.captured_definition_ids

    bound = engine.bind(next_roster, companion.id, LOADOUT_PRESET_IDS[0])
    assert bound.companion_for_preset(LOADOUT_PRESET_IDS[0]) == companion
    _fails(
        "companion.bound_elsewhere",
        lambda: engine.bind(bound, companion.id, LOADOUT_PRESET_IDS[1]),
    )
    transferred = engine.bind(
        bound,
        companion.id,
        LOADOUT_PRESET_IDS[1],
        allow_transfer=True,
    )
    assert transferred.companion_for_preset(LOADOUT_PRESET_IDS[0]) is None
    assert transferred.companion_for_preset(LOADOUT_PRESET_IDS[1]) == companion
    released = engine.release(transferred, companion.id)
    assert not released.instances
    assert not released.bindings
    assert companion.definition_id in released.captured_definition_ids

    full_instances = {
        (clone := replace(
            companion,
            id=f"character-a:companion:{index}",
            reference=f"C{index}",
        )).id: clone
        for index in range(1, 31)
    }
    full = CompanionRosterState(
        "character-a",
        full_instances,
        next_sequence=31,
    )
    _fails(
        "companion.roster_full",
        lambda: engine.open_sanctuary(
            full,
            captured,
            session_id="sanctuary-full",
            world_skin_id=CULTIVATION_SKIN_ID,
            character_level=37,
            logical_time=NOW,
            random=SeededRandomSource("sanctuary-full"),
        ),
    )

    expired = engine.expire(first, logical_time=NOW + timedelta(days=2))
    assert expired.status is CompanionSanctuaryStatus.EXPIRED
    print("companion foundation tests passed")


def _fails(code: str, operation) -> None:
    try:
        operation()
    except CompanionRuleError as exc:
        assert exc.code == code
    else:
        raise AssertionError(f"expected companion failure: {code}")


if __name__ == "__main__":
    main()
