"""多次元随机降临、同源投影和跃迁纯规则测试。"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import sys
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game.content import (  # noqa: E402
    CULTIVATION_SKIN_ID,
    MAGIC_SKIN_ID,
    PRIMARY_CURRENCY_ID,
    PLAYABLE_WORLD_SKIN_IDS,
    STARTING_CITY_ID,
    build_world_view_catalog,
)
from game.core.gameplay import SeededRandomSource  # noqa: E402
from game.rules.character import (  # noqa: E402
    assign_initial_dimension,
    shift_dimension,
)


NOW = datetime(2026, 7, 18, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))


def main() -> None:
    views = build_world_view_catalog()
    cultivation = views.require(CULTIVATION_SKIN_ID)
    magic = views.require(MAGIC_SKIN_ID)

    assert cultivation is views.require(CULTIVATION_SKIN_ID)
    assert magic is views.require(MAGIC_SKIN_ID)
    assert cultivation.catalog is magic.catalog is views.catalog
    assert cultivation.projector.name(PRIMARY_CURRENCY_ID) != magic.projector.name(
        PRIMARY_CURRENCY_ID
    )
    assert cultivation.projector.name(STARTING_CITY_ID) != magic.projector.name(
        STARTING_CITY_ID
    )
    assert cultivation.catalog.items.definitions.ids() == magic.catalog.items.definitions.ids()
    assert cultivation.catalog.weapons.definitions.ids() == magic.catalog.weapons.definitions.ids()
    assert cultivation.catalog.equipment.definitions.ids() == magic.catalog.equipment.definitions.ids()
    assert views.skin_ids() == PLAYABLE_WORLD_SKIN_IDS
    assert set(views.registered_skin_ids()) >= set(views.skin_ids())

    candidates = views.skin_ids()
    assignments = {
        assign_initial_dimension(
            f"character-{seed}",
            candidates,
            random=SeededRandomSource(seed),
            logical_time=NOW,
        ).skin_id
        for seed in range(32)
    }
    assert assignments == {CULTIVATION_SKIN_ID, MAGIC_SKIN_ID}

    initial = assign_initial_dimension(
        "character-repeatable",
        candidates,
        random=SeededRandomSource("same-seed"),
        logical_time=NOW,
    )
    repeated = assign_initial_dimension(
        "character-repeatable",
        candidates,
        random=SeededRandomSource("same-seed"),
        logical_time=NOW,
    )
    assert repeated == initial

    target = MAGIC_SKIN_ID if initial.skin_id == CULTIVATION_SKIN_ID else CULTIVATION_SKIN_ID
    shifted = shift_dimension(initial, target, logical_time=NOW + timedelta(minutes=1))
    assert shifted.status == "shifted"
    assert shifted.previous_skin_id == initial.skin_id
    assert shifted.current is not None
    assert shifted.current.character_id == initial.character_id
    assert shifted.current.skin_id == target
    assert shifted.current.revision == initial.revision + 1

    unchanged = shift_dimension(
        shifted.current,
        target,
        logical_time=NOW + timedelta(minutes=2),
    )
    assert unchanged.status == "already_there"
    assert unchanged.current == shifted.current

    forbidden = (
        "services.content.projector",
        "services.content.gear_projector",
        "services.content.enemy_projector",
        "current_game_services().content.projector",
    )
    for root in (ROOT / "game" / "cmd", ROOT / "game" / "features"):
        for path in root.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert not any(value in source for value in forbidden), (
                f"玩家展示不能回退到服务器默认皮肤: {path}"
            )

    print("dimension projection tests passed")


if __name__ == "__main__":
    main()
