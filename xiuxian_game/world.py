"""首个修仙世界内容包：只提供跑通正式闭环所需的最小内容。"""

from __future__ import annotations

from datetime import time, timedelta

from xiuxian_core.gameplay import (
    AbilityDefinition,
    ActionDefinition,
    ActionSlotKind,
    CalendarSchedule,
    CalendarUnit,
    CycleDefinition,
    DealDamage,
    EffectDefinition,
    EffectReference,
    FixedMagnitude,
    SkinEntry,
    SkinPack,
    TagSet,
)
from xiuxian_core.gameplay.character import (
    COMBAT_ATTACK,
    COMBAT_DEFENSE,
    COMBAT_SPEED,
    HEALTH_MAXIMUM,
    SPIRIT_MAXIMUM,
    CharacterTemplateDefinition,
    ContributionSpec,
    ProgressionDefinition,
    core_attribute_definitions,
    persistent_resource_definitions,
)
from xiuxian_core.gameplay.combat import (
    CombatStats,
    DamageTypeDefinition,
    RecoveryStats,
)
from xiuxian_core.gameplay.content import (
    CombatProfileDefinition,
    ContentAssembler,
    ContentPackage,
    ContentPackageManifest,
    ContentRuntime,
    ContentVersion,
    PackageRequirement,
)
from xiuxian_core.gameplay.economy import CurrencyDefinition
from xiuxian_core.gameplay.equipment import (
    EquipmentDefinition,
    EquipmentQualityProfile,
    EquipmentStyleDefinition,
)
from xiuxian_core.gameplay.inventory import ItemAssetKind, ItemDefinition
from xiuxian_core.gameplay.loadout import (
    ACCESSORY_SLOT_ID,
    BODY_SLOT_ID,
    FEET_SLOT_ID,
    HANDS_SLOT_ID,
    HEAD_SLOT_ID,
    WAIST_SLOT_ID,
    WEAPON_SLOT_ID,
    LoadoutItemComponent,
    QualityDefinition,
)
from xiuxian_core.gameplay.weapon import (
    WeaponDefinition,
    WeaponLevelAttribute,
    WeaponQualityProfile,
)


WORLD_PACKAGE_ID = "content.first_world"
WORLD_SKIN_ID = "skin.first_world"
CHARACTER_TEMPLATE_ID = "character_template.wandering_cultivator"
PROGRESSION_ID = "progression.cultivation_level"
CURRENCY_ID = "currency.spirit_stone"
QUALITY_ID = "quality.mortal"
STARTER_WEAPON_ID = "weapon.green_bamboo_sword"
STARTER_WEAPON_ITEM_ID = "item.weapon.green_bamboo_sword"
TRIAL_ABILITY_ID = "ability.mountain_gate_strike"
TRIAL_EFFECT_ID = "effect.mountain_gate_strike"
TRIAL_ENEMY_ID = "enemy.mountain_gate_puppet"
TRIAL_ACTION_ID = "action.mountain_gate_trial"
TRIAL_OUTCOME_ID = "action_outcome.mountain_gate_victory"
HERB_ITEM_ID = "item.material.clear_dew_herb"
DAILY_CYCLE_ID = "cycle.first_world_day"
TRIAL_STONE_REWARD = 25
TRIAL_EXPERIENCE_REWARD = 20
TRIAL_HERB_REWARD = 2

_EQUIPMENT_SLOTS = (
    (HEAD_SLOT_ID, "head"),
    (BODY_SLOT_ID, "body"),
    (HANDS_SLOT_ID, "hands"),
    (WAIST_SLOT_ID, "waist"),
    (FEET_SLOT_ID, "feet"),
    (ACCESSORY_SLOT_ID, "accessory"),
)


def first_world_packages() -> tuple[ContentPackage, ...]:
    core = _core_package()
    skin = _skin_package(core.display_content_ids)
    return core, skin


def assemble_first_world() -> ContentRuntime:
    return ContentAssembler(
        active_combat_profile_id="combat_profile.first_world",
    ).assemble(first_world_packages())


