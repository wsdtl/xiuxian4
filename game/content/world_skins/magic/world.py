"""魔法世界的世界空间与地点展示。"""

from game.core.gameplay import SkinEntry

from ...catalog import PRIMARY_WORLD_SPACE_ID, STARTING_CITY_ID


MAGIC_WORLD_ENTRIES = {
    PRIMARY_WORLD_SPACE_ID: SkinEntry(name="星辉大陆"),
    STARTING_CITY_ID: SkinEntry(
        name="星辉王城",
        description="坐落于世界原点的第一座王城。",
        icon="🏰",
    ),
}


__all__ = ["MAGIC_WORLD_ENTRIES"]
