"""基础修仙界的正式武器展示；规则蓝图不保存玩家可见文本。"""

from game.core.gameplay import SkinEntry

from ...catalog import STARTER_WEAPON_ID, STARTER_WEAPON_ITEM_ID
from ...catalog.weapon.blueprints import WEAPON_BLUEPRINTS


_WEAPON_DISPLAY = {
    "mountain_cleaver": ("断岳天刀", "重击后削弱防御"),
    "dawn_bane": ("诛邪道剑", "目标越残血伤害越高"),
    "star_piercer": ("摘星神枪", "穿盾攻击并提高暴击"),
    "war_breaker": ("破军戟", "撼动高血量目标并延后行动"),
    "ember_brand": ("燎原刃", "重击点燃并波及邻位"),
    "storm_maul": ("玄雷锤", "双段雷击并尝试眩晕"),
    "blood_reaper": ("饮血镰", "自身越残血越凶并吸取血气"),
    "judgement_bow": ("天罚弓", "真实伤害击败后获得节奏收益"),
    "flash_blade": ("流光剑", "三段攻击后提升速度"),
    "gearshade": ("千机玄伞", "攻守两段并获得短暂防御"),
    "moonstep_twins": ("逐月双刃", "双击后请求一次受限额外行动"),
    "gale_ring": ("回风环", "低消耗攻击并延迟随机目标"),
    "blink_fang": ("惊鸿刺", "必中式突刺后提高闪避"),
    "continuum_rod": ("无间玄尺", "重击后以击败刷新冷却"),
    "soul_chaser": ("追魂索", "追击残血并削减速度"),
    "comet_shuttle": ("飞星梭", "多段攻击以暴击触发回响"),
    "plague_banner": ("万毒幡", "群体施毒并叠加毒印"),
    "cinder_lash": ("赤炼鞭", "灼烧邻位并降低速度"),
    "hemorrhage_nail": ("泣血钉", "流血会在残血目标上加速收割"),
    "wither_fan": ("蚀骨扇", "毒蚀同时削弱防御"),
    "heart_pyrelamp": ("焚心灯", "燃烧血气并抽取灵力"),
    "frost_marrow_needle": ("寒髓针", "寒伤累积并尝试冻结"),
    "blight_staff": ("幽腐杖", "群毒削弱目标攻击"),
    "ashen_crucible": ("劫灰炉", "叠印后引爆并重新点燃"),
    "hidden_edge_coffer": ("藏锋匣", "先藏锋叠印再一次释放"),
    "mana_devourer": ("吞灵宝葫", "抽取灵力并转为恢复"),
    "blade_well": ("养剑池", "攻击积累剑势强化后续爆发"),
    "aether_orb": ("聚元珠", "消耗灵力爆发并获得护盾"),
    "fate_ledger": ("逆命天书", "以血换伤并短暂保命"),
    "soulburn_bell": ("燃魂钟", "高灵力消耗换取行动爆发"),
    "equilibrium_chalice": ("乾坤玉斗", "根据血气与灵力缺口自适应恢复"),
    "formless_wheel": ("无相轮", "真实伤害并清除目标增益"),
    "mountain_seal": ("镇山印", "重击后获得厚重护盾"),
    "verdant_staff": ("回春杖", "稳定攻击并持续自愈"),
    "mirror_blade": ("镜返灵剑", "攻击后以反击回应受伤"),
    "aegis_parasol": ("渡厄伞", "双段攻击后提高格挡"),
    "lifebond_chain": ("同命仙锁", "高额伤害按实际伤害恢复"),
    "phoenix_plume": ("涅槃羽", "自损追猎并以击败恢复"),
    "tortoise_bulwark": ("玄龟甲", "低伤攻击换取单次伤害封顶"),
    "void_mirror": ("太虚镜", "真实伤害后获得短暂免疫"),
    "soul_bell": ("定魂铃", "快速攻击并稳定尝试眩晕"),
    "binding_codex": ("封神天榜", "施加束缚印并强制目标回应"),
    "dream_flute": ("眠云笛", "群体低伤并尝试催眠"),
    "winter_rod": ("冻天尺", "寒伤邻位并延长控制节奏"),
    "dragon_bind": ("缚龙索", "重击后将目标锁定于自身"),
    "gravity_tablet": ("镇岳碑", "压制群体高血目标行动进度"),
    "discord_harp": ("乱心琴", "乱击并削弱随机目标攻击"),
    "null_blade": ("禁法剑", "真实伤害并延长目标冷却"),
    "realm_fan": ("山河宝扇", "群体攻击并统一削防"),
    "ninefold_bow": ("九曜弓", "三箭随机散射并积累暴击"),
    "cloud_piercer": ("穿云枪", "穿盾贯击并延迟邻位"),
    "tide_breaker": ("震海锤", "群体震击并低概率眩晕"),
    "rift_blade": ("裂空刃", "真实溅射并留下裂隙印记"),
    "prism_array": ("万象盘", "一次攻击同时结算火、霜、真实三相伤害"),
    "dragon_coil": ("游龙鞭", "邻位双击并降低速度"),
    "astral_board": ("星罗棋", "全场布印并按层数引爆"),
    "blade_array": ("剑阵图", "群体剑阵以暴击追加回响"),
    "shadow_thread": ("影傀线", "提高闪避并在闪避后反击"),
    "armament_talisman": ("兵解符", "自损换取高伤与额外行动"),
    "thunder_warrant": ("雷池令", "暴击时追加雷击和眩晕"),
    "blood_pact": ("血契卷", "残血增伤并反击来袭者"),
    "phantom_banner": ("幻身幡", "双重幻击后进入闪避窗口"),
    "myriad_vault": ("万剑匣", "群体多段攻击积累自身剑势"),
    "sentinel_sigill": ("天兵仙令", "获得护盾并在破盾时反击"),
    "sevenfold_saber": ("七杀刀", "三段杀招同时消耗自身血气"),
    "sacrifice_blade": ("舍身剑", "以固定血气代价换取极高倍率"),
    "bloomblight_staff": ("枯荣杖", "施毒与自愈形成枯荣循环"),
    "twinphase_edge": ("阴阳刃", "三相混合伤害并获得护盾"),
    "fate_die": ("赌命骰", "每次攻击在低谷与高峰间波动"),
    "death_scribe": ("断生笔", "标记残血并逐次提高斩杀压力"),
    "defiant_spear": ("逆鳞枪", "濒危时爆发并保留最后血气"),
    "samsara_wheel": ("轮回盘", "真实群伤并以击败延续生命"),
}


