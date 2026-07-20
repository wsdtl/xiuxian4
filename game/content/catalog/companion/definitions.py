"""首批两个世界的伙伴物种、秘境和公共显示词。"""

from game.core.gameplay import (
    COMBAT_ATTACK,
    COMBAT_DEFENSE,
    COMBAT_SPEED,
    HEALTH_MAXIMUM,
    SPIRIT_MAXIMUM,
    ContentDefinition,
)

from ..foundation import (
    COMMON_QUALITY_ID,
    EPIC_QUALITY_ID,
    FINE_QUALITY_ID,
    LEGENDARY_QUALITY_ID,
    RARE_QUALITY_ID,
)
from .models import (
    CompanionBalance,
    CompanionCatalog,
    CompanionSanctuaryDefinition,
    CompanionSpeciesDefinition,
)


COMPANION_TERM_ID = "term.companion"
COMPANION_SANCTUARY_TERM_ID = "term.companion_sanctuary"
COMPANION_BIND_ACTION_ID = "term.companion_bind"
COMPANION_RELEASE_ACTION_ID = "term.companion_release"
COMPANION_DISPLAY_DEFINITIONS = tuple(
    ContentDefinition(value, "content.companion_term")
    for value in (
        COMPANION_TERM_ID,
        COMPANION_SANCTUARY_TERM_ID,
        COMPANION_BIND_ACTION_ID,
        COMPANION_RELEASE_ACTION_ID,
    )
)

CULTIVATION_SKIN_ID = "skin.cultivation"
MAGIC_SKIN_ID = "skin.magic"


def _attributes(health: float, spirit: float, attack: float, defense: float, speed: float):
    return {
        HEALTH_MAXIMUM: health,
        SPIRIT_MAXIMUM: spirit,
        COMBAT_ATTACK: attack,
        COMBAT_DEFENSE: defense,
        COMBAT_SPEED: speed,
    }


def _species(
    key: str,
    skin_id: str,
    name: str,
    description: str,
    role: str,
    multipliers,
    core: str,
    traits: tuple[str, ...],
    weight: int = 100,
) -> CompanionSpeciesDefinition:
    return CompanionSpeciesDefinition(
        f"companion.{skin_id.removeprefix('skin.')}.{key}",
        skin_id,
        name,
        description,
        role,
        multipliers,
        f"enemy.behavior.{core}",
        tuple(f"enemy.behavior.{value}" for value in traits),
        weight,
    )


CULTIVATION_COMPANIONS = (
    _species("qingluan", CULTIVATION_SKIN_ID, "青鸾", "栖于云海灵木的青羽神鸟。", "swift", _attributes(0.82, 1.05, 1.08, 0.78, 1.18), "rapid_attack", ("follow_up", "evasion", "burn"), 90),
    _species("xuangui", CULTIVATION_SKIN_ID, "玄龟", "背负玄纹、寿元悠长的水泽灵兽。", "guardian", _attributes(1.30, 1.00, 0.72, 1.35, 0.72), "block", ("shield", "taunt", "regeneration"), 110),
    _species("suanni", CULTIVATION_SKIN_ID, "狻猊", "喜烟好坐、声震山林的龙属异兽。", "assault", _attributes(1.05, 0.92, 1.22, 1.02, 0.96), "heavy_strike", ("burn", "sunder", "counter"), 75),
    _species("chenghuang", CULTIVATION_SKIN_ID, "乘黄", "背生双角、踏风越岭的古老瑞兽。", "swift", _attributes(0.88, 1.05, 0.98, 0.82, 1.30), "evasion", ("rapid_attack", "combo", "slow"), 105),
    _species("tianlu", CULTIVATION_SKIN_ID, "天禄", "辟邪纳福、守望灵脉的独角灵兽。", "guardian", _attributes(1.12, 1.08, 0.90, 1.18, 0.90), "shield", ("block", "counter", "death_guard"), 95),
    _species("jade_rabbit", CULTIVATION_SKIN_ID, "月宫玉兔", "饮月华而生、善辨灵药的白兔。", "sustain", _attributes(0.86, 1.28, 0.82, 0.80, 1.16), "regeneration", ("evasion", "slow", "sleep"), 125),
    _species("dangkang", CULTIVATION_SKIN_ID, "当康", "丰年将至时现身田野的有牙瑞兽。", "sustain", _attributes(1.18, 0.92, 0.94, 1.10, 0.88), "lifesteal", ("regeneration", "heavy_armor", "taunt"), 120),
    _species("mengji", CULTIVATION_SKIN_ID, "孟极", "身披白纹、善伏于山林阴影的异兽。", "control", _attributes(0.92, 1.02, 1.05, 0.84, 1.22), "freeze", ("evasion", "follow_up", "slow"), 100),
)

