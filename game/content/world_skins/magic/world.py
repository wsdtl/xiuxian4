"""魔法世界的世界空间与地点展示。"""

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
    PERSON_EAST_LOCATION_ID,
    PERSON_NORTH_LOCATION_ID,
    PERSON_WEST_LOCATION_ID,
    MAGIC_WORLD_SPACE_ID,
    RETURNING_RUIN_ABYSS_ID,
    SCARLET_FLAME_VALLEY_ID,
    STARTING_CITY_ID,
    SUNSET_RIDGE_ID,
    THUNDER_MARSH_STEPPE_ID,
    VERDANT_WILDERNESS_ID,
    TAIXUAN_WORLD_SPACE_ID,
    STELLAR_RING_WORLD_SPACE_ID,
)


MAGIC_WORLD_ENTRIES = {
    TAIXUAN_WORLD_SPACE_ID: SkinEntry(name="太玄界域"),
    MAGIC_WORLD_SPACE_ID: SkinEntry(name="星辉界域"),
    STELLAR_RING_WORLD_SPACE_ID: SkinEntry(name="星环界域"),
    STARTING_CITY_ID: SkinEntry(
        name="星辉王城",
        description="坐落于世界原点的第一座王城。",
        icon="🏰",
    ),
    GREEN_CLOUD_PLAIN_ID: SkinEntry(name="翠风平原", description="王城外微风常驻的青翠原野。", icon="🌿"),
    SUNSET_RIDGE_ID: SkinEntry(name="晨曦丘陵", description="晨光照耀的连绵丘陵。", icon="⛰"),
    BLACK_WIND_RAVINE_ID: SkinEntry(name="黑风峡谷", description="阴影与怪物盘踞的狭长峡谷。", icon="🌫"),
    MIRROR_LAKE_MARSH_ID: SkinEntry(name="镜湖沼泽", description="幻象水面覆盖的危险沼泽。", icon="🌊"),
    SCARLET_FLAME_VALLEY_ID: SkinEntry(name="熔火峡谷", description="岩浆与火元素涌动的灼热峡谷。", icon="🔥"),
    VERDANT_WILDERNESS_ID: SkinEntry(name="翡翠森林", description="远古树灵守望的苍翠密林。", icon="🌲"),
    THUNDER_MARSH_STEPPE_ID: SkinEntry(name="风暴荒原", description="雷暴永不停歇的开阔荒原。", icon="⚡"),
    NORTHERN_ABYSS_SNOWFIELD_ID: SkinEntry(name="永冬冻土", description="冰霜魔物游荡的北境冻土。", icon="❄"),
    BROKEN_PILLAR_RELIC_ID: SkinEntry(name="泰坦遗境", description="远古泰坦战争留下的破碎遗境。", icon="🗿"),
    KUNLUN_SKY_RUINS_ID: SkinEntry(name="天穹神域", description="漂浮遗迹接近诸神天门的高空领域。", icon="☁"),
    MYRIAD_SWORD_TOMB_ID: SkinEntry(name="英灵兵冢", description="历代英雄武装沉眠的古老墓园。", icon="⚔"),
    HEAVENLY_CRAFT_RELIC_ID: SkinEntry(name="泰坦工坊", description="远古铸造机关仍在运转的神工遗址。", icon="⚙"),
    RETURNING_RUIN_ABYSS_ID: SkinEntry(name="混沌深渊", description="精英魔物和古老灾厄汇聚的深渊。", icon="☄"),
    PERSON_WEST_LOCATION_ID: SkinEntry(name="雾灯小屋", description="一盏银灯终年照亮林间薄雾。", icon="⌂"),
    PERSON_EAST_LOCATION_ID: SkinEntry(name="白塔驿亭", description="废弃驿道旁仍有人看守的白石亭。", icon="⌂"),
    PERSON_NORTH_LOCATION_ID: SkinEntry(name="星象高台", description="记录群星轨迹与界海潮汐的高台。", icon="⌂"),
}


__all__ = ["MAGIC_WORLD_ENTRIES"]