def _build_weapon_entries() -> dict[str, SkinEntry]:
    blueprint_keys = {value.key for value in WEAPON_BLUEPRINTS}
    if set(_WEAPON_DISPLAY) != blueprint_keys:
        raise ValueError("基础修仙界武器展示键必须完整覆盖正式武器蓝图")
    names = [value[0] for value in _WEAPON_DISPLAY.values()]
    if len(names) != len(set(names)):
        raise ValueError("基础修仙界正式武器名称不能重复")
    entries = {
        STARTER_WEAPON_ITEM_ID: SkinEntry(name="仙京制式剑器", icon="⚔"),
        STARTER_WEAPON_ID: SkinEntry(
            name="仙京制式剑",
            description="仙京赐予初入道途者的制式灵剑。",
            icon="⚔",
        ),
    }
    for blueprint in WEAPON_BLUEPRINTS:
        name, description = _WEAPON_DISPLAY[blueprint.key]
        entries.update(
            {
                f"item.weapon.{blueprint.key}": SkinEntry(name=f"{name}器胚", icon="⚔"),
                f"weapon.{blueprint.key}": SkinEntry(name=name, description=description, icon="⚔"),
                f"ability.weapon.{blueprint.key}": SkinEntry(name=f"{name}器诀", description=description, icon="⚔"),
            }
        )
    return entries


CULTIVATION_WEAPON_ENTRIES = _build_weapon_entries()


__all__ = ["CULTIVATION_WEAPON_ENTRIES"]