MAGIC_COMPANIONS = (
    _species("griffin", MAGIC_SKIN_ID, "星辉狮鹫", "翼羽映照星光的高山狮鹫。", "swift", _attributes(0.96, 0.92, 1.14, 0.88, 1.18), "follow_up", ("rapid_attack", "splash", "evasion"), 90),
    _species("unicorn", MAGIC_SKIN_ID, "银角独角兽", "能感知恶意并净化魔力乱流的圣洁生灵。", "sustain", _attributes(1.02, 1.25, 0.84, 0.96, 1.04), "regeneration", ("shield", "evasion", "counter"), 90),
    _species("phoenix_chick", MAGIC_SKIN_ID, "余烬雏凤", "从不灭余烬中孵化的幼年凤凰。", "assault", _attributes(0.88, 1.12, 1.18, 0.78, 1.12), "burn", ("death_guard", "area_attack", "charged_burst"), 65),
    _species("hellhound", MAGIC_SKIN_ID, "冥途猎犬", "巡游冥途边界、追逐灵魂气息的黑犬。", "assault", _attributes(1.02, 0.88, 1.16, 0.92, 1.08), "execute", ("bleed", "lifesteal", "follow_up"), 105),
    _species("wyvern", MAGIC_SKIN_ID, "翡翠翼蜥", "盘旋峡谷、吐出腐蚀毒雾的双足飞兽。", "control", _attributes(0.94, 1.06, 1.04, 0.88, 1.14), "poison", ("splash", "evasion", "slow"), 110),
    _species("flower_sprite", MAGIC_SKIN_ID, "晨露花精", "诞生于第一滴晨露中的微小自然精灵。", "sustain", _attributes(0.76, 1.35, 0.74, 0.72, 1.26), "sleep", ("regeneration", "evasion", "slow"), 130),
    _species("gargoyle", MAGIC_SKIN_ID, "符文石像鬼", "刻满守护符文、夜间苏醒的石翼造物。", "guardian", _attributes(1.22, 0.90, 0.84, 1.30, 0.78), "heavy_armor", ("block", "counter", "shield"), 115),
    _species("thunderbird", MAGIC_SKIN_ID, "苍穹雷鸟", "振翼时牵动雷云的远古巨鸟后裔。", "control", _attributes(0.90, 1.08, 1.12, 0.80, 1.22), "stun", ("area_attack", "rapid_attack", "volatile"), 85),
)

COMPANION_BALANCE = CompanionBalance(
    roster_capacity=30,
    quality_weights={
        COMMON_QUALITY_ID: 550,
        FINE_QUALITY_ID: 280,
        RARE_QUALITY_ID: 120,
        EPIC_QUALITY_ID: 40,
        LEGENDARY_QUALITY_ID: 10,
    },
    aptitude_budgets={
        COMMON_QUALITY_ID: 360,
        FINE_QUALITY_ID: 380,
        RARE_QUALITY_ID: 400,
        EPIC_QUALITY_ID: 420,
        LEGENDARY_QUALITY_ID: 440,
    },
)

COMPANION_CATALOG = CompanionCatalog(
    (*CULTIVATION_COMPANIONS, *MAGIC_COMPANIONS),
    (
        CompanionSanctuaryDefinition(
            "companion_sanctuary.cultivation",
            CULTIVATION_SKIN_ID,
            "万灵秘境",
            "隐于太玄界灵脉夹层中的古老生灵栖地。",
            tuple(value.id for value in CULTIVATION_COMPANIONS),
        ),
        CompanionSanctuaryDefinition(
            "companion_sanctuary.magic",
            MAGIC_SKIN_ID,
            "幻兽庭",
            "漂流在魔力潮汐间、收容异界生灵的隐秘庭域。",
            tuple(value.id for value in MAGIC_COMPANIONS),
        ),
    ),
    COMPANION_BALANCE,
)


__all__ = [name for name in globals() if not name.startswith("_")]
