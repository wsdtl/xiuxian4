"""初始世界空间与坐标化中心城市。"""

import re

from game.core.gameplay import (
    WorldLocationDefinition,
    WorldSpaceDefinition,
    WorldTopologyKind,
)


PRIMARY_WORLD_SPACE_ID = "world_space.primary"
STARTING_CITY_ID = "location.main_city_x0_y0"
CHARACTER_PRESENCE_KIND_ID = "presence.character"

PRIMARY_WORLD_SPACE = WorldSpaceDefinition(
    PRIMARY_WORLD_SPACE_ID,
    WorldTopologyKind.GRID,
    minimum_x=-1_000_000,
    maximum_x=1_000_000,
    minimum_y=-1_000_000,
    maximum_y=1_000_000,
)
STARTING_CITY = WorldLocationDefinition(
    STARTING_CITY_ID,
    PRIMARY_WORLD_SPACE_ID,
    x=0,
    y=0,
)

WORLD_DISPLAY_CONTENT_IDS = frozenset(
    {PRIMARY_WORLD_SPACE_ID, STARTING_CITY_ID}
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


validate_location_coordinate_id(STARTING_CITY)


__all__ = [
    "CHARACTER_PRESENCE_KIND_ID",
    "PRIMARY_WORLD_SPACE",
    "PRIMARY_WORLD_SPACE_ID",
    "STARTING_CITY",
    "STARTING_CITY_ID",
    "WORLD_DISPLAY_CONTENT_IDS",
    "coordinate_token",
    "validate_location_coordinate_id",
]
