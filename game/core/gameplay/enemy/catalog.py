"""敌人领域的类型化目录与装配期完整性校验。"""

from __future__ import annotations

from ..ids import StableId
from ..registry import DefinitionRegistry
from .models import (
    EncounterScopeDefinition,
    EnemyBehaviorDefinition,
    EnemyDefinition,
    EnemyEncounterDefinition,
    EnemyLevelProfileDefinition,
    EnemyRankDefinition,
    EnemyRewardProfileDefinition,
)


class EnemyCatalog:
    def __init__(self) -> None:
        self.level_profiles = DefinitionRegistry[EnemyLevelProfileDefinition]("EnemyLevelProfile")
        self.ranks = DefinitionRegistry[EnemyRankDefinition]("EnemyRank")
        self.behaviors = DefinitionRegistry[EnemyBehaviorDefinition]("EnemyBehavior")
        self.reward_profiles = DefinitionRegistry[EnemyRewardProfileDefinition]("EnemyRewardProfile")
        self.definitions = DefinitionRegistry[EnemyDefinition]("Enemy")
        self.scopes = DefinitionRegistry[EncounterScopeDefinition]("EncounterScope")
        self.encounters = DefinitionRegistry[EnemyEncounterDefinition]("EnemyEncounter")
        self._finalized = False

    def require(self, definition_id: StableId) -> EnemyDefinition:
        return self.definitions.require(definition_id)

    def finalize(
        self,
        *,
        attribute_ids: frozenset[StableId],
        ability_ids: frozenset[StableId],
        trigger_ids: frozenset[StableId],
        interceptor_ids: frozenset[StableId],
        constraint_ids: frozenset[StableId],
        selector_ids: frozenset[StableId],
        loot_table_ids: frozenset[StableId],
    ) -> None:
        if self._finalized:
            return
        for profile in self.level_profiles:
            unknown = set(profile.attribute_values) - set(attribute_ids)
            if unknown:
                raise KeyError(f"敌人等级档案 {profile.id} 引用了未知属性：{', '.join(sorted(unknown))}")
        for rank in self.ranks:
            self._validate_spec(rank.id, rank.contribution, attribute_ids, ability_ids, trigger_ids, interceptor_ids, constraint_ids)
            unknown = set(rank.attribute_multipliers) - set(attribute_ids)
            if unknown:
                raise KeyError(f"敌人阶位 {rank.id} 引用了未知属性：{', '.join(sorted(unknown))}")
        behavior_ids = frozenset(self.behaviors.ids())
        for behavior in self.behaviors:
            self._validate_spec(behavior.id, behavior.contribution, attribute_ids, ability_ids, trigger_ids, interceptor_ids, constraint_ids)
            unknown = set(behavior.attribute_multipliers) - set(attribute_ids)
            if unknown:
                raise KeyError(f"敌人行为 {behavior.id} 引用了未知属性：{', '.join(sorted(unknown))}")
            if not behavior.incompatible_behavior_ids.issubset(behavior_ids):
                raise KeyError(f"敌人行为 {behavior.id} 引用了未知互斥行为")
            self._validate_ai_rules(behavior.id, behavior.ai_rules, ability_ids, selector_ids)
        reward_ids = frozenset(self.reward_profiles.ids())
        for rank in self.ranks:
            if rank.reward_profile_id is not None and rank.reward_profile_id not in reward_ids:
                raise KeyError(f"敌人阶位 {rank.id} 引用了未知奖励档案")
        for reward in self.reward_profiles:
            if reward.loot_table_id is not None and reward.loot_table_id not in loot_table_ids:
                raise KeyError(f"敌人奖励档案 {reward.id} 引用了未知掉落表：{reward.loot_table_id}")
        level_ids = frozenset(self.level_profiles.ids())
        rank_ids = frozenset(self.ranks.ids())
        for definition in self.definitions:
            if definition.level_profile_id not in level_ids:
                raise KeyError(f"敌人 {definition.id} 引用了未知等级档案")
            if definition.reward_profile_id not in reward_ids:
                raise KeyError(f"敌人 {definition.id} 引用了未知奖励档案")
            if not definition.allowed_rank_ids.issubset(rank_ids):
                raise KeyError(f"敌人 {definition.id} 引用了未知阶位")
            self._validate_spec(definition.id, definition.base_contribution, attribute_ids, ability_ids, trigger_ids, interceptor_ids, constraint_ids)
            self._validate_ai_rules(definition.id, definition.base_ai_rules, ability_ids, selector_ids)
        enemy_ids = frozenset(self.definitions.ids())
        scope_ids = frozenset(self.scopes.ids())
        for encounter in self.encounters:
            if encounter.scope_id not in scope_ids:
                raise KeyError(f"敌人遭遇 {encounter.id} 引用了未知范围")
            for spawn in encounter.spawns:
                if not spawn.enemy_ids.issubset(enemy_ids) or spawn.rank_id not in rank_ids:
                    raise KeyError(f"敌人遭遇 {encounter.id} 引用了未知敌人或阶位")
                for enemy_id in spawn.enemy_ids:
                    if spawn.rank_id not in self.require(enemy_id).allowed_rank_ids:
                        raise ValueError(f"敌人遭遇 {encounter.id} 为 {enemy_id} 使用了不允许的阶位")
        for registry in (
            self.level_profiles,
            self.ranks,
            self.behaviors,
            self.reward_profiles,
            self.definitions,
            self.scopes,
            self.encounters,
        ):
            registry.freeze()
        self._finalized = True

    @property
    def finalized(self) -> bool:
        return self._finalized

    @staticmethod
    def _validate_spec(owner_id, spec, attributes, abilities, triggers, interceptors, constraints) -> None:
        checks = (
            ({value.attribute_id for value in spec.attributes} - set(attributes), "属性"),
            (set(spec.abilities) - set(abilities), "Ability"),
            (set(spec.triggers) - set(triggers), "Trigger"),
            (set(spec.interceptors) - set(interceptors), "伤害干预器"),
            (set(spec.target_constraints) - set(constraints), "目标约束"),
        )
        for unknown, label in checks:
            if unknown:
                raise KeyError(f"敌人内容 {owner_id} 引用了未知{label}：{', '.join(sorted(unknown))}")

    @staticmethod
    def _validate_ai_rules(owner_id, rules, abilities, selectors) -> None:
        for rule in rules:
            if rule.ability_id not in abilities or rule.selector_id not in selectors:
                raise KeyError(f"敌人内容 {owner_id} 的 AI 引用了未知 Ability 或目标选择器")


__all__ = ["EnemyCatalog"]
