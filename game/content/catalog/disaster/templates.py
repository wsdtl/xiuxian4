"""灾厄叙事引用的显式战斗行为模板。"""

from types import MappingProxyType


DISASTER_BEHAVIOR_KEYS_BY_TEMPLATE = MappingProxyType(
    {
        "nine_headed_plague": ("poison", "area_attack", "mark_detonation"),
        "drought_incarnate": ("burn", "charged_burst", "splash"),
        "river_rebel": ("lifesteal", "heavy_strike", "taunt"),
        "venom_world_serpent": ("lifesteal", "heavy_strike", "taunt"),
        "twilight_dragon": ("freeze", "shield", "area_attack"),
        "headless_warrior": ("poison", "area_attack", "mark_detonation"),
        "winged_omen": ("rapid_attack", "combo", "evasion"),
        "soul_ferryman": ("heavy_armor", "counter", "death_guard"),
        "celestial_rebel": ("volatile", "cooldown_lock", "mark_detonation"),
        "realm_breaker": ("rapid_attack", "combo", "evasion"),
        "doom_fenrir": ("freeze", "shield", "area_attack"),
        "world_leviathan": ("execute", "resource_drain", "true_damage"),
        "storm_dragon": ("poison", "area_attack", "mark_detonation"),
        "abyss_kraken": ("heavy_armor", "counter", "death_guard"),
        "flame_tyrant": ("heavy_armor", "counter", "death_guard"),
        "ancient_tree_king": ("poison", "area_attack", "mark_detonation"),
        "iron_titan": ("freeze", "shield", "area_attack"),
        "frost_queen": ("rapid_attack", "combo", "evasion"),
        "ash_phoenix": ("burn", "charged_burst", "splash"),
        "final_guardian": ("rapid_attack", "combo", "evasion"),
    }
)


__all__ = ["DISASTER_BEHAVIOR_KEYS_BY_TEMPLATE"]
