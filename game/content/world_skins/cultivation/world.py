"""基础修仙界的世界空间与地点展示。"""

from game.core.gameplay import SkinEntry

from ...catalog import PRIMARY_WORLD_SPACE_ID, STARTING_CITY_ID


CULTIVATION_WORLD_ENTRIES = {
    PRIMARY_WORLD_SPACE_ID: SkinEntry(name="太玄界"),
    STARTING_CITY_ID: SkinEntry(
        name="太玄仙城",
        description="坐落于世界原点的第一座仙城。",
        icon="🏯",
    ),
}


__all__ = ["CULTIVATION_WORLD_ENTRIES"]
