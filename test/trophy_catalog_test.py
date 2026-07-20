"""两百种战利品、价格曲线与双世界展示审计。"""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game.content import MAGIC_SKIN_ID, assemble_official_catalog, select_world_skin  # noqa: E402
from game.content.catalog import PRIMARY_CURRENCY_ID  # noqa: E402
from game.content.catalog.exploration import REGULAR_EXPLORATION_REGIONS  # noqa: E402
from game.content.catalog.item import (  # noqa: E402
    BOSS_TROPHY_ITEMS,
    PARTY_BOSS_TROPHY_ITEMS,
    ITEM_RECYCLE_COMPONENT_ID,
    REGION_TROPHY_ITEMS,
    REGION_TROPHY_WEIGHTS,
    REGULAR_ENEMY_TROPHY_ITEMS,
    TROPHY_ITEMS,
    WORLD_CURIO_ITEMS,
    ItemRecycleValue,
)
from game.core.gameplay import ITEM_STORAGE_COMPONENT_ID, ItemStorageComponent  # noqa: E402


def main() -> None:
    catalog = assemble_official_catalog()
    cultivation = select_world_skin(catalog)
    magic = select_world_skin(catalog, MAGIC_SKIN_ID)
    assert len(TROPHY_ITEMS) == 200
    assert sum(len(items) for items in REGION_TROPHY_ITEMS.values()) == 78
    assert len(REGULAR_ENEMY_TROPHY_ITEMS) == 60
    assert len(BOSS_TROPHY_ITEMS) == 30
    assert len(PARTY_BOSS_TROPHY_ITEMS) == 20
    assert len(WORLD_CURIO_ITEMS) == 12
    assert sum(REGION_TROPHY_WEIGHTS) == 100

    cultivation_names = []
    magic_names = []
    for item in TROPHY_ITEMS:
        assert item.tags.has("item.trophy")
        assert item.tags.has("loot.recyclable")
        assert item.tags.has("storage.backpack")
        storage = item.component(ITEM_STORAGE_COMPONENT_ID, ItemStorageComponent)
        sale = item.component(ITEM_RECYCLE_COMPONENT_ID, ItemRecycleValue)
        assert storage.unit_space == 1
        assert sale.currency_id == PRIMARY_CURRENCY_ID
        assert sale.unit_amount > 0
        cultivation_names.append(cultivation.projector.name(item.id))
        magic_names.append(magic.projector.name(item.id))
    assert len(cultivation_names) == len(set(cultivation_names)) == 200
    assert len(magic_names) == len(set(magic_names)) == 200
    assert cultivation_names != magic_names

    expected_values = []
    for region in REGULAR_EXPLORATION_REGIONS:
        prices = tuple(
            catalog.items.require(item_id)
            .component(ITEM_RECYCLE_COMPONENT_ID, ItemRecycleValue)
            .unit_amount
            for item_id in region.trophy_item_ids
        )
        expected_values.append(
            sum(price * weight for price, weight in zip(prices, region.trophy_weights))
            / sum(region.trophy_weights)
        )
    assert all(left < right for left, right in zip(expected_values, expected_values[1:]))
    print("trophy catalog tests passed")


if __name__ == "__main__":
    main()
