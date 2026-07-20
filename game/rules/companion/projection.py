"""把伙伴实例投影为公共战斗实体和自动行动规则。"""

from __future__ import annotations

from dataclasses import dataclass, replace

from game.content.catalog.companion import CompanionCatalog
from game.core.gameplay import (
    COMBAT_ATTACK,
    COMBAT_DEFENSE,
    COMBAT_SPEED,
    HEALTH_MAXIMUM,
    SPIRIT_MAXIMUM,
    ActiveEffect,
    AttributeModifier,
    BattleAiRule,
    ContributionSpec,
    RuleEntity,
    TagSet,
)

from .models import (
    APTITUDE_AGILITY,
    APTITUDE_FOCUS,
    APTITUDE_OFFENSE,
    APTITUDE_VITALITY,
    CompanionInstance,
    CompanionTrace,
)


@dataclass(frozen=True)
class CompanionCombatProjection:
    companion_id: str
    definition_id: str
    entity: RuleEntity
    ai_rules: tuple[BattleAiRule, ...]


class CompanionCombatProjector:
    """伙伴复用标准行为 Ability，不创建伙伴专用战斗流水线。"""

    def __init__(self, content, companions: CompanionCatalog) -> None:
        self.content = content
        self.companions = companions
        self.attributes = content.enemy_projector.attributes

    def project(
        self,
        value: CompanionInstance | CompanionTrace,
        *,
        entity_id: str | None = None,
        context_tags: TagSet = TagSet(),
    ) -> CompanionCombatProjection:
        species = self.companions.species.require(value.definition_id)
        behaviors = tuple(
            self.content.enemies.behaviors.require(behavior_id)
            for behavior_id in (species.core_behavior_id, value.trait_behavior_id)
        )
        companion_id = entity_id or getattr(value, "id", None)
        if companion_id is None:
            companion_id = f"companion-trace:{value.index}"
        attributes = self._base_attributes(value.level, value.aptitudes)
        for attribute_id, multiplier in species.attribute_multipliers.items():
            attributes[attribute_id] *= multiplier
        for behavior in behaviors:
            for attribute_id, multiplier in behavior.attribute_multipliers.items():
                attributes[attribute_id] = attributes.get(attribute_id, 0.0) * multiplier
        specs = (
            ContributionSpec(
                tags=TagSet.of("entity.companion"),
                abilities=frozenset({"ability.basic_attack"}),
            ),
            *(value.contribution for value in behaviors),
        )
        effects = tuple(
            self._effect(companion_id, spec, index)
            for index, spec in enumerate(specs)
        )
        entity = RuleEntity(
            companion_id,
            attributes,
            base_tags=TagSet.of(
                "entity.companion",
                f"companion.definition.{species.id}",
                f"companion.origin.{species.origin_skin_id}",
            ).merged(context_tags),
            active_effects=effects,
        )
        snapshot = entity.snapshot(self.attributes)
        resources = {}
        for resource_id, definition in self.content.resources.items():
            if definition.maximum_attribute is not None:
                resources[resource_id] = snapshot.value(definition.maximum_attribute)
            elif definition.fixed_maximum is not None:
                resources[resource_id] = definition.fixed_maximum
            else:
                resources[resource_id] = definition.minimum
        entity = replace(entity, resources=resources)
        ai_rules = (
            BattleAiRule(
                "ai.companion.basic_attack",
                "ability.basic_attack",
                "target.enemy.first",
                priority=0,
                maximum_targets=1,
            ),
            *(rule for behavior in behaviors for rule in behavior.ai_rules),
        )
        return CompanionCombatProjection(
            companion_id,
            str(species.id),
            entity,
            tuple(ai_rules),
        )

    @staticmethod
    def _base_attributes(level: int, aptitudes) -> dict[str, float]:
        vitality = aptitudes[APTITUDE_VITALITY] / 100
        offense = aptitudes[APTITUDE_OFFENSE] / 100
        agility = aptitudes[APTITUDE_AGILITY]
        focus = aptitudes[APTITUDE_FOCUS] / 100
        return {
            HEALTH_MAXIMUM: (60 + 6 * (level - 1)) * vitality,
            SPIRIT_MAXIMUM: (80 + level - 1) * focus,
            COMBAT_ATTACK: (4 + 0.55 * (level - 1)) * offense,
            COMBAT_DEFENSE: 0.20 * (level - 1) * vitality,
            COMBAT_SPEED: max(40.0, 100 + (agility - 100) * 0.25),
        }

    @staticmethod
    def _effect(companion_id: str, spec: ContributionSpec, index: int) -> ActiveEffect:
        contribution_kind = ("base", "core", "trait")[index]
        definition_id = f"companion.contribution.{contribution_kind}"
        modifiers = tuple(
            AttributeModifier(
                id=f"companion:{companion_id}:{index}:attribute:{grant_index}",
                attribute_id=grant.attribute_id,
                layer=grant.layer,
                value=grant.value,
                source_id=definition_id,
                required_tags=grant.required_tags,
                blocked_tags=grant.blocked_tags,
                priority=grant.priority,
            )
            for grant_index, grant in enumerate(spec.attributes)
        )
        return ActiveEffect(
            instance_id=f"companion:{companion_id}:contribution:{index}",
            definition_id=definition_id,
            source_id=companion_id,
            modifiers=modifiers,
            granted_tags=spec.tags,
            granted_abilities=spec.abilities,
            granted_triggers=spec.triggers,
            granted_interceptors=spec.interceptors,
            granted_target_constraints=spec.target_constraints,
        )


__all__ = ["CompanionCombatProjection", "CompanionCombatProjector"]
