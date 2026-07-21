"""三个正式世界的独立地图布局与地点映射验收。"""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game.content import (  # noqa: E402
    MAGIC_WORLD_ID,
    STELLAR_RING_WORLD_ID,
    TAIXUAN_WORLD_ID,
    build_world_view_catalog,
)
from game.content.catalog.world import (  # noqa: E402
    GREEN_CLOUD_PLAIN_ID,
    PERSON_EAST_LOCATION_ID,
    PERSON_NORTH_LOCATION_ID,
    PERSON_WEST_LOCATION_ID,
)


def main() -> None:
    worlds = build_world_view_catalog().worlds
    layouts = {
        world_id: {
            binding.display_ref: (
                worlds.require_anchor(binding.anchor_id).x,
                worlds.require_anchor(binding.anchor_id).y,
            )
            for binding in worlds.bindings_for_world(world_id)
        }
        for world_id in (TAIXUAN_WORLD_ID, MAGIC_WORLD_ID, STELLAR_RING_WORLD_ID)
    }

    assert all(len(layout) == 17 for layout in layouts.values())
    assert len(
        {
            binding.anchor_id
            for world_id in layouts
            for binding in worlds.bindings_for_world(world_id)
        }
    ) == 51

    first_region_positions = {
        layout[GREEN_CLOUD_PLAIN_ID]
        for layout in layouts.values()
    }
    assert len(first_region_positions) == 3

    stellar = layouts[STELLAR_RING_WORLD_ID]
    inner_ring = {
        (0, 24),
        (17, 17),
        (24, 0),
        (17, -17),
        (0, -24),
        (-17, -17),
        (-24, 0),
        (-17, 17),
    }
    assert inner_ring <= set(stellar.values())
    assert {
        stellar[PERSON_WEST_LOCATION_ID],
        stellar[PERSON_EAST_LOCATION_ID],
        stellar[PERSON_NORTH_LOCATION_ID],
    } == {(-12, 36), (0, 36), (12, 36)}

    for display_id in layouts[TAIXUAN_WORLD_ID]:
        for world_id in layouts:
            binding = worlds.require_binding_for_display(world_id, display_id)
            resolved = worlds.resolve(world_id, binding.anchor_id)
            assert resolved.display_id == display_id
            assert (resolved.position.x, resolved.position.y) == layouts[world_id][display_id]

    print("world layout tests passed")


if __name__ == "__main__":
    main()
