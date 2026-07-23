"""把探险掉落判定翻译成统一奖励规格。"""

from __future__ import annotations

from dataclasses import dataclass

from game.content.catalog import CHARACTER_LEVEL_PROGRESSION_ID, DRAW_TICKET_ITEM_ID
from game.content.catalog.enemy import (
    AWARD_BOSS_TROPHY_ID,
    AWARD_DRAW_TICKET_ID,
    AWARD_ENEMY_TROPHY_ID,
    AWARD_LARGE_HEALTH_MEDICINE_ID,
    AWARD_LARGE_SPIRIT_MEDICINE_ID,
    AWARD_MEDIUM_HEALTH_MEDICINE_ID,
    AWARD_MEDIUM_SPIRIT_MEDICINE_ID,
    AWARD_RANDOM_EQUIPMENT_ID,
    AWARD_RANDOM_WEAPON_ID,
    AWARD_REGION_TROPHY_ID,
    AWARD_SMALL_HEALTH_MEDICINE_ID,
    AWARD_SMALL_SPIRIT_MEDICINE_ID,
    AWARD_WORLD_CURIO_ID,
)
from game.content.catalog.item import (
    BOSS_TROPHY_ITEM_IDS,
    ITEM_RECYCLE_COMPONENT_ID,
    LARGE_HEALTH_MEDICINE_ITEM_ID,
    LARGE_SPIRIT_MEDICINE_ITEM_ID,
    MEDIUM_HEALTH_MEDICINE_ITEM_ID,
    MEDIUM_SPIRIT_MEDICINE_ITEM_ID,
    REGULAR_ENEMY_TROPHY_ITEM_IDS,
    SMALL_HEALTH_MEDICINE_ITEM_ID,
    SMALL_SPIRIT_MEDICINE_ITEM_ID,
    WORLD_CURIO_ITEM_IDS,
    WORLD_CURIO_WEIGHTS,
    CurrencyRecycleYield,
)
from game.core.gameplay import (
    ITEM_STORAGE_COMPONENT_ID,
    CharacterExperienceReward,
    GeneratedEquipmentReward,
    GeneratedWeaponReward,
    ItemStorageComponent,
    StackItemReward,
    WeaponExperienceReward,
)
from game.rules.equipment import EquipmentGenerationRequest, EquipmentInstanceGenerator
from game.rules.exploration import ExplorationRewardKind, ExplorationRewardReference
from game.rules.weapon import WeaponGenerationRequest, WeaponInstanceGenerator
from game.content.catalog.weapon.mechanics import WEAPON_MAXIMUM_LEVEL_TABLE


_MEDICINE_AWARDS = {
    AWARD_SMALL_HEALTH_MEDICINE_ID: SMALL_HEALTH_MEDICINE_ITEM_ID,
    AWARD_SMALL_SPIRIT_MEDICINE_ID: SMALL_SPIRIT_MEDICINE_ITEM_ID,
    AWARD_MEDIUM_HEALTH_MEDICINE_ID: MEDIUM_HEALTH_MEDICINE_ITEM_ID,
    AWARD_MEDIUM_SPIRIT_MEDICINE_ID: MEDIUM_SPIRIT_MEDICINE_ITEM_ID,
    AWARD_LARGE_HEALTH_MEDICINE_ID: LARGE_HEALTH_MEDICINE_ITEM_ID,
    AWARD_LARGE_SPIRIT_MEDICINE_ID: LARGE_SPIRIT_MEDICINE_ITEM_ID,
}


@dataclass(frozen=True)
class ExplorationRewardBuild:
    rewards: tuple[object, ...]
    weapon_drops: int
    equipment_drops: int
    trophy_drops: int
    medicine_drops: int
    draw_ticket_drops: int
    trophy_value: int
    backpack_space: int
    references: tuple[ExplorationRewardReference, ...]