def _core_package() -> ContentPackage:
    quality = QualityDefinition(QUALITY_ID, 0)
    progression = ProgressionDefinition(PROGRESSION_ID, (100, 240, 420, 680))
    template = CharacterTemplateDefinition(
        CHARACTER_TEMPLATE_ID,
        {
            HEALTH_MAXIMUM: 100,
            SPIRIT_MAXIMUM: 60,
            COMBAT_ATTACK: 10,
            COMBAT_DEFENSE: 2,
            COMBAT_SPEED: 10,
        },
        progression_ids=frozenset({progression.id}),
    )
    weapon_item = ItemDefinition(
        STARTER_WEAPON_ITEM_ID,
        ItemAssetKind.INSTANCE,
        tags=TagSet.of("item.weapon"),
        components={
            "item_component.loadout": LoadoutItemComponent(
                frozenset({WEAPON_SLOT_ID})
            )
        },
    )
    herb = ItemDefinition(
        HERB_ITEM_ID,
        ItemAssetKind.STACK,
        tags=TagSet.of("item.material", "item.herb"),
        stack_limit=99,
    )
    weapon = WeaponDefinition(
        STARTER_WEAPON_ID,
        weapon_item.id,
        ContributionSpec(abilities=frozenset({TRIAL_ABILITY_ID})),
        {
            quality.id: WeaponQualityProfile(
                quality.id,
                experience_requirements=(80, 180),
                level_attributes=(
                    WeaponLevelAttribute(
                        COMBAT_ATTACK,
                        "local_flat",
                        (4, 7, 11),
                    ),
                ),
            )
        },
    )
    style = EquipmentStyleDefinition("style.wandering")
    equipment_items = tuple(
        ItemDefinition(
            f"item.equipment.wandering_{suffix}",
            ItemAssetKind.INSTANCE,
            tags=TagSet.of("item.equipment", f"item.equipment.{suffix}"),
            components={
                "item_component.loadout": LoadoutItemComponent(frozenset({slot_id}))
            },
        )
        for slot_id, suffix in _EQUIPMENT_SLOTS
    )
    equipment = tuple(
        EquipmentDefinition(
            f"equipment.wandering_{suffix}",
            item.id,
            slot_id,
            style.id,
            quality_profiles={
                quality.id: EquipmentQualityProfile(
                    quality.id,
                    ContributionSpec(),
                )
            },
        )
        for (slot_id, suffix), item in zip(_EQUIPMENT_SLOTS, equipment_items)
    )
    damage_type = DamageTypeDefinition(
        "damage.physical",
        defense_attribute=COMBAT_DEFENSE,
    )
    effect = EffectDefinition(
        TRIAL_EFFECT_ID,
        operations=(
            DealDamage(
                "operation.mountain_gate_strike",
                damage_type.id,
                FixedMagnitude(18),
                can_miss=False,
                can_critical=False,
                can_block=False,
            ),
        ),
    )
    ability = AbilityDefinition(
        TRIAL_ABILITY_ID,
        effects=(EffectReference(effect.id),),
    )
    trial_action = ActionDefinition(
        TRIAL_ACTION_ID,
        ActionSlotKind.MAIN,
        timedelta(0),
    )
    display_ids = frozenset(
        {
            CURRENCY_ID,
            QUALITY_ID,
            CHARACTER_TEMPLATE_ID,
            PROGRESSION_ID,
            STARTER_WEAPON_ITEM_ID,
            HERB_ITEM_ID,
            style.id,
            damage_type.id,
            ability.id,
            DAILY_CYCLE_ID,
            TRIAL_ACTION_ID,
            *(item.id for item in equipment_items),
        }
    )
    return ContentPackage(
        ContentPackageManifest(WORLD_PACKAGE_ID, ContentVersion(1, 0, 0)),
        currencies=(CurrencyDefinition(CURRENCY_ID),),
        qualities=(quality,),
        attributes=tuple(core_attribute_definitions().values()),
        resources=tuple(persistent_resource_definitions().values()),
        progressions=(progression,),
        character_templates=(template,),
        items=(weapon_item, herb, *equipment_items),
        equipment_styles=(style,),
        weapons=(weapon,),
        equipment=equipment,
        combat_profiles=(
            CombatProfileDefinition(
                "combat_profile.first_world",
                CombatStats("health.current"),
                RecoveryStats("health.current"),
            ),
        ),
        damage_types=(damage_type,),
        effects=(effect,),
        abilities=(ability,),
        cycles=(
            CycleDefinition(
                DAILY_CYCLE_ID,
                CalendarSchedule("Asia/Shanghai", CalendarUnit.DAY, time(4)),
            ),
        ),
        actions=(trial_action,),
        display_content_ids=display_ids,
    )


def _skin_package(display_ids: frozenset[str]) -> ContentPackage:
    names = {
        CURRENCY_ID: "灵石",
        QUALITY_ID: "凡品",
        CHARACTER_TEMPLATE_ID: "云游散修",
        PROGRESSION_ID: "修行境界",
        STARTER_WEAPON_ITEM_ID: "青竹剑",
        STARTER_WEAPON_ID: "青竹剑",
        HERB_ITEM_ID: "清露草",
        "style.wandering": "云游",
        "damage.physical": "劲力",
        TRIAL_EFFECT_ID: "叩山一击",
        TRIAL_ABILITY_ID: "叩山一击",
        DAILY_CYCLE_ID: "山中一日",
        TRIAL_ACTION_ID: "山门试炼",
    }
    equipment_names = {
        "head": "云游巾",
        "body": "云游袍",
        "hands": "云游护腕",
        "waist": "云游带",
        "feet": "云游履",
        "accessory": "云游佩",
    }
    for _slot_id, suffix in _EQUIPMENT_SLOTS:
        names[f"item.equipment.wandering_{suffix}"] = equipment_names[suffix]
        names[f"equipment.wandering_{suffix}"] = equipment_names[suffix]
    entries = {content_id: SkinEntry(names[content_id]) for content_id in display_ids}
    return ContentPackage(
        ContentPackageManifest(
            "content.first_world_skin",
            ContentVersion(1, 0, 0),
            (PackageRequirement(WORLD_PACKAGE_ID, ContentVersion(1, 0, 0)),),
        ),
        skin_packs=(SkinPack(WORLD_SKIN_ID, 1, entries),),
    )


__all__ = [
    "CHARACTER_TEMPLATE_ID",
    "CURRENCY_ID",
    "DAILY_CYCLE_ID",
    "HERB_ITEM_ID",
    "PROGRESSION_ID",
    "QUALITY_ID",
    "STARTER_WEAPON_ID",
    "STARTER_WEAPON_ITEM_ID",
    "TRIAL_ABILITY_ID",
    "TRIAL_ACTION_ID",
    "TRIAL_EXPERIENCE_REWARD",
    "TRIAL_ENEMY_ID",
    "TRIAL_HERB_REWARD",
    "TRIAL_OUTCOME_ID",
    "TRIAL_STONE_REWARD",
    "WORLD_PACKAGE_ID",
    "WORLD_SKIN_ID",
    "assemble_first_world",
    "first_world_packages",
]
