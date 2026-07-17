"""魔法世界的正式武器展示；规则蓝图不保存玩家可见文本。"""

from game.core.gameplay import SkinEntry

from ...catalog import STARTER_WEAPON_ID, STARTER_WEAPON_ITEM_ID
from ...catalog.weapon.blueprints import WEAPON_BLUEPRINTS


_WEAPON_DISPLAY = {
    "mountain_cleaver": ("裂峰巨刃", "重击后削弱防御"),
    "dawn_bane": ("破晓圣剑", "目标越残血伤害越高"),
    "star_piercer": ("星界长枪", "穿盾攻击并提高暴击"),
    "war_breaker": ("征服战戟", "撼动高血量目标并延后行动"),
    "ember_brand": ("熔火魔刃", "重击点燃并波及邻位"),
    "storm_maul": ("雷霆战锤", "双段雷击并尝试眩晕"),
    "blood_reaper": ("猩红收割者", "自身越残血越凶并吸取生命"),
    "judgement_bow": ("审判长弓", "真实伤害击败后获得节奏收益"),
    "flash_blade": ("闪光细剑", "三段攻击后提升速度"),
    "gearshade": ("机巧伞刃", "攻守两段并获得短暂防御"),
    "moonstep_twins": ("月步双刃", "双击后请求一次受限额外行动"),
    "gale_ring": ("风暴轮刃", "低消耗攻击并延迟随机目标"),
    "blink_fang": ("瞬影刺", "必中式突刺后提高闪避"),
    "continuum_rod": ("时序法杖", "重击后以击败刷新冷却"),
    "soul_chaser": ("灵魂锁链", "追击残血并削减速度"),
    "comet_shuttle": ("彗星飞刃", "多段攻击以暴击触发回响"),
    "plague_banner": ("瘟疫战旗", "群体施毒并叠加疫病印记"),
    "cinder_lash": ("炽焰长鞭", "灼烧邻位并降低速度"),
    "hemorrhage_nail": ("放血骨钉", "流血会在残血目标上加速收割"),
    "wither_fan": ("凋零魔扇", "毒蚀同时削弱防御"),
    "heart_pyrelamp": ("心火提灯", "燃烧生命并抽取魔力"),
    "frost_marrow_needle": ("霜髓法针", "冰霜伤害累积并尝试冻结"),
    "blight_staff": ("枯疫法杖", "群毒削弱目标攻击"),
    "ashen_crucible": ("灰烬熔炉", "叠印后引爆并重新点燃"),
    "hidden_edge_coffer": ("秘刃魔匣", "先藏锋叠印再一次释放"),
    "mana_devourer": ("噬魔之瓶", "抽取魔力并转为恢复"),
    "blade_well": ("刃魂之井", "攻击积累刃势强化后续爆发"),
    "aether_orb": ("奥能法球", "消耗魔力爆发并获得护盾"),
    "fate_ledger": ("命运账册", "以血换伤并短暂保命"),
    "soulburn_bell": ("焚魂魔钟", "高魔力消耗换取行动爆发"),
    "equilibrium_chalice": ("均衡圣杯", "根据生命与魔力缺口自适应恢复"),
    "formless_wheel": ("无形法轮", "真实伤害并清除目标增益"),
    "mountain_seal": ("泰坦战印", "重击后获得厚重护盾"),
    "verdant_staff": ("翠生法杖", "稳定攻击并持续自愈"),
    "mirror_blade": ("镜像反刃", "攻击后以反击回应受伤"),
    "aegis_parasol": ("圣辉华盖", "双段攻击后提高格挡"),
    "lifebond_chain": ("生命锁链", "高额伤害按实际伤害恢复"),
    "phoenix_plume": ("不死鸟羽", "自损追猎并以击败恢复"),
    "tortoise_bulwark": ("磐甲壁垒", "低伤攻击换取单次伤害封顶"),
    "void_mirror": ("虚空魔镜", "真实伤害后获得短暂免疫"),
    "soul_bell": ("镇魂银铃", "快速攻击并稳定尝试眩晕"),
    "binding_codex": ("封缚法典", "施加束缚印并强制目标回应"),
    "dream_flute": ("梦雾长笛", "群体低伤并尝试催眠"),
    "winter_rod": ("永冬权杖", "冰霜伤害邻位并延长控制节奏"),
    "dragon_bind": ("巨龙锁链", "重击后将目标锁定于自身"),
    "gravity_tablet": ("重力石碑", "压制群体高血目标行动进度"),
    "discord_harp": ("失序竖琴", "乱击并削弱随机目标攻击"),
    "null_blade": ("奥术断绝者", "真实伤害并延长目标冷却"),
    "realm_fan": ("王权战扇", "群体攻击并统一削防"),
    "ninefold_bow": ("九星战弓", "三箭随机散射并积累暴击"),
    "cloud_piercer": ("天穹长枪", "穿盾贯击并延迟邻位"),
    "tide_breaker": ("潮汐粉碎者", "群体震击并低概率眩晕"),
    "rift_blade": ("空间裂刃", "真实溅射并留下裂隙印记"),
    "prism_array": ("棱镜魔盘", "一次攻击同时结算火、霜、真实三相伤害"),
    "dragon_coil": ("翔龙长鞭", "邻位双击并降低速度"),
    "astral_board": ("星界棋盘", "全场布印并按层数引爆"),
    "blade_array": ("刃阵卷轴", "群体剑阵以暴击追加回响"),
    "shadow_thread": ("暗影傀线", "提高闪避并在闪避后反击"),
    "armament_talisman": ("兵魂符印", "自损换取高伤与额外行动"),
    "thunder_warrant": ("雷域法令", "暴击时追加雷击和眩晕"),
    "blood_pact": ("鲜血契约", "残血增伤并反击来袭者"),
    "phantom_banner": ("幻影军旗", "双重幻击后进入闪避窗口"),
    "myriad_vault": ("万刃宝库", "群体多段攻击积累自身刃势"),
    "sentinel_sigill": ("守望者徽记", "获得护盾并在破盾时反击"),
    "sevenfold_saber": ("七罪军刀", "三段杀招同时消耗自身生命"),
    "sacrifice_blade": ("献祭之刃", "以固定生命代价换取极高倍率"),
    "bloomblight_staff": ("荣枯法杖", "施毒与自愈形成枯荣循环"),
    "twinphase_edge": ("双相魔刃", "三相混合伤害并获得护盾"),
    "fate_die": ("命运魔骰", "每次攻击在低谷与高峰间波动"),
    "death_scribe": ("终命羽笔", "标记残血并逐次提高斩杀压力"),
    "defiant_spear": ("逆境长枪", "濒危时爆发并保留最后生命"),
    "samsara_wheel": ("轮回法轮", "真实群伤并以击败延续生命"),
}


