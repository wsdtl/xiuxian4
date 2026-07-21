"""三个正式世界的独立地图布局。"""

from types import MappingProxyType

from game.core.gameplay import MapAnchorDefinition

from ..catalog.world import (
    BLACK_WIND_RAVINE_ID,
    BROKEN_PILLAR_RELIC_ID,
    GREEN_CLOUD_PLAIN_ID,
    HEAVENLY_CRAFT_RELIC_ID,
    KUNLUN_SKY_RUINS_ID,
    LOCATION_DISPLAY_IDS,
    MIRROR_LAKE_MARSH_ID,
    MYRIAD_SWORD_TOMB_ID,
    NORTHERN_ABYSS_SNOWFIELD_ID,
    PERSON_EAST_LOCATION_ID,
    PERSON_NORTH_LOCATION_ID,
    PERSON_WEST_LOCATION_ID,
    RETURNING_RUIN_ABYSS_ID,
    SCARLET_FLAME_VALLEY_ID,
    STARTING_CITY_ID,
    SUNSET_RIDGE_ID,
    THUNDER_MARSH_STEPPE_ID,
    VERDANT_WILDERNESS_ID,
    coordinate_token,
    validate_anchor_coordinate_id,
)


def _layout(world_token: str, positions: dict[str, tuple[int, int]]):
    expected = set(LOCATION_DISPLAY_IDS)
    if set(positions) != expected:
        missing = sorted(expected - set(positions))
        unknown = sorted(set(positions) - expected)
        raise ValueError(
            f"{world_token} 地图布局不完整，缺少={missing}，未知={unknown}"
        )
    if len(set(positions.values())) != len(positions):
        raise ValueError(f"{world_token} 地图布局存在重复坐标")
    anchors = {}
    for display_id, (x, y) in positions.items():
        display_token = display_id.removeprefix("location.")
        anchor = MapAnchorDefinition(
            f"map_anchor.{world_token}_{display_token}_"
            f"x{coordinate_token(x)}_y{coordinate_token(y)}",
            x,
            y,
        )
        validate_anchor_coordinate_id(anchor)
        anchors[display_id] = anchor
    return MappingProxyType(anchors)


# 太玄界沿山脉、河谷和遗迹自然散布，不追求几何对称。
TAIXUAN_LAYOUT = _layout(
    "taixuan",
    {
        STARTING_CITY_ID: (0, 0),
        GREEN_CLOUD_PLAIN_ID: (-18, 12),
        SUNSET_RIDGE_ID: (14, 24),
        BLACK_WIND_RAVINE_ID: (-34, 37),
        MIRROR_LAKE_MARSH_ID: (31, 33),
        SCARLET_FLAME_VALLEY_ID: (-52, 16),
        VERDANT_WILDERNESS_ID: (48, 8),
        THUNDER_MARSH_STEPPE_ID: (-57, -28),
        NORTHERN_ABYSS_SNOWFIELD_ID: (43, -39),
        BROKEN_PILLAR_RELIC_ID: (-26, -55),
        KUNLUN_SKY_RUINS_ID: (18, -67),
        MYRIAD_SWORD_TOMB_ID: (-82, 72),
        HEAVENLY_CRAFT_RELIC_ID: (76, 63),
        RETURNING_RUIN_ABYSS_ID: (2, -92),
        PERSON_WEST_LOCATION_ID: (-13, -9),
        PERSON_EAST_LOCATION_ID: (24, -16),
        PERSON_NORTH_LOCATION_ID: (9, 44),
    },
)


# 魔法世界围绕星辉王城形成内环、外环和三处远端秘所。
MAGIC_LAYOUT = _layout(
    "magic",
    {
        STARTING_CITY_ID: (0, 0),
        GREEN_CLOUD_PLAIN_ID: (0, 18),
        SUNSET_RIDGE_ID: (17, 10),
        BLACK_WIND_RAVINE_ID: (20, -12),
        MIRROR_LAKE_MARSH_ID: (0, -24),
        SCARLET_FLAME_VALLEY_ID: (-22, -12),
        VERDANT_WILDERNESS_ID: (-18, 11),
        THUNDER_MARSH_STEPPE_ID: (0, 42),
        NORTHERN_ABYSS_SNOWFIELD_ID: (38, 20),
        BROKEN_PILLAR_RELIC_ID: (38, -24),
        KUNLUN_SKY_RUINS_ID: (-40, -22),
        MYRIAD_SWORD_TOMB_ID: (0, 72),
        HEAVENLY_CRAFT_RELIC_ID: (68, -58),
        RETURNING_RUIN_ABYSS_ID: (-70, -60),
        PERSON_WEST_LOCATION_ID: (-8, 28),
        PERSON_EAST_LOCATION_ID: (28, 0),
        PERSON_NORTH_LOCATION_ID: (-28, 0),
    },
)


# 星环界严格服从轴线、镜像和固定间距，连人物驻点也排列成等距阵列。
STELLAR_RING_LAYOUT = _layout(
    "stellar_ring",
    {
        STARTING_CITY_ID: (0, 0),
        GREEN_CLOUD_PLAIN_ID: (0, 24),
        SUNSET_RIDGE_ID: (17, 17),
        BLACK_WIND_RAVINE_ID: (24, 0),
        MIRROR_LAKE_MARSH_ID: (17, -17),
        SCARLET_FLAME_VALLEY_ID: (0, -24),
        VERDANT_WILDERNESS_ID: (-17, -17),
        THUNDER_MARSH_STEPPE_ID: (-24, 0),
        NORTHERN_ABYSS_SNOWFIELD_ID: (-17, 17),
        BROKEN_PILLAR_RELIC_ID: (0, 52),
        KUNLUN_SKY_RUINS_ID: (0, -52),
        MYRIAD_SWORD_TOMB_ID: (-72, 0),
        HEAVENLY_CRAFT_RELIC_ID: (72, 0),
        RETURNING_RUIN_ABYSS_ID: (0, -88),
        PERSON_WEST_LOCATION_ID: (-12, 36),
        PERSON_EAST_LOCATION_ID: (0, 36),
        PERSON_NORTH_LOCATION_ID: (12, 36),
    },
)


WORLD_MAP_ANCHORS = (
    *TAIXUAN_LAYOUT.values(),
    *MAGIC_LAYOUT.values(),
    *STELLAR_RING_LAYOUT.values(),
)


__all__ = [
    "MAGIC_LAYOUT",
    "STELLAR_RING_LAYOUT",
    "TAIXUAN_LAYOUT",
    "WORLD_MAP_ANCHORS",
]
