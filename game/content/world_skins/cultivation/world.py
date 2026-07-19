"""太玄界的世界空间与地点展示。"""

from game.core.gameplay import SkinEntry

from ...catalog.world import (
    BLACK_WIND_RAVINE_ID,
    BROKEN_PILLAR_RELIC_ID,
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
)


CULTIVATION_WORLD_ENTRIES = {
    PRIMARY_WORLD_SPACE_ID: SkinEntry(name="太玄界"),
    STARTING_CITY_ID: SkinEntry(
        name="太玄仙城",
        description="坐落于世界原点的第一座仙城。",
        icon="🏯",
    ),
    GREEN_CLOUD_PLAIN_ID: SkinEntry(name="青云原", description="仙城外灵气平缓的辽阔原野。", icon="🌿"),
    SUNSET_RIDGE_ID: SkinEntry(name="栖霞岭", description="霞光终日不散的连绵山岭。", icon="⛰"),
    BLACK_WIND_RAVINE_ID: SkinEntry(name="黑风涧", description="阴风盘旋、妖影出没的深涧。", icon="🌫"),
    MIRROR_LAKE_MARSH_ID: SkinEntry(name="镜湖泽", description="水镜与迷泽交错的古老湿地。", icon="🌊"),
    SCARLET_FLAME_VALLEY_ID: SkinEntry(name="赤炎谷", description="地火喷涌、赤石遍布的炎谷。", icon="🔥"),
    VERDANT_WILDERNESS_ID: SkinEntry(name="苍梧林", description="巨木遮天、灵兽潜行的古林。", icon="🌲"),
    THUNDER_MARSH_STEPPE_ID: SkinEntry(name="雷泽古原", description="雷云低垂、古兽留痕的荒原。", icon="⚡"),
    NORTHERN_ABYSS_SNOWFIELD_ID: SkinEntry(name="北冥雪域", description="寒潮不息、冰妖盘踞的雪域。", icon="❄"),
    BROKEN_PILLAR_RELIC_ID: SkinEntry(name="不周遗境", description="天柱崩裂后遗留的破碎险境。", icon="🗿"),
    KUNLUN_SKY_RUINS_ID: SkinEntry(name="昆仑天墟", description="接近天门、遗迹遍布的高天废墟。", icon="☁"),
    MYRIAD_SWORD_TOMB_ID: SkinEntry(name="万剑冢", description="无数古剑与执念沉眠的兵冢。", icon="⚔"),
    HEAVENLY_CRAFT_RELIC_ID: SkinEntry(name="天工遗府", description="上古机关与护宝傀儡守卫的遗府。", icon="⚙"),
    RETURNING_RUIN_ABYSS_ID: SkinEntry(name="归墟魔渊", description="精英妖魔与灾主汇聚的高危深渊。", icon="☄"),
}


__all__ = ["CULTIVATION_WORLD_ENTRIES"]