class ExplorationRewardFactory:
    """决定奖励规格和容量需求，不读取或提交数据库。"""

    def __init__(self, content) -> None:
        self.content = content
        catalog = content.catalog
        self.weapon_generator = WeaponInstanceGenerator(
            catalog.weapons,
            catalog.itemization_engine,
            WEAPON_MAXIMUM_LEVEL_TABLE,
        )
        self.equipment_generator = EquipmentInstanceGenerator(
            catalog.equipment,
            catalog.itemization_engine,
        )

    def build(
        self,
        awards,
        *,
        plan,
        character,
        inventory,
        loadout,
        character_experience: int,
        weapon_experience: int,
        context,
    ) -> ExplorationRewardBuild:
        armory_id = _container_id(inventory, "container.armory")
        backpack_id = _container_id(inventory, "container.backpack")
        special_id = _container_id(inventory, "container.special")
        rewards: list[object] = [
            CharacterExperienceReward(
                character.id,
                CHARACTER_LEVEL_PROGRESSION_ID,
                character_experience,
            )
        ]
        if loadout.weapon_asset_id is not None and weapon_experience > 0:
            rewards.append(
                WeaponExperienceReward(loadout.weapon_asset_id, weapon_experience)
            )

        weapon_count = 0
        equipment_count = 0
        trophy_count = 0
        medicine_count = 0
        draw_ticket_count = 0
        trophy_value = 0
        backpack_space = 0
        references: list[ExplorationRewardReference] = []
        sequence = 0
        stack_quantities: dict[str, int] = {}
        weapon_ids = tuple(
            value
            for value in self.content.catalog.weapons.definitions.ids()
            if self.content.catalog.weapons.require(value).generation_profile_id is not None
        )
        equipment_ids = self.content.catalog.equipment.definitions.ids()
        for award in awards:
            for _ in range(award.quantity):
                asset_id = f"asset:{context.trace_id}:{award.draw_index}:{sequence}"
                if award.award_id == AWARD_RANDOM_WEAPON_ID:
                    definition_id = context.random.choice(weapon_ids)
                    generated = self.weapon_generator.generate(
                        WeaponGenerationRequest(
                            f"{context.trace_id}:weapon:{sequence}",
                            asset_id,
                            definition_id,
                            self.content.catalog.report.content_fingerprint,
                        ),
                        context=context,
                    ).state
                    definition = self.content.catalog.weapons.require(definition_id)
                    rewards.append(
                        GeneratedWeaponReward(
                            generated,
                            definition.item_definition_id,
                            armory_id,
                        )
                    )
                    weapon_count += 1
                    references.append(
                        ExplorationRewardReference(
                            ExplorationRewardKind.WEAPON,
                            generated.definition_id,
                            asset_id=generated.asset_id,
                        )
                    )
                elif award.award_id == AWARD_RANDOM_EQUIPMENT_ID:
                    definition_id = context.random.choice(equipment_ids)
                    generated = self.equipment_generator.generate(
                        EquipmentGenerationRequest(
                            f"{context.trace_id}:equipment:{sequence}",
                            asset_id,
                            definition_id,
                            self.content.catalog.report.content_fingerprint,
                        ),
                        context=context,
                    ).state
                    definition = self.content.catalog.equipment.require(definition_id)
                    rewards.append(
                        GeneratedEquipmentReward(
                            generated,
                            definition.item_definition_id,
                            armory_id,
                        )
                    )
                    equipment_count += 1
                    references.append(
                        ExplorationRewardReference(
                            ExplorationRewardKind.EQUIPMENT,
                            generated.definition_id,
                            asset_id=generated.asset_id,
                        )
                    )
                else:
                    definition_id = self._stack_definition(award, plan, context)
                    if definition_id is not None:
                        stack_quantities[definition_id] = (
                            stack_quantities.get(definition_id, 0) + 1
                        )
                sequence += 1

        for definition_id, requested_quantity in stack_quantities.items():
            definition = self.content.catalog.items.require(definition_id)
            container_id = (
                backpack_id
                if definition.tags.has("storage.backpack")
                else special_id
            )
            existing = next(
                (
                    stack
                    for stack in inventory.stacks.values()
                    if stack.definition_id == definition_id
                    and stack.container_id == container_id
                ),
                None,
            )
            quantity = requested_quantity
            if definition.stack_limit is not None:
                quantity = min(
                    quantity,
                    definition.stack_limit - (existing.quantity if existing else 0),
                )
            if quantity < 1:
                continue
            stack_asset_id = (
                existing.id
                if existing is not None
                else f"stack:{character.id}:{definition_id}"
            )
            rewards.append(
                StackItemReward(
                    stack_asset_id,
                    definition_id,
                    container_id,
                    quantity,
                )
            )
            references.append(
                ExplorationRewardReference(
                    ExplorationRewardKind.ITEM,
                    definition_id,
                    quantity=quantity,
                )
            )
            if definition.tags.has("item.trophy"):
                trophy_count += quantity
                recycle = definition.component(
                    ITEM_RECYCLE_COMPONENT_ID,
                    CurrencyRecycleYield,
                )
                trophy_value += recycle.unit_amount * quantity
                storage = definition.component(
                    ITEM_STORAGE_COMPONENT_ID,
                    ItemStorageComponent,
                )
                backpack_space += storage.unit_space * quantity
            elif definition.tags.has("item.medicine"):
                medicine_count += quantity
            elif definition.tags.has("item.draw_ticket"):
                draw_ticket_count += quantity

        return ExplorationRewardBuild(
            tuple(rewards),
            weapon_count,
            equipment_count,
            trophy_count,
            medicine_count,
            draw_ticket_count,
            trophy_value,
            backpack_space,
            tuple(references),
        )

    def _stack_definition(self, award, plan, context) -> str | None:
        if award.award_id == AWARD_DRAW_TICKET_ID:
            return DRAW_TICKET_ITEM_ID
        if award.award_id in _MEDICINE_AWARDS:
            return _MEDICINE_AWARDS[award.award_id]
        enemies = plan.encounter.enemies if plan.encounter is not None else ()
        enemy = enemies[award.roll_index % len(enemies)] if enemies else None
        if award.award_id == AWARD_REGION_TROPHY_ID:
            region = self.content.exploration_regions.require(plan.region_id)
            return _weighted_choice(
                region.trophy_item_ids,
                region.trophy_weights,
                context,
            )
        if award.award_id == AWARD_ENEMY_TROPHY_ID and enemy is not None:
            return REGULAR_ENEMY_TROPHY_ITEM_IDS.get(enemy.definition_id)
        if award.award_id == AWARD_BOSS_TROPHY_ID and enemy is not None:
            return BOSS_TROPHY_ITEM_IDS.get(enemy.definition_id)
        if award.award_id == AWARD_WORLD_CURIO_ID:
            return _weighted_choice(
                WORLD_CURIO_ITEM_IDS,
                WORLD_CURIO_WEIGHTS,
                context,
            )
        return None


