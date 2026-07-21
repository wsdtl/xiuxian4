"""星环界的世界空间与地点展示。"""

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
    STELLAR_RING_WORLD_SPACE_ID,
    RETURNING_RUIN_ABYSS_ID,
    SCARLET_FLAME_VALLEY_ID,
    STARTING_CITY_ID,
    SUNSET_RIDGE_ID,
    THUNDER_MARSH_STEPPE_ID,
    VERDANT_WILDERNESS_ID,
    TAIXUAN_WORLD_SPACE_ID,
)


STELLAR_RING_WORLD_ENTRIES = {
    TAIXUAN_WORLD_SPACE_ID: SkinEntry(name="太玄界域"),
    MAGIC_WORLD_SPACE_ID: SkinEntry(name="魔法界域"),
    STELLAR_RING_WORLD_SPACE_ID: SkinEntry(name="星环界域"),
    STARTING_CITY_ID: SkinEntry(
        name="环心天城",
        description="悬于人造恒星近轨的中枢城市，十二天环由此校准。",
        icon="🏰",
    ),
    GREEN_CLOUD_PLAIN_ID: SkinEntry(name="生态穹原", description="第一天环维持的广阔生态穹顶。", icon="🌿"),
    SUNSET_RIDGE_ID: SkinEntry(name="曙光脊轨", description="沿恒星晨昏线延伸的高架轨道。", icon="⛰"),
    BLACK_WIND_RAVINE_ID: SkinEntry(name="静默裂廊", description="通讯与照明同时失效的维护裂廊。", icon="🌫"),
    MIRROR_LAKE_MARSH_ID: SkinEntry(name="镜海冷却区", description="覆盖环城底部的银色冷却海。", icon="🌊"),
    SCARLET_FLAME_VALLEY_ID: SkinEntry(name="赤炉峡带", description="废热炉群昼夜喷吐炽红等离子流。", icon="🔥"),
    VERDANT_WILDERNESS_ID: SkinEntry(name="森环培育层", description="失去管理者后自行演化的巨型培育层。", icon="🌲"),
    THUNDER_MARSH_STEPPE_ID: SkinEntry(name="脉冲荒原", description="高压能源网周期性扫过的空旷环面。", icon="⚡"),
    NORTHERN_ABYSS_SNOWFIELD_ID: SkinEntry(name="零温封存带", description="古代档案与危险样本沉睡的低温区域。", icon="❄"),
    BROKEN_PILLAR_RELIC_ID: SkinEntry(name="断环遗构", description="一段坠毁天环形成的巨型结构废墟。", icon="🗿"),
    KUNLUN_SKY_RUINS_ID: SkinEntry(name="天穹观测阵", description="仍在记录界海外侧信号的高空阵列。", icon="☁"),
    MYRIAD_SWORD_TOMB_ID: SkinEntry(name="兵装墓库", description="封存历代制式兵装与战斗记录的禁库。", icon="⚔"),
    HEAVENLY_CRAFT_RELIC_ID: SkinEntry(name="造物母厂", description="无人值守却仍在制造未知构件的母厂。", icon="⚙"),
    RETURNING_RUIN_ABYSS_ID: SkinEntry(name="第十三暗环", description="不在官方星图中的失控环带。", icon="☄"),
    PERSON_WEST_LOCATION_ID: SkinEntry(name="七码头", description="旧航标堆满泊位的边缘码头。", icon="⌂"),
    PERSON_EAST_LOCATION_ID: SkinEntry(name="重构工站", description="专门修复断环结构的独立工程站。", icon="⌂"),
    PERSON_NORTH_LOCATION_ID: SkinEntry(name="零弦观测台", description="监听人造恒星内部脉冲的孤立平台。", icon="⌂"),
}


__all__ = ["STELLAR_RING_WORLD_ENTRIES"]
