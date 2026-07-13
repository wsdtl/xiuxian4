"""角色永久特征和外部系统使用的统一数值贡献协议。"""

from __future__ import annotations

from dataclasses import dataclass

from ..attributes import ModifierLayer
from ..ids import StableId, stable_id
from ..tags import EMPTY_TAGS, TagSet


@dataclass(frozen=True)
class AttributeGrant:
    """尚未绑定运行来源的一条属性贡献。"""

    attribute_id: StableId
    layer: ModifierLayer
    value: float
    required_tags: TagSet = EMPTY_TAGS
    blocked_tags: TagSet = EMPTY_TAGS
    priority: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "attribute_id",
            stable_id(self.attribute_id, field="contribution attribute id"),
        )
        object.__setattr__(self, "layer", ModifierLayer(self.layer))


@dataclass(frozen=True)
class ContributionSpec:
    """一种来源可以投影给规则实体的全部能力。"""

    attributes: tuple[AttributeGrant, ...] = ()
    tags: TagSet = EMPTY_TAGS
    abilities: frozenset[StableId] = frozenset()
    triggers: frozenset[StableId] = frozenset()
    interceptors: frozenset[StableId] = frozenset()
    target_constraints: frozenset[StableId] = frozenset()

    def __post_init__(self) -> None:
        for field_name, label in (
            ("abilities", "ability id"),
            ("triggers", "trigger id"),
            ("interceptors", "interceptor id"),
            ("target_constraints", "target constraint id"),
        ):
            values = frozenset(stable_id(value, field=label) for value in getattr(self, field_name))
            object.__setattr__(self, field_name, values)


@dataclass(frozen=True)
class CharacterFeatureDefinition:
    """角色永久拥有的一项体质、血脉、天赋或其他特征。"""

    id: StableId
    contribution: ContributionSpec = ContributionSpec()

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="character feature id"))


@dataclass(frozen=True)
class CharacterContribution:
    """装备、宗门、场景等外部系统提交的一份带来源贡献。"""

    id: StableId
    source_kind: StableId
    source_id: str
    contribution: ContributionSpec

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="contribution id"))
        object.__setattr__(self, "source_kind", stable_id(self.source_kind, field="source kind"))
        if not self.source_id.strip():
            raise ValueError("CharacterContribution 缺少 source_id")


def merge_contribution_specs(*specs: ContributionSpec) -> ContributionSpec:
    """按来源顺序合并贡献积木，不解释任何具体玩法。"""

    return ContributionSpec(
        attributes=tuple(grant for spec in specs for grant in spec.attributes),
        tags=EMPTY_TAGS.merged(*(spec.tags for spec in specs)),
        abilities=frozenset(value for spec in specs for value in spec.abilities),
        triggers=frozenset(value for spec in specs for value in spec.triggers),
        interceptors=frozenset(value for spec in specs for value in spec.interceptors),
        target_constraints=frozenset(
            value for spec in specs for value in spec.target_constraints
        ),
    )


__all__ = [
    "AttributeGrant",
    "CharacterContribution",
    "CharacterFeatureDefinition",
    "ContributionSpec",
    "merge_contribution_specs",
]