def available_backpack_space(inventory, item_catalog) -> int | None:
    """返回背包剩余空间；无限容量返回 None。"""

    container_id = _container_id(inventory, "container.backpack")
    maximum = inventory.containers[container_id].maximum_space
    if maximum is None:
        return None
    used = 0
    for stack in inventory.stacks.values():
        if stack.container_id != container_id:
            continue
        definition = item_catalog.require(stack.definition_id)
        storage = definition.component(ITEM_STORAGE_COMPONENT_ID, ItemStorageComponent)
        used += storage.unit_space * stack.quantity
    for instance in inventory.instances.values():
        if instance.container_id != container_id:
            continue
        definition = item_catalog.require(instance.definition_id)
        storage = definition.component(ITEM_STORAGE_COMPONENT_ID, ItemStorageComponent)
        used += storage.unit_space
    return maximum - used


def _container_id(inventory, kind: str) -> str:
    return next(value.id for value in inventory.containers.values() if value.kind == kind)


def _weighted_choice(values, weights, context):
    total = sum(weights)
    sampled = context.random.randint(1, total)
    for value, weight in zip(values, weights):
        sampled -= weight
        if sampled <= 0:
            return value
    return values[-1]


__all__ = [
    "ExplorationRewardBuild",
    "ExplorationRewardFactory",
    "available_backpack_space",
]