def _build_weapon_entries() -> dict[str, SkinEntry]:
    blueprint_keys = {value.key for value in WEAPON_BLUEPRINTS}
    if set(_WEAPON_DISPLAY) != blueprint_keys:
        raise ValueError("魔法世界武器展示键必须完整覆盖正式武器蓝图")
    names = [value[0] for value in _WEAPON_DISPLAY.values()]
    if len(names) != len(set(names)):
        raise ValueError("魔法世界正式武器名称不能重复")
    entries = {
        STARTER_WEAPON_ITEM_ID: SkinEntry(name="王都守备剑原型", icon="⚔"),
        STARTER_WEAPON_ID: SkinEntry(
            name="王都守备剑",
            description="王都兵工坊配发给新晋冒险者的制式长剑。",
            icon="⚔",
        ),
    }
    for blueprint in WEAPON_BLUEPRINTS:
        name, description = _WEAPON_DISPLAY[blueprint.key]
        entries.update(
            {
                f"item.weapon.{blueprint.key}": SkinEntry(name=f"{name}原型", icon="⚔"),
                f"weapon.{blueprint.key}": SkinEntry(name=name, description=description, icon="⚔"),
                f"ability.weapon.{blueprint.key}": SkinEntry(name=f"{name}战技", description=description, icon="⚔"),
            }
        )
    return entries


MAGIC_WEAPON_ENTRIES = _build_weapon_entries()


__all__ = ["MAGIC_WEAPON_ENTRIES"]
