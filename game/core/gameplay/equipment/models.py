"""六槽装备的底座族、品质、套装印记和实例状态。"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from ..character import CharacterContribution, ContributionSpec, merge_contribution_specs
from ..ids import StableId, stable_id
from ..inventory import ItemAssetKind, ItemCatalog, ItemInstance
from ..itemization import ItemRollState, ItemizationEngine, ItemizationKind
from ..loadout import (
    EQUIPMENT_SLOT_IDS,
    LOADOUT_ITEM_COMPONENT_ID,
    LoadoutItemComponent,
    LoadoutSlotCatalog,
    QualityCatalog,
)
from ..registry import DefinitionRegistry
from ..tags import EMPTY_TAGS, TagSet


EQUIPMENT_STATE_DATA_KEY = "equipment.state"


@dataclass(frozen=True)
class EquipmentFamilyDefinition:
    """有限装备底座族的稳定身份，不限制随机属性或套装。"""

    id: StableId
    tags: TagSet = EMPTY_TAGS

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="equipment family id"))


@dataclass(frozen=True)
class EquipmentQualityProfile:
    quality_id: StableId
    contribution: ContributionSpec

    def __post_init__(self) -> None:
        object.__setattr__(self, "quality_id", stable_id(self.quality_id, field="quality id"))


@dataclass(frozen=True)
class EquipmentSetBonus:
    required_pieces: int
    contribution: ContributionSpec

    def __post_init__(self) -> None:
        if self.required_pieces < 2:
            raise ValueError("套装加成至少需要两件装备")


@dataclass(frozen=True)
class EquipmentSetDefinition:
    id: StableId
    bonuses: tuple[EquipmentSetBonus, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="equipment set id"))
        bonuses = tuple(self.bonuses)
        thresholds = [value.required_pieces for value in bonuses]
        if not bonuses or thresholds != sorted(thresholds) or len(thresholds) != len(set(thresholds)):
            raise ValueError("套装加成件数必须非空、严格递增且不能重复")
        if thresholds[-1] > len(EQUIPMENT_SLOT_IDS):
            raise ValueError("套装加成件数不能超过标准装备槽数量")
        object.__setattr__(self, "bonuses", bonuses)


@dataclass(frozen=True)
class EquipmentDefinition:
    """槽位和底座族固定；随机属性与套装印记属于具体实例。"""

    id: StableId
    item_definition_id: StableId
    slot_id: StableId
    family_id: StableId
    base_contribution: ContributionSpec = ContributionSpec()
    quality_profiles: Mapping[StableId, EquipmentQualityProfile] = field(default_factory=dict)
    generation_profile_id: StableId | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="equipment id"))
        object.__setattr__(
            self,
            "item_definition_id",
            stable_id(self.item_definition_id, field="item id"),
        )
        object.__setattr__(self, "slot_id", stable_id(self.slot_id, field="equipment slot id"))
        object.__setattr__(
            self,
            "family_id",
            stable_id(self.family_id, field="equipment family id"),
        )
        if self.slot_id not in EQUIPMENT_SLOT_IDS:
            raise ValueError(f"装备定义不能使用非装备槽：{self.slot_id}")
        profiles = dict(self.quality_profiles)
        if not profiles:
            raise ValueError("EquipmentDefinition.quality_profiles 不能为空")
        for key, profile in profiles.items():
            if stable_id(key, field="quality id") != profile.quality_id:
                raise ValueError("装备品质档案映射键与 quality_id 不一致")
        object.__setattr__(self, "quality_profiles", MappingProxyType(profiles))
        if self.generation_profile_id is not None:
            object.__setattr__(
                self,
                "generation_profile_id",
                stable_id(self.generation_profile_id, field="generation profile id"),
            )


@dataclass(frozen=True)
class EquipmentState:
    """装备实例没有成长等级；随机属性由不可变生成凭据完整保存。"""

    asset_id: str
    definition_id: StableId
    quality_id: StableId
    roll: ItemRollState | None = None
    set_id: StableId | None = None

    def __post_init__(self) -> None:
        if not self.asset_id.strip():
            raise ValueError("EquipmentState 缺少 asset_id")
        object.__setattr__(self, "definition_id", stable_id(self.definition_id, field="equipment id"))
        object.__setattr__(self, "quality_id", stable_id(self.quality_id, field="quality id"))
        if self.set_id is not None:
            object.__setattr__(self, "set_id", stable_id(self.set_id, field="equipment set id"))


class EquipmentCatalog:
    def __init__(
        self,
        qualities: QualityCatalog,
        slots: LoadoutSlotCatalog,
        items: ItemCatalog,
        itemization: ItemizationEngine | None = None,
    ) -> None:
        self.qualities = qualities
        self.slots = slots
        self.items = items
        self.itemization = itemization
        self.families = DefinitionRegistry[EquipmentFamilyDefinition]("EquipmentFamily")
        self.sets = DefinitionRegistry[EquipmentSetDefinition]("EquipmentSet")
        self.definitions = DefinitionRegistry[EquipmentDefinition]("Equipment")
        self._finalized = False

    def register_family(self, definition: EquipmentFamilyDefinition) -> EquipmentFamilyDefinition:
        if self._finalized:
            raise RuntimeError("装备目录已经完成组装")
        return self.families.register(definition)

    def register(self, definition: EquipmentDefinition) -> EquipmentDefinition:
        if self._finalized:
            raise RuntimeError("装备目录已经完成组装")
        return self.definitions.register(definition)

    def register_set(self, definition: EquipmentSetDefinition) -> EquipmentSetDefinition:
        if self._finalized:
            raise RuntimeError("装备目录已经完成组装")
        return self.sets.register(definition)

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
        family_ids = set(self.families.ids())
        used_items: set[StableId] = set()
        combinations: set[tuple[StableId, StableId]] = set()
        for definition in self.definitions:
            if definition.family_id not in family_ids:
                raise KeyError(
                    f"装备 {definition.id} 引用了未知底座族：{definition.family_id}"
                )
            unknown = set(definition.quality_profiles) - quality_ids
            if unknown:
                raise KeyError(
                    f"装备 {definition.id} 引用了未知品质：{', '.join(sorted(unknown))}"
                )
            combination = (definition.slot_id, definition.family_id)
            if combination in combinations:
                raise ValueError(
                    f"装备槽位与底座族组合重复：{definition.slot_id} + {definition.family_id}"
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
            if definition.generation_profile_id is not None:
                if self.itemization is None:
                    raise ValueError(f"生成型装备 {definition.id} 缺少物品化引擎")
                generation = self.itemization.catalog.require_profile(
                    definition.generation_profile_id
                )
                if generation.kind is not ItemizationKind.EQUIPMENT:
                    raise ValueError(f"装备 {definition.id} 引用了非装备生成策略")
                unknown_qualities = {
                    band.quality_id for band in generation.quality_bands
                } - set(definition.quality_profiles)
                if unknown_qualities:
                    raise KeyError(
                        f"装备 {definition.id} 的生成策略产出未配置品质："
                        + ", ".join(sorted(unknown_qualities))
                    )
        self.families.freeze()
        self.sets.freeze()
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
        roll: ItemRollState | None = None,
        set_id: StableId | None = None,
    ) -> EquipmentState:
        if not self._finalized:
            self.finalize()
        definition = self.require(definition_id)
        if quality_id not in definition.quality_profiles:
            raise KeyError(f"装备 {definition.id} 不支持品质：{quality_id}")
        if definition.generation_profile_id is None:
            if roll is not None:
                raise ValueError(f"固定装备 {definition.id} 不能携带随机属性")
        else:
            if roll is None:
                raise ValueError(f"生成型装备 {definition.id} 必须携带随机属性")
            if roll.profile_id != definition.generation_profile_id:
                raise ValueError("装备随机属性策略与定义不一致")
            if roll.quality_id != quality_id:
                raise ValueError("装备随机属性品质与实例品质不一致")
            assert self.itemization is not None
            self.itemization.validate_roll(roll)
        if set_id is not None:
            self.sets.require(set_id)
        return EquipmentState(asset_id, definition.id, quality_id, roll, set_id)


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
        family = self.catalog.families.require(definition.family_id)
        family_spec = ContributionSpec(tags=family.tags)
        return CharacterContribution(
            definition.id,
            "source.equipment_instance",
            state.asset_id,
            merge_contribution_specs(
                family_spec,
                definition.base_contribution,
                profile.contribution,
                self._random_contribution(definition, state),
            ),
        )

    def contributions(
        self,
        states: tuple[EquipmentState, ...],
    ) -> tuple[CharacterContribution, ...]:
        """一次返回全部单件与套装贡献，避免上层漏算套装。"""

        items = tuple(self.contribution(state) for state in states)
        return (*items, *self.set_contributions(states))

    def set_contributions(
        self,
        states: tuple[EquipmentState, ...],
    ) -> tuple[CharacterContribution, ...]:
        if len({state.asset_id for state in states}) != len(states):
            raise ValueError("套装统计不能重复传入同一个装备实例")
        slots = [self.catalog.require(state.definition_id).slot_id for state in states]
        if len(set(slots)) != len(slots):
            raise ValueError("套装统计不能在同一装备槽传入多个实例")
        counts: dict[StableId, int] = {}
        for state in states:
            self.catalog.require(state.definition_id)
            if state.set_id is not None:
                self.catalog.sets.require(state.set_id)
                counts[state.set_id] = counts.get(state.set_id, 0) + 1
        result = []
        for set_id, count in sorted(counts.items()):
            definition = self.catalog.sets.require(set_id)
            for bonus in definition.bonuses:
                if count >= bonus.required_pieces:
                    result.append(
                        CharacterContribution(
                            f"{set_id}.bonus.pieces_{bonus.required_pieces}",
                            "source.equipment_set",
                            set_id,
                            bonus.contribution,
                        )
                    )
        return tuple(result)

    def _random_contribution(
        self,
        definition: EquipmentDefinition,
        state: EquipmentState,
    ) -> ContributionSpec:
        if definition.generation_profile_id is None:
            if state.roll is not None:
                raise ValueError("固定装备实例不能携带随机属性")
            return ContributionSpec()
        if state.roll is None or state.roll.profile_id != definition.generation_profile_id:
            raise ValueError("生成型装备实例缺少有效随机属性")
        if state.roll.quality_id != state.quality_id:
            raise ValueError("生成型装备实例品质与随机属性不一致")
        if self.catalog.itemization is None:
            raise RuntimeError("生成型装备目录缺少物品化引擎")
        return self.catalog.itemization.validate_roll(state.roll)


def equipment_state_data(state: EquipmentState) -> Mapping[str, object]:
    """生成库存实例时使用的稳定类型化数据入口。"""

    return MappingProxyType({EQUIPMENT_STATE_DATA_KEY: state})


def equipment_state_from_data(data: Mapping[str, object]) -> EquipmentState:
    try:
        state = data[EQUIPMENT_STATE_DATA_KEY]
    except KeyError as exc:
        raise KeyError("物品实例缺少装备状态") from exc
    if not isinstance(state, EquipmentState):
        raise TypeError("物品实例中的装备状态类型不正确")
    return state


def equipment_state_from_instance(instance: ItemInstance) -> EquipmentState:
    state = equipment_state_from_data(instance.data)
    if state.asset_id != instance.id:
        raise ValueError("物品实例与装备状态资产 id 不一致")
    return state


__all__ = [
    "EquipmentCatalog",
    "EquipmentContributionProvider",
    "EquipmentDefinition",
    "EquipmentQualityProfile",
    "EquipmentSetBonus",
    "EquipmentSetDefinition",
    "EquipmentState",
    "EquipmentFamilyDefinition",
    "EQUIPMENT_STATE_DATA_KEY",
    "equipment_state_data",
    "equipment_state_from_data",
    "equipment_state_from_instance",
]
