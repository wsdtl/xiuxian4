"""世界空间与地点名录的稳定入口。"""

from .definitions import (
    CHARACTER_PRESENCE_KIND_ID,
    PRIMARY_WORLD_SPACE_ID,
    STARTING_CITY_ID,
    coordinate_token,
    validate_location_coordinate_id,
)


__all__ = [name for name in globals() if not name.startswith("_")]
