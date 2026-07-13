"""武器定义、品质等级表和实例成长状态。"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from ..attributes import ModifierLayer
from ..character import AttributeGrant, ContributionSpec
from ..ids import StableId, stable_id
from ..inventory import ItemAssetKind, ItemCatalog
from ..loadout import (
    LOADOUT_ITEM_COMPONENT_ID,
    WEAPON_SLOT_ID,
    LoadoutItemComponent,
    QualityCatalog,
)
from ..registry import DefinitionRegistry


@dataclass(frozen=True)
class WeaponLevelAttribute:
    """一个属性在每个武器等级的完整贡献值，不使用隐藏成长公式。"""

    attribute_id: StableId
    layer: ModifierLayer
    values: tuple[float, ...]
    priority: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "attribute_id", stable_id(self.attribute_id, field="weapon attribute id"))
        object.__setattr__(self, "layer", ModifierLayer(self.layer))
        values = tuple(float(value) for value in self.values)
        if not values:
            raise ValueError("WeaponLevelAttribute.values 不能为空")
        object.__setattr__(self, "values", values)


@dataclass(frozen=True)
class WeaponQualityProfile:
    quality_id: StableId
    experience_requirements: tuple[int, ...]
    contribution: ContributionSpec = ContributionSpec()
    level_attributes: tuple[WeaponLevelAttribute, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "quality_id", stable_id(self.quality_id, field="quality id"))
        requirements = tuple(int(value) for value in self.experience_requirements)
        if any(value < 1 for value in requirements):
            raise ValueError("武器升级经验需求必须全部大于 0")
        object.__setattr__(self, "experience_requirements", requirements)
        for progression in self.level_attributes:
            if len(progression.values) != self.maximum_level:
                raise ValueError(
                    f"武器属性 {progression.attribute_id} 的等级值数量必须等于 {self.maximum_level}"
                )

    @property
    def maximum_level(self) -> int:
        return len(self.experience_requirements) + 1

    def required_for_next_level(self, level: int) -> int | None:
        if level < 1:
            raise ValueError("武器等级必须大于 0")
        if level >= self.maximum_level:
            return None
        return self.experience_requirements[level - 1]


@dataclass(frozen=True)
class WeaponDefinition:
    id: StableId
    item_definition_id: StableId
    base_contribution: ContributionSpec
    quality_profiles: Mapping[StableId, WeaponQualityProfile]

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="weapon id"))
        object.__setattr__(
            self,
            "item_definition_id",
            stable_id(self.item_definition_id, field="item id"),
        )
        profiles = dict(self.quality_profiles)
        if not profiles:
            raise ValueError("WeaponDefinition.quality_profiles 不能为空")
        for key, profile in profiles.items():
            if stable_id(key, field="quality id") != profile.quality_id:
                raise ValueError("武器品质档案映射键与 quality_id 不一致")
        object.__setattr__(self, "quality_profiles", MappingProxyType(profiles))


@dataclass(frozen=True)
class WeaponState:
    asset_id: str
    definition_id: StableId
    quality_id: StableId
    level: int = 1
    experience: int = 0
    total_experience: int = 0
    revision: int = 0

    def __post_init__(self) -> None:
        if not self.asset_id.strip():
            raise ValueError("WeaponState 缺少 asset_id")
        object.__setattr__(self, "definition_id", stable_id(self.definition_id, field="weapon id"))
        object.__setattr__(self, "quality_id", stable_id(self.quality_id, field="quality id"))
        for field_name in ("level", "experience", "total_experience", "revision"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"WeaponState.{field_name} 必须是整数")
        if self.level < 1 or self.experience < 0 or self.total_experience < 0:
            raise ValueError("武器等级和经验不能小于有效边界")
        if self.experience > self.total_experience:
            raise ValueError("武器当前经验不能大于累计经验")
        if self.revision < 0:
            raise ValueError("WeaponState.revision 不能小于 0")


class WeaponCatalog:
    def __init__(self, qualities: QualityCatalog, items: ItemCatalog) -> None:
        self.qualities = qualities
        self.items = items
        self.definitions = DefinitionRegistry[WeaponDefinition]("Weapon")
        self._finalized = False

    def register(self, definition: WeaponDefinition) -> WeaponDefinition:
        if self._finalized:
            raise RuntimeError("武器目录已经完成组装")
        return self.definitions.register(definition)

    def require(self, definition_id: StableId) -> WeaponDefinition:
        return self.definitions.require(definition_id)

    def finalize(self) -> None:
        if self._finalized:
            return
        if not self.qualities.finalized:
            self.qualities.finalize()
        if not self.items.finalized:
            self.items.finalize()
        quality_ids = set(self.qualities.definitions.ids())
        used_items: set[StableId] = set()
        for definition in self.definitions:
            unknown = set(definition.quality_profiles) - quality_ids
            if unknown:
                raise KeyError(
                    f"武器 {definition.id} 引用了未知品质：{', '.join(sorted(unknown))}"
                )
            if definition.item_definition_id in used_items:
                raise ValueError(f"物品定义重复绑定武器：{definition.item_definition_id}")
            used_items.add(definition.item_definition_id)
            item = self.items.require(definition.item_definition_id)
            if item.asset_kind is not ItemAssetKind.INSTANCE or not item.tags.has("item.weapon"):
                raise ValueError(f"武器 {definition.id} 必须绑定带 item.weapon 标签的独立物品")
            component = item.component(LOADOUT_ITEM_COMPONENT_ID, LoadoutItemComponent)
            if component.allowed_slot_ids != frozenset({WEAPON_SLOT_ID}):
                raise ValueError(f"武器 {definition.id} 只能进入唯一武器槽")
        self.definitions.freeze()
        self._finalized = True

    @property
    def finalized(self) -> bool:
        return self._finalized

    def create_state(
        self,
        *,
        asset_id: str,
        definition_id: StableId,
        quality_id: StableId,
    ) -> WeaponState:
        if not self._finalized:
            self.finalize()
        definition = self.require(definition_id)
        if quality_id not in definition.quality_profiles:
            raise KeyError(f"武器 {definition.id} 不支持品质：{quality_id}")
        return WeaponState(asset_id, definition.id, quality_id)


def weapon_level_contribution(
    profile: WeaponQualityProfile,
    level: int,
) -> ContributionSpec:
    if level < 1 or level > profile.maximum_level:
        raise ValueError("武器等级超过品质档案范围")
    return ContributionSpec(
        attributes=tuple(
            AttributeGrant(
                progression.attribute_id,
                progression.layer,
                progression.values[level - 1],
                priority=progression.priority,
            )
            for progression in profile.level_attributes
        )
    )


__all__ = [
    "WeaponCatalog",
    "WeaponDefinition",
    "WeaponLevelAttribute",
    "WeaponQualityProfile",
    "WeaponState",
    "weapon_level_contribution",
]
