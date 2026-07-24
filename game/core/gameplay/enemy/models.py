"""敌人、行为、阶位、阶段与遭遇的稳定数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from ..character import ContributionSpec
from ..combat.ai import BattleAiRule
from ..ids import StableId, stable_id
from ..tags import EMPTY_TAGS, TagSet


ENEMY_RANK_NORMAL_ID = "enemy.rank.normal"
ENEMY_RANK_ELITE_ID = "enemy.rank.elite"
ENEMY_RANK_BOSS_ID = "enemy.rank.boss"

ENCOUNTER_SCOPE_PERSONAL_ID = "encounter.scope.personal"
ENCOUNTER_SCOPE_PARTY_ID = "encounter.scope.party"
ENCOUNTER_SCOPE_GLOBAL_ID = "encounter.scope.global"


def _stable_ids(values, *, field_name: str) -> frozenset[StableId]:
    return frozenset(stable_id(value, field=field_name) for value in values)


@dataclass(frozen=True)
class EnemyLevelProfileDefinition:
    id: StableId
    attribute_values: Mapping[StableId, tuple[float, ...]]

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="enemy level profile id"))
        values = {
            stable_id(attribute_id, field="attribute id"): tuple(float(value) for value in levels)
            for attribute_id, levels in self.attribute_values.items()
        }
        if not values:
            raise ValueError("敌人等级档案不能为空")
        lengths = {len(levels) for levels in values.values()}
        if len(lengths) != 1 or next(iter(lengths)) < 1:
            raise ValueError("敌人等级档案必须为每项属性提供相同长度的非空数值表")
        object.__setattr__(self, "attribute_values", MappingProxyType(values))

    @property
    def maximum_level(self) -> int:
        return len(next(iter(self.attribute_values.values())))

    def attributes_at(self, level: int) -> Mapping[StableId, float]:
        if level < 1 or level > self.maximum_level:
            raise ValueError(f"敌人等级必须位于 1 到 {self.maximum_level}")
        return MappingProxyType(
            {attribute_id: values[level - 1] for attribute_id, values in self.attribute_values.items()}
        )


@dataclass(frozen=True)
class EnemyRankDefinition:
    id: StableId
    attribute_multipliers: Mapping[StableId, float] = field(default_factory=dict)
    contribution: ContributionSpec = ContributionSpec()
    minimum_behaviors: int = 1
    maximum_behaviors: int = 1
    threat_multiplier: float = 1.0
    reward_profile_id: StableId | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="enemy rank id"))
        multipliers = {
            stable_id(key, field="attribute id"): float(value)
            for key, value in self.attribute_multipliers.items()
        }
        if any(value <= 0 for value in multipliers.values()):
            raise ValueError("敌人阶位属性倍率必须大于 0")
        if self.minimum_behaviors < 0 or self.maximum_behaviors < self.minimum_behaviors:
            raise ValueError("敌人阶位行为数量边界无效")
        if self.threat_multiplier <= 0:
            raise ValueError("敌人阶位威胁倍率必须大于 0")
        if self.reward_profile_id is not None:
            object.__setattr__(
                self,
                "reward_profile_id",
                stable_id(self.reward_profile_id, field="enemy reward profile id"),
            )
        object.__setattr__(self, "attribute_multipliers", MappingProxyType(multipliers))


@dataclass(frozen=True)
class EnemyBehaviorDefinition:
    id: StableId
    attribute_multipliers: Mapping[StableId, float] = field(default_factory=dict)
    contribution: ContributionSpec = ContributionSpec()
    ai_rules: tuple[BattleAiRule, ...] = ()
    incompatible_behavior_ids: frozenset[StableId] = frozenset()
    threat_bonus: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="enemy behavior id"))
        multipliers = {
            stable_id(key, field="attribute id"): float(value)
            for key, value in self.attribute_multipliers.items()
        }
        if any(value <= 0 for value in multipliers.values()):
            raise ValueError("敌人行为属性倍率必须大于 0")
        if self.threat_bonus < 0:
            raise ValueError("敌人行为威胁加值不能小于 0")
        object.__setattr__(self, "attribute_multipliers", MappingProxyType(multipliers))
        object.__setattr__(self, "ai_rules", tuple(self.ai_rules))
        object.__setattr__(
            self,
            "incompatible_behavior_ids",
            _stable_ids(self.incompatible_behavior_ids, field_name="enemy behavior id"),
        )


@dataclass(frozen=True)
class EnemyPhaseLoadout:
    """An instance-owned phase plan generated together with the encounter."""

    id: StableId
    health_ratio: float
    behavior_ids: tuple[StableId, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="enemy phase id"))
        if not 0 < self.health_ratio < 1:
            raise ValueError("敌人实例阶段血量阈值必须位于 0 到 1")
        behaviors = tuple(
            stable_id(value, field="enemy behavior id")
            for value in self.behavior_ids
        )
        if not behaviors or len(behaviors) != len(set(behaviors)):
            raise ValueError("敌人实例阶段必须包含不重复的行为")
        object.__setattr__(self, "behavior_ids", behaviors)


@dataclass(frozen=True)
class EnemyRewardProfileDefinition:
    id: StableId
    character_experience_per_level: float
    weapon_experience_per_level: float
    loot_table_id: StableId | None = None
    base_loot_rolls: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="enemy reward profile id"))
        if self.loot_table_id is not None:
            object.__setattr__(self, "loot_table_id", stable_id(self.loot_table_id, field="loot table id"))
        if self.character_experience_per_level < 0 or self.weapon_experience_per_level < 0:
            raise ValueError("敌人经验系数不能小于 0")
        if self.base_loot_rolls < 0:
            raise ValueError("敌人基础掉落次数不能小于 0")


@dataclass(frozen=True)
class EnemyDefinition:
    id: StableId
    level_profile_id: StableId
    reward_profile_id: StableId
    allowed_rank_ids: frozenset[StableId]
    base_contribution: ContributionSpec = ContributionSpec()
    base_ai_rules: tuple[BattleAiRule, ...] = ()
    tags: TagSet = EMPTY_TAGS

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="enemy id"))
        object.__setattr__(self, "level_profile_id", stable_id(self.level_profile_id, field="enemy level profile id"))
        object.__setattr__(self, "reward_profile_id", stable_id(self.reward_profile_id, field="enemy reward profile id"))
        allowed = _stable_ids(self.allowed_rank_ids, field_name="enemy rank id")
        if not allowed:
            raise ValueError("敌人必须允许至少一个阶位")
        object.__setattr__(self, "allowed_rank_ids", allowed)
        object.__setattr__(self, "base_ai_rules", tuple(self.base_ai_rules))


@dataclass(frozen=True)
class EncounterScopeDefinition:
    id: StableId
    maximum_participants: int | None = 1
    shared_health: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="encounter scope id"))
        if self.maximum_participants is not None and self.maximum_participants < 1:
            raise ValueError("遭遇参与上限必须大于 0")


@dataclass(frozen=True)
class EnemySpawnDefinition:
    enemy_ids: frozenset[StableId]
    rank_id: StableId
    minimum_count: int = 1
    maximum_count: int = 1
    behavior_count: int | None = None
    phase_health_ratios: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        enemies = _stable_ids(self.enemy_ids, field_name="enemy id")
        if not enemies:
            raise ValueError("敌人生成槽必须包含候选")
        object.__setattr__(self, "enemy_ids", enemies)
        object.__setattr__(self, "rank_id", stable_id(self.rank_id, field="enemy rank id"))
        if self.minimum_count < 1 or self.maximum_count < self.minimum_count:
            raise ValueError("敌人生成数量边界无效")
        if self.behavior_count is not None and self.behavior_count < 0:
            raise ValueError("敌人生成行为数量不能小于 0")
        ratios = tuple(float(value) for value in self.phase_health_ratios)
        if any(not 0 < value < 1 for value in ratios):
            raise ValueError("敌人生成阶段阈值必须位于 0 到 1")
        if len(ratios) != len(set(ratios)):
            raise ValueError("敌人生成阶段阈值不能重复")
        object.__setattr__(
            self,
            "phase_health_ratios",
            tuple(sorted(ratios, reverse=True)),
        )


@dataclass(frozen=True)
class EnemyEncounterDefinition:
    id: StableId
    scope_id: StableId
    minimum_level: int
    maximum_level: int
    spawns: tuple[EnemySpawnDefinition, ...]
    tags: TagSet = EMPTY_TAGS

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="enemy encounter id"))
        object.__setattr__(self, "scope_id", stable_id(self.scope_id, field="encounter scope id"))
        if self.minimum_level < 1 or self.maximum_level < self.minimum_level:
            raise ValueError("敌人遭遇等级边界无效")
        spawns = tuple(self.spawns)
        if not spawns:
            raise ValueError("敌人遭遇必须包含生成槽")
        object.__setattr__(self, "spawns", spawns)


@dataclass(frozen=True)
class EnemyInstance:
    id: str
    definition_id: StableId
    level: int
    rank_id: StableId
    behavior_ids: tuple[StableId, ...]
    generation_seed: str
    content_version: str
    phase_loadouts: tuple[EnemyPhaseLoadout, ...] = ()

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.generation_seed.strip() or not self.content_version.strip():
            raise ValueError("敌人实例缺少稳定身份、种子或内容版本")
        if self.level < 1:
            raise ValueError("敌人实例等级必须大于 0")
        object.__setattr__(self, "definition_id", stable_id(self.definition_id, field="enemy id"))
        object.__setattr__(self, "rank_id", stable_id(self.rank_id, field="enemy rank id"))
        behaviors = tuple(stable_id(value, field="enemy behavior id") for value in self.behavior_ids)
        if len(behaviors) != len(set(behaviors)):
            raise ValueError("敌人实例行为不能重复")
        object.__setattr__(self, "behavior_ids", behaviors)
        phases = tuple(
            sorted(self.phase_loadouts, key=lambda value: value.health_ratio, reverse=True)
        )
        if len({value.id for value in phases}) != len(phases):
            raise ValueError("敌人实例阶段 ID 不能重复")
        all_behaviors = [*behaviors]
        for phase in phases:
            all_behaviors.extend(phase.behavior_ids)
        if len(all_behaviors) != len(set(all_behaviors)):
            raise ValueError("敌人开场与阶段行为不能重复")
        object.__setattr__(self, "phase_loadouts", phases)


@dataclass(frozen=True)
class EnemyEncounterInstance:
    id: str
    definition_id: StableId
    scope_id: StableId
    level: int
    enemies: tuple[EnemyInstance, ...]
    generation_seed: str
    content_version: str

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.generation_seed.strip() or not self.content_version.strip():
            raise ValueError("遭遇实例缺少稳定身份、种子或内容版本")
        object.__setattr__(self, "definition_id", stable_id(self.definition_id, field="enemy encounter id"))
        object.__setattr__(self, "scope_id", stable_id(self.scope_id, field="encounter scope id"))
        if self.level < 1 or not self.enemies:
            raise ValueError("遭遇实例等级或敌人集合无效")
        if len({value.id for value in self.enemies}) != len(self.enemies):
            raise ValueError("遭遇实例中的敌人 ID 不能重复")
        object.__setattr__(self, "enemies", tuple(self.enemies))


__all__ = [
    "ENCOUNTER_SCOPE_GLOBAL_ID",
    "ENCOUNTER_SCOPE_PARTY_ID",
    "ENCOUNTER_SCOPE_PERSONAL_ID",
    "ENEMY_RANK_BOSS_ID",
    "ENEMY_RANK_ELITE_ID",
    "ENEMY_RANK_NORMAL_ID",
    "EncounterScopeDefinition",
    "EnemyBehaviorDefinition",
    "EnemyDefinition",
    "EnemyEncounterDefinition",
    "EnemyEncounterInstance",
    "EnemyInstance",
    "EnemyLevelProfileDefinition",
    "EnemyPhaseLoadout",
    "EnemyRankDefinition",
    "EnemyRewardProfileDefinition",
    "EnemySpawnDefinition",
]
