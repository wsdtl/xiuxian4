"""角色模板、成长曲线、里程碑和内容目录。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Mapping

from ..attributes import AttributeDefinition, ResourceDefinition
from ..ids import StableId, stable_id
from ..registry import DefinitionRegistry
from ..tags import EMPTY_TAGS, TagSet
from .contributions import CharacterFeatureDefinition
from .models import (
    COMBAT_ATTACK,
    COMBAT_DEFENSE,
    COMBAT_SPEED,
    CORE_ATTRIBUTE_IDS,
    CharacterState,
    HEALTH_CURRENT,
    HEALTH_MAXIMUM,
    ProgressionState,
    SPIRIT_CURRENT,
    SPIRIT_MAXIMUM,
)


@dataclass(frozen=True)
class ProgressionMilestone:
    """达到某一级时一次性写入角色永久状态的奖励。"""

    level: int
    core_attribute_deltas: Mapping[StableId, float] = field(default_factory=dict)
    feature_ids: frozenset[StableId] = frozenset()

    def __post_init__(self) -> None:
        if self.level < 2:
            raise ValueError("成长里程碑从 2 级开始，初始内容应写入角色模板")
        deltas = {
            stable_id(key, field="core attribute id"): float(value)
            for key, value in self.core_attribute_deltas.items()
        }
        unknown = set(deltas) - CORE_ATTRIBUTE_IDS
        if unknown:
            raise ValueError(f"成长里程碑不能修改非核心属性：{', '.join(sorted(unknown))}")
        features = frozenset(stable_id(value, field="feature id") for value in self.feature_ids)
        object.__setattr__(self, "core_attribute_deltas", MappingProxyType(deltas))
        object.__setattr__(self, "feature_ids", features)


@dataclass(frozen=True)
class ProgressionDefinition:
    """显式经验数值表；第一个值表示 1 级升到 2 级的需求。"""

    id: StableId
    experience_requirements: tuple[int, ...]
    milestones: Mapping[int, ProgressionMilestone] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="progression id"))
        requirements = tuple(int(value) for value in self.experience_requirements)
        if any(value < 1 for value in requirements):
            raise ValueError("成长经验需求必须全部大于 0")
        milestones = dict(self.milestones)
        for level, milestone in milestones.items():
            if int(level) != milestone.level:
                raise ValueError("成长里程碑映射键与 level 不一致")
            if milestone.level > len(requirements) + 1:
                raise ValueError(f"成长里程碑超过轨道最高等级：{milestone.level}")
        object.__setattr__(self, "experience_requirements", requirements)
        object.__setattr__(self, "milestones", MappingProxyType(milestones))

    @property
    def maximum_level(self) -> int:
        return len(self.experience_requirements) + 1

    def required_for_next_level(self, level: int) -> int | None:
        if level < 1:
            raise ValueError("成长等级必须大于 0")
        if level >= self.maximum_level:
            return None
        return self.experience_requirements[level - 1]


@dataclass(frozen=True)
class CharacterTemplateDefinition:
    """新角色的五项核心值、初始成长轨道和初始永久特征。"""

    id: StableId
    core_attributes: Mapping[StableId, float]
    progression_ids: frozenset[StableId] = frozenset()
    feature_ids: frozenset[StableId] = frozenset()
    tags: TagSet = EMPTY_TAGS

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="character template id"))
        attributes = {
            stable_id(key, field="core attribute id"): float(value)
            for key, value in self.core_attributes.items()
        }
        if set(attributes) != set(CORE_ATTRIBUTE_IDS):
            raise ValueError("角色模板必须且只能定义五项核心属性")
        # 复用 CharacterState 的完整边界校验，避免模板和运行状态产生两套规则。
        CharacterState(
            "template-validation",
            "template-validation",
            self.id,
            datetime(2000, 1, 1, tzinfo=timezone.utc),
            attributes,
            {
                HEALTH_CURRENT: attributes[HEALTH_MAXIMUM],
                SPIRIT_CURRENT: attributes[SPIRIT_MAXIMUM],
            },
        )
        progressions = frozenset(stable_id(value, field="progression id") for value in self.progression_ids)
        features = frozenset(stable_id(value, field="feature id") for value in self.feature_ids)
        object.__setattr__(self, "core_attributes", MappingProxyType(attributes))
        object.__setattr__(self, "progression_ids", progressions)
        object.__setattr__(self, "feature_ids", features)


class CharacterCatalog:
    """角色模板、成长轨道和永久特征的启动期目录。"""

    def __init__(self) -> None:
        self.templates = DefinitionRegistry[CharacterTemplateDefinition]("CharacterTemplate")
        self.progressions = DefinitionRegistry[ProgressionDefinition]("Progression")
        self.features = DefinitionRegistry[CharacterFeatureDefinition]("CharacterFeature")
        self._finalized = False

    def finalize(self) -> None:
        if self._finalized:
            return
        progression_ids = set(self.progressions.ids())
        feature_ids = set(self.features.ids())
        for progression in self.progressions:
            for milestone in progression.milestones.values():
                unknown = set(milestone.feature_ids) - feature_ids
                if unknown:
                    raise KeyError(
                        f"成长轨道 {progression.id} 引用了未知永久特征："
                        f"{', '.join(sorted(unknown))}"
                    )
        for template in self.templates:
            unknown_progressions = set(template.progression_ids) - progression_ids
            unknown_features = set(template.feature_ids) - feature_ids
            if unknown_progressions:
                raise KeyError(
                    f"角色模板 {template.id} 引用了未知成长轨道："
                    f"{', '.join(sorted(unknown_progressions))}"
                )
            if unknown_features:
                raise KeyError(
                    f"角色模板 {template.id} 引用了未知永久特征："
                    f"{', '.join(sorted(unknown_features))}"
                )
        self.templates.freeze()
        self.progressions.freeze()
        self.features.freeze()
        self._finalized = True

    @property
    def finalized(self) -> bool:
        return self._finalized

    def create_character(
        self,
        *,
        character_id: str,
        account_id: str,
        template_id: StableId,
        created_at: datetime,
    ) -> CharacterState:
        if not self._finalized:
            self.finalize()
        template = self.templates.require(template_id)
        return CharacterState(
            character_id,
            account_id,
            template.id,
            created_at,
            template.core_attributes,
            {
                HEALTH_CURRENT: template.core_attributes[HEALTH_MAXIMUM],
                SPIRIT_CURRENT: template.core_attributes[SPIRIT_MAXIMUM],
            },
            {
                progression_id: ProgressionState(progression_id)
                for progression_id in template.progression_ids
            },
            template.feature_ids,
        )


def core_attribute_definitions() -> dict[StableId, AttributeDefinition]:
    """五项核心属性的标准边界，不设置统一数值上限。"""

    return {
        HEALTH_MAXIMUM: AttributeDefinition(HEALTH_MAXIMUM, minimum=1),
        SPIRIT_MAXIMUM: AttributeDefinition(SPIRIT_MAXIMUM, minimum=0),
        COMBAT_ATTACK: AttributeDefinition(COMBAT_ATTACK, minimum=0),
        COMBAT_DEFENSE: AttributeDefinition(COMBAT_DEFENSE),
        COMBAT_SPEED: AttributeDefinition(COMBAT_SPEED, minimum=0),
    }


def persistent_resource_definitions() -> dict[StableId, ResourceDefinition]:
    """当前血气和当前灵力的标准资源定义。"""

    return {
        HEALTH_CURRENT: ResourceDefinition(HEALTH_CURRENT, maximum_attribute=HEALTH_MAXIMUM),
        SPIRIT_CURRENT: ResourceDefinition(SPIRIT_CURRENT, maximum_attribute=SPIRIT_MAXIMUM),
    }


__all__ = [
    "CharacterCatalog",
    "CharacterTemplateDefinition",
    "ProgressionDefinition",
    "ProgressionMilestone",
    "core_attribute_definitions",
    "persistent_resource_definitions",
]
