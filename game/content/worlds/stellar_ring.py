"""星环界真实世界身份与地点功能绑定。"""

from game.core.gameplay import WorldDefinition, WorldLocationBinding

from ..catalog.companion import STELLAR_RING_PEOPLE
from ..catalog.exploration import EXPLORATION_REGIONS
from ..catalog.world import (
    LOCATION_FUNCTION_CITY,
    LOCATION_FUNCTION_COMPANION_PERSON,
    LOCATION_FUNCTION_EXPLORATION,
    STARTING_CITY_ID,
    STELLAR_RING_WORLD_ID,
    STELLAR_RING_WORLD_SPACE_ID,
)
from ..world_skins import STELLAR_RING_SKIN_ID
from .layouts import STELLAR_RING_LAYOUT


STELLAR_RING_WORLD = WorldDefinition(
    STELLAR_RING_WORLD_ID,
    STELLAR_RING_WORLD_SPACE_ID,
    STELLAR_RING_SKIN_ID,
    STELLAR_RING_LAYOUT[STARTING_CITY_ID].id,
)
STELLAR_RING_LOCATION_BINDINGS = (
    WorldLocationBinding(
        STELLAR_RING_WORLD_ID,
        STELLAR_RING_LAYOUT[STARTING_CITY_ID].id,
        LOCATION_FUNCTION_CITY,
        display_ref=STARTING_CITY_ID,
    ),
    *(
        WorldLocationBinding(
            STELLAR_RING_WORLD_ID,
            STELLAR_RING_LAYOUT[value.location_id].id,
            LOCATION_FUNCTION_EXPLORATION,
            value.id,
            display_ref=value.location_id,
        )
        for value in EXPLORATION_REGIONS
    ),
    *(
        WorldLocationBinding(
            STELLAR_RING_WORLD_ID,
            STELLAR_RING_LAYOUT[value.location_id].id,
            LOCATION_FUNCTION_COMPANION_PERSON,
            value.id,
            display_ref=value.location_id,
        )
        for value in STELLAR_RING_PEOPLE
    ),
)


__all__ = ["STELLAR_RING_LOCATION_BINDINGS", "STELLAR_RING_WORLD"]
