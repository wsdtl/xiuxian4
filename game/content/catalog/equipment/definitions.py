"""十二个装备底座族、六槽正式装备和十八套可混搭套装。"""

from __future__ import annotations

from dataclasses import dataclass

from game.core.gameplay import (
    COMBAT_ATTACK,
    COMBAT_DEFENSE,
    COMBAT_SPEED,
    HEALTH_MAXIMUM,
    SPIRIT_MAXIMUM,
    LOADOUT_ITEM_COMPONENT_ID,
    AttributeGrant,
    ContributionSpec,
    EquipmentDefinition,
    EquipmentFamilyDefinition,
    EquipmentQualityProfile,
    EquipmentSetBonus,
    EquipmentSetDefinition,
    ItemAssetKind,
    ItemDefinition,
    LoadoutItemComponent,
    ModifierLayer,
    TagSet,
)

from ..foundation import QUALITY_IDS
from ..combat.stats import (
    COMBAT_ACCURACY,
    COMBAT_BLOCK_CHANCE,
    COMBAT_BLOCK_REDUCTION,
    COMBAT_CONTROL_CHANCE,
    COMBAT_CONTROL_RESISTANCE,
    COMBAT_CRITICAL_CHANCE,
    COMBAT_CRITICAL_DAMAGE,
    COMBAT_EVASION,
    COMBAT_FLAT_PENETRATION,
    COMBAT_HEALING_RATE,
    COMBAT_HEALING_RECEIVED,
    COMBAT_OUTGOING_RATE,
    COMBAT_RATE_PENETRATION,
    COMBAT_TENACITY,
)
from .blueprints import (
    EQUIPMENT_FAMILY_BLUEPRINTS,
    EQUIPMENT_SET_BLUEPRINTS,
    EQUIPMENT_SLOT_BLUEPRINTS,
)
from .properties import (
    EQUIPMENT_GENERATION_PROFILE_ID,
    equipment_trigger_id,
)


@dataclass(frozen=True)
class EquipmentCatalogContent:
    items: tuple[ItemDefinition, ...]
    families: tuple[EquipmentFamilyDefinition, ...]
    sets: tuple[EquipmentSetDefinition, ...]
    equipment: tuple[EquipmentDefinition, ...]
    display_ids: frozenset[str]


def equipment_family_id(key: str) -> str:
    return f"equipment_family.{key}"


def equipment_set_id(key: str) -> str:
    return f"equipment_set.{key}"


def equipment_definition_id(family_key: str, slot_key: str) -> str:
    return f"equipment.{family_key}.{slot_key}"


def equipment_item_id(family_key: str, slot_key: str) -> str:
    return f"item.equipment.{family_key}.{slot_key}"


def _attributes(*values: tuple[str, ModifierLayer, float]) -> ContributionSpec:
    return ContributionSpec(
        attributes=tuple(AttributeGrant(attribute, layer, amount) for attribute, layer, amount in values)
    )


def _trigger(key: str, tier: int) -> ContributionSpec:
    return ContributionSpec(triggers=frozenset({equipment_trigger_id(key, tier)}))


