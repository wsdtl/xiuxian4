"""把角色永久状态和外部贡献投影为统一 RuleEntity。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping

from ..attributes import AttributeModifier, AttributeResolver, ResourceDefinition
from ..entity import ActiveEffect, RuleEntity
from ..ids import StableId
from ..tags import TagSet
from .contributions import CharacterContribution, ContributionSpec
from .definitions import CharacterCatalog
from .models import CORE_ATTRIBUTE_IDS, CharacterState, CharacterStatus, PERSISTENT_RESOURCE_IDS


@dataclass(frozen=True)
class CharacterProjection:
    character_id: str
    entity: RuleEntity
    contributions: tuple[CharacterContribution, ...]


class CharacterProjector:
    """角色进入战斗和其他规则场景的唯一标准投影入口。"""

    def __init__(
        self,
        catalog: CharacterCatalog,
        attributes: AttributeResolver,
        resources: Mapping[StableId, ResourceDefinition],
        *,
        ability_ids: frozenset[StableId] = frozenset(),
        trigger_ids: frozenset[StableId] = frozenset(),
        interceptor_ids: frozenset[StableId] = frozenset(),
        target_constraint_ids: frozenset[StableId] = frozenset(),
    ) -> None:
        if not catalog.finalized:
            catalog.finalize()
        self.catalog = catalog
        self.attributes = attributes
        self.resources = dict(resources)
        self.ability_ids = ability_ids
        self.trigger_ids = trigger_ids
        self.interceptor_ids = interceptor_ids
        self.target_constraint_ids = target_constraint_ids
        self._validate_foundation()
        for feature in self.catalog.features:
            self._validate_spec(feature.id, feature.contribution)

    def project(
        self,
        character: CharacterState,
        *,
        contributions: tuple[CharacterContribution, ...] = (),
        context_tags: TagSet = TagSet(),
    ) -> CharacterProjection:
        if character.status is not CharacterStatus.ACTIVE:
            raise ValueError("退隐角色不能投影为可行动规则实体")
        template = self.catalog.templates.require(character.template_id)
        feature_contributions = tuple(
            CharacterContribution(
                id=feature.id,
                source_kind="source.character_feature",
                source_id=feature.id,
                contribution=feature.contribution,
            )
            for feature in (
                self.catalog.features.require(feature_id)
                for feature_id in sorted(character.features)
            )
        )
        all_contributions = (*feature_contributions, *contributions)
        identities: set[tuple[str, str, str]] = set()
        effects: list[ActiveEffect] = []
        for index, contribution in enumerate(all_contributions):
            identity = (contribution.id, contribution.source_kind, contribution.source_id)
            if identity in identities:
                raise ValueError(f"角色贡献重复：{identity}")
            identities.add(identity)
            self._validate_spec(contribution.id, contribution.contribution)
            effects.append(self._to_effect(character.id, contribution, index))
        entity = RuleEntity(
            id=character.id,
            base_attributes=character.core_attributes,
            resources=character.resources,
            base_tags=template.tags.merged(TagSet.of("entity.character"), context_tags),
            active_effects=tuple(effects),
            revision=character.revision,
        )
        snapshot = entity.snapshot(self.attributes)
        resources = dict(entity.resources)
        for resource_id, value in resources.items():
            resources[resource_id] = self.resources[resource_id].clamp(value, snapshot)
        entity = RuleEntity(
            id=entity.id,
            base_attributes=entity.base_attributes,
            resources=resources,
            base_tags=entity.base_tags,
            base_abilities=entity.base_abilities,
            active_effects=entity.active_effects,
            cooldowns=entity.cooldowns,
            revision=entity.revision,
        )
        return CharacterProjection(character.id, entity, tuple(all_contributions))

    def initialize_new_character(
        self,
        character: CharacterState,
        *,
        contributions: tuple[CharacterContribution, ...] = (),
    ) -> CharacterState:
        """按初始永久特征的完整投影，把新角色资源填充到最终上限。"""

        if character.revision != 0:
            raise ValueError("initialize_new_character 只能用于 revision=0 的新角色")
        projection = self.project(character, contributions=contributions)
        snapshot = projection.entity.snapshot(self.attributes)
        resources: dict[StableId, float] = {}
        for resource_id in PERSISTENT_RESOURCE_IDS:
            definition = self.resources[resource_id]
            if definition.maximum_attribute is not None:
                resources[resource_id] = snapshot.value(definition.maximum_attribute)
            elif definition.fixed_maximum is not None:
                resources[resource_id] = definition.fixed_maximum
            else:
                raise ValueError(f"持久资源 {resource_id} 缺少最大值定义")
        return replace(character, resources=resources)

    def _to_effect(
        self,
        character_id: str,
        contribution: CharacterContribution,
        index: int,
    ) -> ActiveEffect:
        spec = contribution.contribution
        modifiers = tuple(
            AttributeModifier(
                id=f"character:{character_id}:{index}:attribute:{grant_index}",
                attribute_id=grant.attribute_id,
                layer=grant.layer,
                value=grant.value,
                source_id=contribution.source_id,
                required_tags=grant.required_tags,
                blocked_tags=grant.blocked_tags,
                priority=grant.priority,
            )
            for grant_index, grant in enumerate(spec.attributes)
        )
        return ActiveEffect(
            instance_id=f"character:{character_id}:contribution:{index}",
            definition_id=contribution.id,
            source_id=contribution.source_id,
            modifiers=modifiers,
            granted_tags=spec.tags,
            granted_abilities=spec.abilities,
            granted_triggers=spec.triggers,
            granted_interceptors=spec.interceptors,
            granted_target_constraints=spec.target_constraints,
            remaining_turns=None,
        )

    def _validate_foundation(self) -> None:
        missing_attributes = CORE_ATTRIBUTE_IDS - set(self.attributes.definitions)
        if missing_attributes:
            raise KeyError(
                f"角色投影缺少核心属性定义：{', '.join(sorted(missing_attributes))}"
            )
        missing_resources = PERSISTENT_RESOURCE_IDS - set(self.resources)
        if missing_resources:
            raise KeyError(
                f"角色投影缺少持久资源定义：{', '.join(sorted(missing_resources))}"
            )
        for resource_id in PERSISTENT_RESOURCE_IDS:
            definition = self.resources[resource_id]
            if definition.id != resource_id:
                raise ValueError(f"资源定义映射键与 id 不一致：{resource_id}")

    def _validate_spec(self, contribution_id: StableId, spec: ContributionSpec) -> None:
        unknown_attributes = {
            grant.attribute_id for grant in spec.attributes
        } - set(self.attributes.definitions)
        checks = (
            (unknown_attributes, "属性"),
            (set(spec.abilities) - set(self.ability_ids), "Ability"),
            (set(spec.triggers) - set(self.trigger_ids), "Trigger"),
            (set(spec.interceptors) - set(self.interceptor_ids), "伤害干预器"),
            (
                set(spec.target_constraints) - set(self.target_constraint_ids),
                "目标约束",
            ),
        )
        for unknown, label in checks:
            if unknown:
                raise KeyError(
                    f"角色贡献 {contribution_id} 引用了未知{label}："
                    f"{', '.join(sorted(unknown))}"
                )


__all__ = ["CharacterProjection", "CharacterProjector"]
