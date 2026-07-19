"""太玄界有限坐标空间、中心仙城与首批探险地点。"""

import re

from game.core.gameplay import (
    WorldLocationDefinition,
    WorldSpaceDefinition,
    WorldTopologyKind,
)


PRIMARY_WORLD_SPACE_ID = "world_space.primary"
STARTING_CITY_ID = "location.main_city_x0_y0"
CHARACTER_PRESENCE_KIND_ID = "presence.character"

GREEN_CLOUD_PLAIN_ID = "location.green_cloud_plain_xn20_yp10"
SUNSET_RIDGE_ID = "location.sunset_ridge_xp10_yp20"
BLACK_WIND_RAVINE_ID = "location.black_wind_ravine_xn30_yp30"
MIRROR_LAKE_MARSH_ID = "location.mirror_lake_marsh_xp30_yp30"
SCARLET_FLAME_VALLEY_ID = "location.scarlet_flame_valley_xn45_yp10"
VERDANT_WILDERNESS_ID = "location.verdant_wilderness_xp45_yp5"
THUNDER_MARSH_STEPPE_ID = "location.thunder_marsh_steppe_xn50_yn25"
NORTHERN_ABYSS_SNOWFIELD_ID = "location.northern_abyss_snowfield_xp40_yn35"
BROKEN_PILLAR_RELIC_ID = "location.broken_pillar_relic_xn20_yn50"
KUNLUN_SKY_RUINS_ID = "location.kunlun_sky_ruins_xp15_yn60"
MYRIAD_SWORD_TOMB_ID = "location.myriad_sword_tomb_xn80_yp70"
HEAVENLY_CRAFT_RELIC_ID = "location.heavenly_craft_relic_xp75_yp60"
RETURNING_RUIN_ABYSS_ID = "location.returning_ruin_abyss_x0_yn90"

PRIMARY_WORLD_SPACE = WorldSpaceDefinition(
    PRIMARY_WORLD_SPACE_ID,
    WorldTopologyKind.GRID,
    minimum_x=-100,
    maximum_x=100,
    minimum_y=-100,
    maximum_y=100,
)
STARTING_CITY = WorldLocationDefinition(
    STARTING_CITY_ID,
    PRIMARY_WORLD_SPACE_ID,
    x=0,
    y=0,
)


EXPLORATION_LOCATIONS = (
    WorldLocationDefinition(GREEN_CLOUD_PLAIN_ID, PRIMARY_WORLD_SPACE_ID, x=-20, y=10),
    WorldLocationDefinition(SUNSET_RIDGE_ID, PRIMARY_WORLD_SPACE_ID, x=10, y=20),
    WorldLocationDefinition(BLACK_WIND_RAVINE_ID, PRIMARY_WORLD_SPACE_ID, x=-30, y=30),
    WorldLocationDefinition(MIRROR_LAKE_MARSH_ID, PRIMARY_WORLD_SPACE_ID, x=30, y=30),
    WorldLocationDefinition(SCARLET_FLAME_VALLEY_ID, PRIMARY_WORLD_SPACE_ID, x=-45, y=10),
    WorldLocationDefinition(VERDANT_WILDERNESS_ID, PRIMARY_WORLD_SPACE_ID, x=45, y=5),
    WorldLocationDefinition(THUNDER_MARSH_STEPPE_ID, PRIMARY_WORLD_SPACE_ID, x=-50, y=-25),
    WorldLocationDefinition(NORTHERN_ABYSS_SNOWFIELD_ID, PRIMARY_WORLD_SPACE_ID, x=40, y=-35),
    WorldLocationDefinition(BROKEN_PILLAR_RELIC_ID, PRIMARY_WORLD_SPACE_ID, x=-20, y=-50),
    WorldLocationDefinition(KUNLUN_SKY_RUINS_ID, PRIMARY_WORLD_SPACE_ID, x=15, y=-60),
    WorldLocationDefinition(MYRIAD_SWORD_TOMB_ID, PRIMARY_WORLD_SPACE_ID, x=-80, y=70),
    WorldLocationDefinition(HEAVENLY_CRAFT_RELIC_ID, PRIMARY_WORLD_SPACE_ID, x=75, y=60),
    WorldLocationDefinition(RETURNING_RUIN_ABYSS_ID, PRIMARY_WORLD_SPACE_ID, x=0, y=-90),
)
ALL_WORLD_LOCATIONS = (STARTING_CITY, *EXPLORATION_LOCATIONS)

WORLD_DISPLAY_CONTENT_IDS = frozenset(
    {PRIMARY_WORLD_SPACE_ID, *(value.id for value in ALL_WORLD_LOCATIONS)}
)

_COORDINATE_SUFFIX = re.compile(r"_x(0|p[1-9][0-9]*|n[1-9][0-9]*)_y(0|p[1-9][0-9]*|n[1-9][0-9]*)$")


def coordinate_token(value: int) -> str:
    """把整数坐标编码为稳定 ID 后缀，不参与运行期坐标计算。"""

    if value == 0:
        return "0"
    return f"p{value}" if value > 0 else f"n{abs(value)}"


def validate_location_coordinate_id(definition: WorldLocationDefinition) -> None:
    """正式地点装配时校验 ID 后缀与定义中的真实坐标一致。"""

    if definition.x is None or definition.y is None:
        raise ValueError("坐标化地点必须提供 x/y")
    match = _COORDINATE_SUFFIX.search(definition.id)
    expected = f"_x{coordinate_token(definition.x)}_y{coordinate_token(definition.y)}"
    if match is None or match.group(0) != expected:
        raise ValueError(f"地点 ID 坐标后缀与实际坐标不一致：{definition.id} != {expected}")


for _location in ALL_WORLD_LOCATIONS:
    validate_location_coordinate_id(_location)


__all__ = [
    "ALL_WORLD_LOCATIONS",
    "BLACK_WIND_RAVINE_ID",
    "BROKEN_PILLAR_RELIC_ID",
    "CHARACTER_PRESENCE_KIND_ID",
    "EXPLORATION_LOCATIONS",
    "GREEN_CLOUD_PLAIN_ID",
    "HEAVENLY_CRAFT_RELIC_ID",
    "KUNLUN_SKY_RUINS_ID",
    "MIRROR_LAKE_MARSH_ID",
    "MYRIAD_SWORD_TOMB_ID",
    "NORTHERN_ABYSS_SNOWFIELD_ID",
    "PRIMARY_WORLD_SPACE",
    "PRIMARY_WORLD_SPACE_ID",
    "RETURNING_RUIN_ABYSS_ID",
    "SCARLET_FLAME_VALLEY_ID",
    "STARTING_CITY",
    "STARTING_CITY_ID",
    "SUNSET_RIDGE_ID",
    "THUNDER_MARSH_STEPPE_ID",
    "VERDANT_WILDERNESS_ID",
    "WORLD_DISPLAY_CONTENT_IDS",
    "coordinate_token",
    "validate_location_coordinate_id",
]