def _set_bonuses(key: str) -> tuple[EquipmentSetBonus, ...]:
    bonuses = {
        "army_breaker": (
            _attributes((COMBAT_RATE_PENETRATION, ModifierLayer.GLOBAL_FLAT, 0.05)),
            _attributes((COMBAT_CRITICAL_CHANCE, ModifierLayer.GLOBAL_FLAT, 0.04)),
            _trigger("critical_echo", 2),
        ),
        "everlife": (
            _attributes((HEALTH_MAXIMUM, ModifierLayer.LOCAL_FLAT, 70)),
            _attributes((COMBAT_HEALING_RECEIVED, ModifierLayer.GLOBAL_FLAT, 0.07)),
            _trigger("healing_shield", 2),
        ),
        "myriad_venom": (
            _attributes((COMBAT_OUTGOING_RATE, ModifierLayer.GLOBAL_FLAT, 0.04)),
            _attributes((COMBAT_CONTROL_CHANCE, ModifierLayer.GLOBAL_FLAT, 0.04)),
            _trigger("venom_touch", 2),
        ),
        "mirror_sea": (
            _attributes((COMBAT_EVASION, ModifierLayer.GLOBAL_FLAT, 0.05)),
            _attributes((COMBAT_SPEED, ModifierLayer.LOCAL_FLAT, 7)),
            _trigger("evade_counter", 2),
        ),
        "mystic_bastion": (
            _attributes((COMBAT_DEFENSE, ModifierLayer.LOCAL_FLAT, 9)),
            _attributes((COMBAT_BLOCK_CHANCE, ModifierLayer.GLOBAL_FLAT, 0.05)),
            _trigger("damaged_shield", 2),
        ),
        "wind_walk": (
            _attributes((COMBAT_SPEED, ModifierLayer.LOCAL_FLAT, 8)),
            _attributes((COMBAT_EVASION, ModifierLayer.GLOBAL_FLAT, 0.04)),
            _trigger("kill_cooldown", 2),
        ),
        "spirit_well": (
            _attributes((SPIRIT_MAXIMUM, ModifierLayer.LOCAL_FLAT, 40)),
            _attributes((COMBAT_HEALING_RATE, ModifierLayer.GLOBAL_FLAT, 0.06)),
            _trigger("critical_spirit", 2),
        ),
        "frost_prison": (
            _attributes((COMBAT_CONTROL_CHANCE, ModifierLayer.GLOBAL_FLAT, 0.05)),
            _attributes((COMBAT_TENACITY, ModifierLayer.GLOBAL_FLAT, 0.05)),
            _trigger("frost_touch", 2),
        ),
        "starfall": (
            _attributes((COMBAT_ACCURACY, ModifierLayer.GLOBAL_FLAT, 0.05)),
            _attributes((COMBAT_CRITICAL_DAMAGE, ModifierLayer.GLOBAL_FLAT, 0.10)),
            _trigger("critical_echo", 1),
        ),
        "sky_burn": (
            _attributes((COMBAT_OUTGOING_RATE, ModifierLayer.GLOBAL_FLAT, 0.04)),
            _attributes((COMBAT_CRITICAL_CHANCE, ModifierLayer.GLOBAL_FLAT, 0.03)),
            _trigger("burning_touch", 2),
        ),
        "void_realm": (
            _attributes((COMBAT_FLAT_PENETRATION, ModifierLayer.GLOBAL_FLAT, 7)),
            _attributes((COMBAT_RATE_PENETRATION, ModifierLayer.GLOBAL_FLAT, 0.04)),
            _trigger("execute_echo", 2),
        ),
        "samsara": (
            _attributes((HEALTH_MAXIMUM, ModifierLayer.LOCAL_FLAT, 65)),
            _attributes((COMBAT_HEALING_RECEIVED, ModifierLayer.GLOBAL_FLAT, 0.06)),
            _trigger("low_health_guard", 2),
        ),
        "blood_moon": (
            _attributes((COMBAT_CRITICAL_DAMAGE, ModifierLayer.GLOBAL_FLAT, 0.12)),
            _attributes((COMBAT_HEALING_RATE, ModifierLayer.GLOBAL_FLAT, 0.06)),
            _trigger("lifesteal", 2),
        ),
        "thunder_judgment": (
            _attributes((COMBAT_ATTACK, ModifierLayer.LOCAL_FLAT, 7)),
            _attributes((COMBAT_SPEED, ModifierLayer.LOCAL_FLAT, 6)),
            _trigger("critical_stun", 2),
        ),
        "thorn_crown": (
            _attributes((COMBAT_DEFENSE, ModifierLayer.LOCAL_FLAT, 8)),
            _attributes((COMBAT_BLOCK_REDUCTION, ModifierLayer.GLOBAL_FLAT, 0.06)),
            _trigger("thorns", 2),
        ),
        "spirit_tide": (
            _attributes((SPIRIT_MAXIMUM, ModifierLayer.LOCAL_FLAT, 45)),
            _attributes((COMBAT_HEALING_RATE, ModifierLayer.GLOBAL_FLAT, 0.05)),
            _trigger("turn_spirit", 2),
        ),
        "hunters_mark": (
            _attributes((COMBAT_ACCURACY, ModifierLayer.GLOBAL_FLAT, 0.05)),
            _attributes((COMBAT_OUTGOING_RATE, ModifierLayer.GLOBAL_FLAT, 0.04)),
            _trigger("hit_slow", 2),
        ),
        "immortal_guard": (
            _attributes((HEALTH_MAXIMUM, ModifierLayer.LOCAL_FLAT, 74)),
            _attributes((COMBAT_CONTROL_RESISTANCE, ModifierLayer.GLOBAL_FLAT, 0.06)),
            _trigger("damaged_heal", 2),
        ),
    }
    try:
        two, three, four = bonuses[key]
    except KeyError as error:
        raise ValueError(f"未知正式装备套装：{key}") from error
    return (
        EquipmentSetBonus(2, two),
        EquipmentSetBonus(3, three),
        EquipmentSetBonus(4, four),
    )


def build_equipment_catalog_content() -> EquipmentCatalogContent:
    families = tuple(
        EquipmentFamilyDefinition(
            equipment_family_id(blueprint.key),
            TagSet.of(f"equipment.family.{blueprint.key}"),
        )
        for blueprint in EQUIPMENT_FAMILY_BLUEPRINTS
    )
    sets = tuple(
        EquipmentSetDefinition(
            equipment_set_id(blueprint.key),
            _set_bonuses(blueprint.key),
        )
        for blueprint in EQUIPMENT_SET_BLUEPRINTS
    )
    quality_profiles = {
        quality_id: EquipmentQualityProfile(quality_id, ContributionSpec())
        for quality_id in QUALITY_IDS
    }
    items = []
    definitions = []
    display_ids = {
        *(value.id for value in families),
        *(value.id for value in sets),
    }
    for family in EQUIPMENT_FAMILY_BLUEPRINTS:
        for slot in EQUIPMENT_SLOT_BLUEPRINTS:
            item_id = equipment_item_id(family.key, slot.key)
            definition_id = equipment_definition_id(family.key, slot.key)
            items.append(
                ItemDefinition(
                    item_id,
                    ItemAssetKind.INSTANCE,
                    TagSet.of("item.equipment", "item.armament"),
                    components={
                        LOADOUT_ITEM_COMPONENT_ID: LoadoutItemComponent(
                            frozenset({slot.slot_id})
                        )
                    },
                )
            )
            definitions.append(
                EquipmentDefinition(
                    definition_id,
                    item_id,
                    slot.slot_id,
                    equipment_family_id(family.key),
                    quality_profiles=quality_profiles,
                    generation_profile_id=EQUIPMENT_GENERATION_PROFILE_ID,
                )
            )
            display_ids.update((item_id, definition_id))
    return EquipmentCatalogContent(
        tuple(items),
        families,
        sets,
        tuple(definitions),
        frozenset(display_ids),
    )


EQUIPMENT_CATALOG_CONTENT = build_equipment_catalog_content()


__all__ = [
    "EQUIPMENT_CATALOG_CONTENT",
    "EquipmentCatalogContent",
    "build_equipment_catalog_content",
    "equipment_definition_id",
    "equipment_family_id",
    "equipment_item_id",
    "equipment_set_id",
]
