"""六槽装备的流派、品质和实例状态。"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from ..character import CharacterContribution, ContributionSpec, merge_contribution_specs
from ..ids import StableId, stable_id
from ..inventory import ItemAssetKind, ItemCatalog
from ..loadout import (
    EQUIPMENT_SLOT_IDS,
    LOADOUT_ITEM_COMPONENT_ID,
    LoadoutItemComponent,
    LoadoutSlotCatalog,
    QualityCatalog,
)
from ..registry import DefinitionRegistry
from ..tags import EMPTY_TAGS, TagSet


@dataclass(frozen=True)
class EquipmentStyleDefinition:
    """装备流派的稳定身份和规则标签，不包含玩家可见名称。"""

    id: StableId
    tags: TagSet = EMPTY_TAGS

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="equipment style id"))


@dataclass(frozen=True)
class EquipmentQualityProfile:
    quality_id: StableId
    contribution: ContributionSpec

    def __post_init__(self) -> None:
        object.__setattr__(self, "quality_id", stable_id(self.quality_id, field="quality id"))


@dataclass(frozen=True)
class EquipmentDefinition:
    """槽位和流派固定，品质只选择对应的明确贡献参数。"""

    id: StableId
    item_definition_id: StableId
    slot_id: StableId
    style_id: StableId
    base_contribution: ContributionSpec = ContributionSpec()
    quality_profiles: Mapping[StableId, EquipmentQualityProfile] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="equipment id"))
        object.__setattr__(
            self,
            "item_definition_id",
            stable_id(self.item_definition_id, field="item id"),
        )
        object.__setattr__(self, "slot_id", stable_id(self.slot_id, field="equipment slot id"))
        object.__setattr__(self, "style_id", stable_id(self.style_id, field="equipment style id"))
        if self.slot_id not in EQUIPMENT_SLOT_IDS:
            raise ValueError(f"装备定义不能使用非装备槽：{self.slot_id}")
        profiles = dict(self.quality_profiles)
        if not profiles:
            raise ValueError("EquipmentDefinition.quality_profiles 不能为空")
        for key, profile in profiles.items():
            if stable_id(key, field="quality id") != profile.quality_id:
                raise ValueError("装备品质档案映射键与 quality_id 不一致")
        object.__setattr__(self, "quality_profiles", MappingProxyType(profiles))


@dataclass(frozen=True)
class EquipmentState:
    """装备实例只有定义和品质，没有等级、经验或附魔状态。"""

    asset_id: str
    definition_id: StableId
    quality_id: StableId

    def __post_init__(self) -> None:
        if not self.asset_id.strip():
            raise ValueError("EquipmentState 缺少 asset_id")
        object.__setattr__(self, "definition_id", stable_id(self.definition_id, field="equipment id"))
        object.__setattr__(self, "quality_id", stable_id(self.quality_id, field="quality id"))


class EquipmentCatalog:
    def __init__(
        self,
        qualities: QualityCatalog,
        slots: LoadoutSlotCatalog,
        items: ItemCatalog,
    ) -> None:
        self.qualities = qualities
        self.slots = slots
        self.items = items
        self.styles = DefinitionRegistry[EquipmentStyleDefinition]("EquipmentStyle")
        self.definitions = DefinitionRegistry[EquipmentDefinition]("Equipment")
        self._finalized = False

    def register_style(self, definition: EquipmentStyleDefinition) -> EquipmentStyleDefinition:
        if self._finalized:
            raise RuntimeError("装备目录已经完成组装")
        return self.styles.register(definition)

    def register(self, definition: EquipmentDefinition) -> EquipmentDefinition:
        if self._finalized:
            raise RuntimeError("装备目录已经完成组装")
        return self.definitions.register(definition)

    def require(self, definition_id: StableId) -> EquipmentDefinition:
        return self.definitions.require(definition_id)

    def finalize(self) -> None:
        if self._finalized:
            return
        if not self.qualities.finalized:
            self.qualities.finalize()
        if not self.slots.finalized:
            self.slots.finalize()
        if not self.items.finalized:
            self.items.finalize()
        quality_ids = set(self.qualities.definitions.ids())
        style_ids = set(self.styles.ids())
        used_items: set[StableId] = set()
        combinations: set[tuple[StableId, StableId]] = set()
        for definition in self.definitions:
            if definition.style_id not in style_ids:
                raise KeyError(
                    f"装备 {definition.id} 引用了未知流派：{definition.style_id}"
                )
            unknown = set(definition.quality_profiles) - quality_ids
            if unknown:
                raise KeyError(
                    f"装备 {definition.id} 引用了未知品质：{', '.join(sorted(unknown))}"
                )
            combination = (definition.slot_id, definition.style_id)
            if combination in combinations:
                raise ValueError(
                    f"装备槽位与流派组合重复：{definition.slot_id} + {definition.style_id}"
                )
            combinations.add(combination)
            if definition.item_definition_id in used_items:
                raise ValueError(f"物品定义重复绑定装备：{definition.item_definition_id}")
            used_items.add(definition.item_definition_id)
            item = self.items.require(definition.item_definition_id)
            if item.asset_kind is not ItemAssetKind.INSTANCE or not item.tags.has("item.equipment"):
                raise ValueError(f"装备 {definition.id} 必须绑定带 item.equipment 标签的独立物品")
            component = item.component(LOADOUT_ITEM_COMPONENT_ID, LoadoutItemComponent)
            if component.allowed_slot_ids != frozenset({definition.slot_id}):
                raise ValueError(
                    f"装备 {definition.id} 的物品组件必须只允许槽位 {definition.slot_id}"
                )
        self.styles.freeze()
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
    ) -> EquipmentState:
        if not self._finalized:
            self.finalize()
        definition = self.require(definition_id)
        if quality_id not in definition.quality_profiles:
            raise KeyError(f"装备 {definition.id} 不支持品质：{quality_id}")
        return EquipmentState(asset_id, definition.id, quality_id)


class EquipmentContributionProvider:
    def __init__(self, catalog: EquipmentCatalog) -> None:
        if not catalog.finalized:
            catalog.finalize()
        self.catalog = catalog

    def contribution(self, state: EquipmentState) -> CharacterContribution:
        definition = self.catalog.require(state.definition_id)
        try:
            profile = definition.quality_profiles[state.quality_id]
        except KeyError as exc:
            raise KeyError(f"装备 {definition.id} 不支持品质：{state.quality_id}") from exc
        style = self.catalog.styles.require(definition.style_id)
        style_spec = ContributionSpec(tags=style.tags)
        return CharacterContribution(
            definition.id,
            "source.equipment_instance",
            state.asset_id,
            merge_contribution_specs(
                style_spec,
                definition.base_contribution,
                profile.contribution,
            ),
        )


__all__ = [
    "EquipmentCatalog",
    "EquipmentContributionProvider",
    "EquipmentDefinition",
    "EquipmentQualityProfile",
    "EquipmentState",
    "EquipmentStyleDefinition",
]
