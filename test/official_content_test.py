"""官方基础名录、双世界皮肤和统一装配边界测试。"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game.content import (  # noqa: E402
    BASIC_ATTACK_ABILITY_ID,
    BASIC_COMBAT_FEATURE_ID,
    CATALOG_PACKAGE,
    CATALOG_PACKAGE_ID,
    CHARACTER_LEVEL_EXPERIENCE_REQUIREMENTS,
    DEFAULT_CHARACTER_TEMPLATE_ID,
    COMMON_QUALITY_ID,
    CULTIVATION_SKIN,
    CULTIVATION_SKIN_ID,
    DEFAULT_SKIN_ID,
    MAGIC_SKIN,
    MAGIC_SKIN_ID,
    PRIMARY_CURRENCY_ID,
    STARTING_CITY_ID,
    coordinate_token,
    validate_location_coordinate_id,
    SKIN_PACKAGE_ID,
    SKIN_PACKAGE,
    assemble_official_catalog,
    select_world_skin,
)
from game.core.gameplay import (  # noqa: E402
    ContentAssembler,
    CurrencyDefinition,
    LoadoutState,
    WorldLocationDefinition,
)


def main() -> None:
    catalog = assemble_official_catalog()

    assert tuple(value.id for value in catalog.report.packages) == (
        CATALOG_PACKAGE_ID,
        SKIN_PACKAGE_ID,
    )
    assert len(catalog.report.content_fingerprint) == 64
    assert catalog.report.display_content_ids == CATALOG_PACKAGE.display_content_ids
    progression = catalog.characters.progressions.require("progression.character_level")
    assert progression.maximum_level == 100
    assert progression.experience_requirements == CHARACTER_LEVEL_EXPERIENCE_REQUIREMENTS
    assert progression.required_for_next_level(80) == 6_359_356
    assert progression.required_for_next_level(90) == 10_356_800
    assert progression.required_for_next_level(99) == 13_380_764
    assert sum(progression.experience_requirements) == 270_305_413
    assert catalog.characters.templates.require(DEFAULT_CHARACTER_TEMPLATE_ID)
    basic_combat = catalog.characters.features.require(BASIC_COMBAT_FEATURE_ID)
    assert BASIC_ATTACK_ABILITY_ID in basic_combat.contribution.abilities
    city = catalog.world.locations.require(STARTING_CITY_ID)
    assert (city.x, city.y) == (0, 0)
    assert coordinate_token(12) == "p12"
    assert coordinate_token(-12) == "n12"
    validate_location_coordinate_id(city)
    try:
        validate_location_coordinate_id(
            WorldLocationDefinition(
                "location.main_city_xp1_y0",
                city.space_id,
                x=2,
                y=0,
            )
        )
        raise AssertionError("地点 ID 后缀必须与真实坐标一致")
    except ValueError as exc:
        assert "坐标后缀" in str(exc)
    assert not LoadoutState("empty-loadout-character").slots
    assert catalog.skins.frozen
    assert catalog.skins.skin_ids() == (CULTIVATION_SKIN_ID, MAGIC_SKIN_ID)

    cultivation = select_world_skin(catalog, DEFAULT_SKIN_ID)
    magic = select_world_skin(catalog, MAGIC_SKIN_ID)
    assert cultivation.catalog is magic.catalog
    assert cultivation.skin.name == "基础修仙界"
    assert cultivation.skin.icon == "☯"
    assert cultivation.projector.name(PRIMARY_CURRENCY_ID) == "灵石"
    assert cultivation.projector.name(COMMON_QUALITY_ID) == "凡品"
    assert magic.skin.name == "魔法世界"
    assert magic.skin.icon == "✦"
    assert magic.projector.name(PRIMARY_CURRENCY_ID) == "魔晶"
    assert magic.projector.name(COMMON_QUALITY_ID) == "普通"
    assert cultivation.projector.name(STARTING_CITY_ID) == "太玄仙城"
    assert magic.projector.name(STARTING_CITY_ID) == "星辉王城"

    _assert_new_display_content_requires_both_skins()
    print("official content tests passed")


def _assert_new_display_content_requires_both_skins() -> None:
    required = frozenset(
        {PRIMARY_CURRENCY_ID, COMMON_QUALITY_ID, "item.example"}
    )
    for skin in (CULTIVATION_SKIN, MAGIC_SKIN):
        try:
            skin.validate(required)
            raise AssertionError("新增展示内容必须同步补齐全部世界皮肤")
        except ValueError as exc:
            assert "缺少条目" in str(exc)

    changed_catalog = replace(
        CATALOG_PACKAGE,
        currencies=(
            *CATALOG_PACKAGE.currencies,
            CurrencyDefinition("currency.new_for_test"),
        ),
        display_content_ids=(
            CATALOG_PACKAGE.display_content_ids | {"currency.new_for_test"}
        ),
    )
    try:
        ContentAssembler().assemble((changed_catalog, SKIN_PACKAGE))
        raise AssertionError("完整装配不能接受缺少世界皮肤名称的新内容")
    except ValueError as exc:
        assert "缺少条目" in str(exc)


if __name__ == "__main__":
    main()
