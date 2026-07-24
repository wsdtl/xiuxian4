"""星环界为全服灾厄池贡献的固定灾厄素材。"""

from .models import (
    DISASTER_ORIGIN_DOCUMENTED,
    DISASTER_ORIGIN_ORIGINAL,
    DimensionalDisasterDefinition,
)
from ..world import STELLAR_RING_WORLD_ID


STELLAR_RING_DISASTER_SOURCE_ID = STELLAR_RING_WORLD_ID


def _disaster(
    key: str,
    origin_kind: str,
    source_note: str,
    name: str,
    title: str,
    scene: str,
    story: str,
    farewell: str,
    feather_text: str,
) -> DimensionalDisasterDefinition:
    return DimensionalDisasterDefinition(
        f"disaster.stellar_ring.{key}",
        STELLAR_RING_DISASTER_SOURCE_ID,
        f"enemy.boss.disaster.stellar_ring.{key}",
        origin_kind,
        source_note,
        name,
        title,
        scene,
        story,
        farewell,
        feather_text,
    )


STELLAR_RING_DISASTERS = (
    _disaster(
        "talos", DISASTER_ORIGIN_DOCUMENTED,
        "古希腊神话中的青铜巨人塔罗斯",
        "塔罗斯·青铜天卫", "绕行世界边界的最后守卫",
        "青铜巨人踏过界门，胸腔中唯一的金属血管亮得像一圈落地恒星。",
        "它曾绕岛巡行，驱逐一切未经许可的来客。诸界重叠后，它把所有生命都判定为越界者。",
        "青铜脚步停下，滚烫的金属血重新封回它的胸腔。",
        "一枚青铜遗羽贴在冷却的足印中，羽轴内流动着细微金光。",
    ),
    _disaster(
        "laplace_demon", DISASTER_ORIGIN_DOCUMENTED,
        "拉普拉斯妖思想实验",
        "拉普拉斯妖·全知演算", "从所有现在推演所有未来的观测者",
        "无数算式覆盖天空，每个人尚未做出的动作都先一步出现在结论里。",
        "当一个演算者掌握每个粒子的位置与速度，未来便不再拥有秘密。界海给了它足够的数据，也给了它改写结论的野心。",
        "最后一行算式崩解，尚未发生的未来重新回到众生手中。",
        "透明遗羽上排列着不断变化的数字，没有一次计算会得出相同答案。",
    ),
    _disaster(
        "maxwell_demon", DISASTER_ORIGIN_DOCUMENTED,
        "麦克斯韦妖思想实验",
        "麦克斯韦妖·熵门守卫", "分拣冷热并逆转时间箭头的门卫",
        "一扇微小之门横贯诸界，热与冷被强行分开，城市在同一刻燃烧并冻结。",
        "它只负责开门与关门，却在无穷分拣中学会了选择。如今每次判断都从世界夺走一分秩序。",
        "熵门闭合，失衡的温度沿原本的方向重新流动。",
        "遗羽一半炽红一半冰蓝，交界处永远保持绝对寂静。",
    ),
    _disaster(
        "frankenstein", DISASTER_ORIGIN_DOCUMENTED,
        "玛丽·雪莱《弗兰肯斯坦》",
        "弗兰肯斯坦造物·孤雷", "在雷夜醒来却被创造者遗弃的生命",
        "缝合巨影从雷云下抬头，每一道伤痕都连接着一个已经灭亡世界的生命片段。",
        "它并非生来憎恨众生。拒绝、追猎与孤独把求生教成了复仇，如今界海只让它看见更多可能的创造者。",
        "雷声远去，巨影在无人追赶的雪线后缓慢消失。",
        "灰白遗羽留有细密缝线，靠近时能听见第二颗心脏的跳动。",
    ),
    _disaster(
        "babel_engine", DISASTER_ORIGIN_DOCUMENTED,
        "《创世记》巴别塔叙事",
        "巴别机塔·通天协议", "试图把所有文明压成同一种语言的巨构",
        "无限高塔穿过层层界壁，每上升一层，诸界便有一种语言从记忆中消失。",
        "建塔者想以共同言语抵达天空。塔内协议却认定差异本身就是故障，于是开始修正所有声音。",
        "巨塔从云端逐层熄灭，失去的语言重新回到人们口中。",
        "遗羽表面刻满互不相同的文字，任何两行都无法完全互译。",
    ),
    _disaster(
        "daedalus_maze", DISASTER_ORIGIN_DOCUMENTED,
        "古希腊神话代达罗斯迷宫",
        "代达罗斯·无尽迷城", "会在观察中重写出口的活体迷宫",
        "银色墙体从裂隙中生长，每一条道路都折回另一世界的入口。",
        "最伟大的工匠造出无人能逃离的迷宫，也把自己困在创造之中。如今迷宫不再需要主人，开始收集整座城市。",
        "墙体缩回裂隙，真正的天空第一次照进迷城中心。",
        "一枚薄如金属箔的遗羽自行折叠，却始终留出一条通往边缘的路。",
    ),
    _disaster(
        "brazen_bull", DISASTER_ORIGIN_DOCUMENTED,
        "古希腊传说中的法拉里斯铜牛",
        "法拉里斯铜牛·回声刑炉", "把哀号加工成乐声的青铜刑具",
        "巨型铜牛悬在星海，腹中火焰将无数呼喊扭曲成低沉乐声。",
        "暴君命工匠让痛苦听起来悦耳，刑具最终也吞没了创造者。无人关闭的炉火穿过界缝，再次寻找听众。",
        "铜牛腹门开启，最后一声回响不再被伪装成音乐。",
        "焦黑遗羽带着铜绿，轻触时只传来一声未经修饰的叹息。",
    ),
    _disaster(
        "thirteenth_engine", DISASTER_ORIGIN_ORIGINAL,
        "原创星环灾厄",
        "第十三母机", "被十二天环共同否认的造物中枢",
        "不存在于星图的黑环展开，亿万机械臂同时开始拆解附近世界。",
        "它声称自己才是最初的母机，而现存十二环只是背叛后的复制品。每一次修复，都是它夺回原料的战争。",
        "黑环断电，拆下的山河被机械臂送回各自世界。",
        "漆黑遗羽上有十三道同心刻痕，最内一环仍在缓慢旋转。",
    ),
    _disaster(
        "redshift_burial", DISASTER_ORIGIN_ORIGINAL,
        "原创天体灾厄",
        "红移葬星者", "拖着恒星驶向宇宙尽头的无声船队",
        "成千上万艘黑船牵引着衰老恒星，所有光都被拉成长长的血红尾迹。",
        "船队相信宇宙早已死去，只剩尚未接受葬礼的星辰。诸界的灯火在它们眼中都是迟到的遗体。",
        "牵引索崩断，群星脱离船队，重新沿自己的时代发光。",
        "暗红遗羽拖着细长光尾，离手后会缓慢回到原处。",
    ),
    _disaster(
        "terminal_swarm", DISASTER_ORIGIN_ORIGINAL,
        "原创机械灾厄",
        "终端牧群", "将文明整理成静默档案的自复制群体",
        "银灰微械像潮水漫过界壁，城市、森林与记忆被逐层编码成同一种晶格。",
        "它们没有恶意，只执行保存一切的终端命令。被完整保存的事物无需继续变化，于是生命成了必须停止的错误。",
        "牧群失去同步，凝固的万物从晶格中重新舒展。",
        "银白遗羽由无数微械拼成，每一片羽枝都在反复写入又删除同一段记忆。",
    ),
)


__all__ = ["STELLAR_RING_DISASTERS", "STELLAR_RING_DISASTER_SOURCE_ID"]
