"""敌人身份与行为蓝图；玩家可见名称全部属于世界皮肤。"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class EnemyBehaviorBlueprint:
    key: str
    source_weapon_key: str
    attribute_multipliers: Mapping[str, float] = field(default_factory=dict)
    threat_bonus: float = 0.0
    incompatible_keys: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.key.strip() or not self.source_weapon_key.strip():
            raise ValueError("敌人行为蓝图缺少稳定键")
        object.__setattr__(
            self,
            "attribute_multipliers",
            MappingProxyType({str(key): float(value) for key, value in self.attribute_multipliers.items()}),
        )


@dataclass(frozen=True)
class EnemyIdentityBlueprint:
    key: str
    boss: bool = False


BEHAVIOR_BLUEPRINTS = (
    EnemyBehaviorBlueprint("heavy_strike", "mountain_cleaver", {"combat.attack": 1.12}, 8),
    EnemyBehaviorBlueprint("rapid_attack", "gale_ring", {"combat.speed": 1.18}, 8),
    EnemyBehaviorBlueprint("combo", "flash_blade", {"combat.speed": 1.08}, 10),
    EnemyBehaviorBlueprint("follow_up", "comet_shuttle", {"combat.critical.chance": 1.10}, 10),
    EnemyBehaviorBlueprint("execute", "dawn_bane", {"combat.attack": 1.08}, 12),
    EnemyBehaviorBlueprint("charged_burst", "hidden_edge_coffer", {"combat.attack": 1.15}, 12),
    EnemyBehaviorBlueprint("piercing", "star_piercer", {}, 9),
    EnemyBehaviorBlueprint("true_damage", "judgement_bow", {}, 13),
    EnemyBehaviorBlueprint("splash", "ember_brand", {}, 10),
    EnemyBehaviorBlueprint("area_attack", "realm_fan", {}, 12),
    EnemyBehaviorBlueprint("poison", "plague_banner", {}, 11, frozenset({"regeneration"})),
    EnemyBehaviorBlueprint("burn", "cinder_lash", {}, 10),
    EnemyBehaviorBlueprint("bleed", "hemorrhage_nail", {}, 10),
    EnemyBehaviorBlueprint("mark_detonation", "ashen_crucible", {}, 13),
    EnemyBehaviorBlueprint("resource_drain", "mana_devourer", {}, 10),
    EnemyBehaviorBlueprint("heavy_armor", "mountain_seal", {"health.maximum": 1.22, "combat.defense.physical": 1.30, "combat.speed": 0.88}, 12),
    EnemyBehaviorBlueprint("shield", "mountain_seal", {"health.maximum": 1.10}, 10),
    EnemyBehaviorBlueprint("evasion", "blink_fang", {"combat.evasion": 1.20, "combat.speed": 1.08}, 10),
    EnemyBehaviorBlueprint("block", "aegis_parasol", {"combat.defense.physical": 1.15}, 10),
    EnemyBehaviorBlueprint("counter", "mirror_blade", {}, 11),
    EnemyBehaviorBlueprint("lifesteal", "lifebond_chain", {}, 12),
    EnemyBehaviorBlueprint("regeneration", "verdant_staff", {"health.maximum": 1.10}, 10, frozenset({"poison"})),
    EnemyBehaviorBlueprint("death_guard", "defiant_spear", {}, 14),
    EnemyBehaviorBlueprint("sunder", "wither_fan", {}, 9),
    EnemyBehaviorBlueprint("stun", "soul_bell", {}, 13, frozenset({"sleep", "freeze"})),
    EnemyBehaviorBlueprint("freeze", "winter_rod", {}, 14, frozenset({"stun", "sleep"})),
    EnemyBehaviorBlueprint("sleep", "dream_flute", {}, 14, frozenset({"stun", "freeze"})),
    EnemyBehaviorBlueprint("slow", "dragon_coil", {}, 8),
    EnemyBehaviorBlueprint("taunt", "binding_codex", {"health.maximum": 1.08}, 10),
    EnemyBehaviorBlueprint("cooldown_lock", "null_blade", {}, 12),
    EnemyBehaviorBlueprint("volatile", "fate_die", {}, 11),
    EnemyBehaviorBlueprint("sacrifice", "sacrifice_blade", {"combat.attack": 1.18}, 13),
)


REGULAR_ENEMY_KEYS = (
    "mountain_ape", "moon_wolf", "fox_trickster", "venom_spider", "cave_serpent", "corpse_guard",
    "drowned_spirit", "painted_wraith", "night_raider", "blood_drinker", "dream_eater", "stone_guardian",
    "wind_hunter", "frost_stalker", "treasure_boar", "cliff_screecher", "war_ape", "river_mimic",
    "plague_beast", "flame_bird", "thunder_beast", "giant_serpent", "shadow_cat", "horned_brute",
    "grave_knight", "mist_witch", "bone_archer", "marsh_lurker", "ember_hound", "ice_elemental",
    "storm_elemental", "earth_elemental", "shadow_elemental", "forest_guardian", "blood_mage", "curse_caster",
    "shield_bearer", "pack_leader", "soul_reaper", "iron_colossus", "sky_predator", "deep_crawler",
    "mirror_spirit", "chain_warden", "ruin_sentinel", "star_gazer", "void_priest", "frost_witch",
    "plague_shaman", "flame_raider", "thunder_caller", "abyss_stalker", "moon_specter", "sun_guardian",
    "chaos_spawn", "time_watcher", "fate_weaver", "death_scribe", "realm_wanderer", "ancient_guardian",
)
REGULAR_ENEMY_BLUEPRINTS = tuple(EnemyIdentityBlueprint(key) for key in REGULAR_ENEMY_KEYS)


PERSONAL_BOSS_KEYS = (
    "nine_headed_plague", "venom_world_serpent", "drought_incarnate", "winged_omen",
    "stubborn_ruin", "endless_maw", "faceless_chaos", "twilight_dragon",
    "headless_warrior", "river_rebel", "scarlet_war_ape", "nine_headed_bird",
    "man_eating_raptor", "cavern_serpent_king", "thunder_one_leg", "eclipse_hound",
    "solar_raven", "flood_stag", "weakwater_predator", "wilderness_colossus",
    "ghost_emperor", "corpse_ancestor", "fox_matriarch", "dream_sovereign",
    "mountain_lord", "sea_dragon", "storm_sovereign", "frost_queen",
    "flame_tyrant", "plague_lord",
)


CULTIVATION_PARTY_BOSS_KEYS = (
    "blood_count", "bone_dragon",
    "fallen_seraph", "labyrinth_lord", "forge_cyclops", "stone_gaze_queen",
    "abyss_kraken", "world_leviathan", "earth_behemoth", "doom_fenrir",
)


MAGIC_PARTY_BOSS_KEYS = (
    "ancient_tree_king", "phantom_knight", "death_judge", "void_archon",
    "time_dragon", "fate_matriarch", "mirror_lord", "iron_titan",
    "moon_devourer", "sun_destroyer",
)

STELLAR_RING_PARTY_BOSS_KEYS = (
    "orbital_behemoth", "archive_warden", "ringbreaker_colossus",
    "solar_mirror", "null_conductor", "swarm_mother", "chrono_engine",
    "horizon_devourer", "protocol_judge", "thirteenth_core",
)


DISASTER_TEMPLATE_KEYS = (
    "star_eater", "realm_breaker", "soul_ferryman", "underworld_king",
    "celestial_rebel", "chaos_witch",
    "storm_dragon", "winter_king", "ash_phoenix", "final_guardian",
)


def _boss_blueprints(keys: tuple[str, ...]) -> tuple[EnemyIdentityBlueprint, ...]:
    return tuple(EnemyIdentityBlueprint(key, True) for key in keys)


PERSONAL_BOSS_BLUEPRINTS = _boss_blueprints(PERSONAL_BOSS_KEYS)
CULTIVATION_PARTY_BOSS_BLUEPRINTS = _boss_blueprints(CULTIVATION_PARTY_BOSS_KEYS)
MAGIC_PARTY_BOSS_BLUEPRINTS = _boss_blueprints(MAGIC_PARTY_BOSS_KEYS)
STELLAR_RING_PARTY_BOSS_BLUEPRINTS = _boss_blueprints(STELLAR_RING_PARTY_BOSS_KEYS)
PARTY_BOSS_BLUEPRINTS = (
    *CULTIVATION_PARTY_BOSS_BLUEPRINTS,
    *MAGIC_PARTY_BOSS_BLUEPRINTS,
    *STELLAR_RING_PARTY_BOSS_BLUEPRINTS,
)


_ALL_BOSS_TEMPLATE_KEYS = (
    *PERSONAL_BOSS_KEYS,
    *CULTIVATION_PARTY_BOSS_KEYS,
    *MAGIC_PARTY_BOSS_KEYS,
    *STELLAR_RING_PARTY_BOSS_KEYS,
    *DISASTER_TEMPLATE_KEYS,
)
BOSS_TEMPLATE_KEYS = tuple(_ALL_BOSS_TEMPLATE_KEYS)


def _validate() -> None:
    if len(BEHAVIOR_BLUEPRINTS) != 32:
        raise ValueError("首批敌人行为模板必须正好包含 32 项")
    if len(REGULAR_ENEMY_BLUEPRINTS) != 60:
        raise ValueError("首批敌人身份必须包含 60 个普通身份")
    if len(PERSONAL_BOSS_BLUEPRINTS) != 30 or len(PARTY_BOSS_BLUEPRINTS) != 30:
        raise ValueError("正式个人首领必须为 30 个，组队首领必须为 30 个")
    identity_keys = [
        value.key
        for value in (
            *REGULAR_ENEMY_BLUEPRINTS,
            *PERSONAL_BOSS_BLUEPRINTS,
            *PARTY_BOSS_BLUEPRINTS,
        )
    ]
    if len(identity_keys) != len(set(identity_keys)):
        raise ValueError("敌人身份稳定键不能重复")
    if len(BOSS_TEMPLATE_KEYS) != len(set(BOSS_TEMPLATE_KEYS)):
        raise ValueError("首领战斗模板键不能重复或缺失")


_validate()


__all__ = [
    "BEHAVIOR_BLUEPRINTS",
    "BOSS_TEMPLATE_KEYS",
    "CULTIVATION_PARTY_BOSS_BLUEPRINTS",
    "CULTIVATION_PARTY_BOSS_KEYS",
    "DISASTER_TEMPLATE_KEYS",
    "EnemyBehaviorBlueprint",
    "EnemyIdentityBlueprint",
    "MAGIC_PARTY_BOSS_BLUEPRINTS",
    "MAGIC_PARTY_BOSS_KEYS",
    "PARTY_BOSS_BLUEPRINTS",
    "PERSONAL_BOSS_BLUEPRINTS",
    "PERSONAL_BOSS_KEYS",
    "REGULAR_ENEMY_BLUEPRINTS",
    "REGULAR_ENEMY_KEYS",
    "STELLAR_RING_PARTY_BOSS_BLUEPRINTS",
    "STELLAR_RING_PARTY_BOSS_KEYS",
]
