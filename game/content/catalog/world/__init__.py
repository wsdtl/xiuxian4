"""世界空间与地点名录的稳定入口。"""

from .definitions import (
    ALL_WORLD_LOCATIONS,
    BLACK_WIND_RAVINE_ID,
    BROKEN_PILLAR_RELIC_ID,
    CHARACTER_PRESENCE_KIND_ID,
    EXPLORATION_LOCATIONS,
    GREEN_CLOUD_PLAIN_ID,
    HEAVENLY_CRAFT_RELIC_ID,
    KUNLUN_SKY_RUINS_ID,
    MIRROR_LAKE_MARSH_ID,
    MYRIAD_SWORD_TOMB_ID,
    NORTHERN_ABYSS_SNOWFIELD_ID,
    PRIMARY_WORLD_SPACE_ID,
    RETURNING_RUIN_ABYSS_ID,
    SCARLET_FLAME_VALLEY_ID,
    STARTING_CITY_ID,
    SUNSET_RIDGE_ID,
    THUNDER_MARSH_STEPPE_ID,
    VERDANT_WILDERNESS_ID,
    coordinate_token,
    validate_location_coordinate_id,
)


__all__ = [name for name in globals() if not name.startswith("_")]
