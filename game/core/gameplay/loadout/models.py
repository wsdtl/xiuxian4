"""一个武器槽、六个装备槽和共享品质目录。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from ..ids import StableId, stable_id
from ..inventory import ItemComponentRegistry, ItemComponentType
from ..registry import DefinitionRegistry
from ..tags import EMPTY_TAGS, TagSet


WEAPON_SLOT_ID = "loadout_slot.weapon"
HEAD_SLOT_ID = "equipment_slot.head"
BODY_SLOT_ID = "equipment_slot.body"
HANDS_SLOT_ID = "equipment_slot.hands"
WAIST_SLOT_ID = "equipment_slot.waist"
FEET_SLOT_ID = "equipment_slot.feet"
ACCESSORY_SLOT_ID = "equipment_slot.accessory"

EQUIPMENT_SLOT_IDS = frozenset(
    {
        HEAD_SLOT_ID,
        BODY_SLOT_ID,
        HANDS_SLOT_ID,
        WAIST_SLOT_ID,
        FEET_SLOT_ID,
        ACCESSORY_SLOT_ID,
    }
)
STANDARD_LOADOUT_SLOT_IDS = frozenset({WEAPON_SLOT_ID, *EQUIPMENT_SLOT_IDS})
STANDARD_LOADOUT_SLOT_ORDER = (
    WEAPON_SLOT_ID,
    HEAD_SLOT_ID,
    BODY_SLOT_ID,
    HANDS_SLOT_ID,
    WAIST_SLOT_ID,
    FEET_SLOT_ID,
    ACCESSORY_SLOT_ID,
)
LOADOUT_ITEM_COMPONENT_ID = "item_component.loadout"


class LoadoutSlotKind(str, Enum):
    WEAPON = "weapon"
    EQUIPMENT = "equipment"


@dataclass(frozen=True)
class LoadoutSlotDefinition:
    id: StableId
    kind: LoadoutSlotKind
    required_item_tags: TagSet = EMPTY_TAGS
    blocked_item_tags: TagSet = EMPTY_TAGS

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="loadout slot id"))
        object.__setattr__(self, "kind", LoadoutSlotKind(self.kind))


class LoadoutSlotCatalog:
    """启动期登记装配槽，标准游戏必须正好拥有一武器槽和六装备槽。"""

    def __init__(self) -> None:
        self.definitions = DefinitionRegistry[LoadoutSlotDefinition]("LoadoutSlot")
        self._finalized = False

    def register(self, definition: LoadoutSlotDefinition) -> LoadoutSlotDefinition:
        if self._finalized:
            raise RuntimeError("装配槽目录已经完成组装")
        return self.definitions.register(definition)

    def require(self, slot_id: StableId) -> LoadoutSlotDefinition:
        return self.definitions.require(slot_id)

    def finalize(self) -> None:
        if self._finalized:
            return
        actual = set(self.definitions.ids())
        if actual != set(STANDARD_LOADOUT_SLOT_IDS):
            raise ValueError(
                "标准装配槽必须且只能包含一武器槽和六装备槽："
                f"missing={sorted(STANDARD_LOADOUT_SLOT_IDS - actual)}, "
                f"extra={sorted(actual - STANDARD_LOADOUT_SLOT_IDS)}"
            )
        weapon = self.require(WEAPON_SLOT_ID)
        if weapon.kind is not LoadoutSlotKind.WEAPON:
            raise ValueError("loadout_slot.weapon 必须是武器槽")
        for slot_id in EQUIPMENT_SLOT_IDS:
            if self.require(slot_id).kind is not LoadoutSlotKind.EQUIPMENT:
                raise ValueError(f"{slot_id} 必须是装备槽")
        self.definitions.freeze()
        self._finalized = True

    @property
    def finalized(self) -> bool:
        return self._finalized


def standard_loadout_slot_catalog() -> LoadoutSlotCatalog:
    catalog = LoadoutSlotCatalog()
    catalog.register(
        LoadoutSlotDefinition(
            WEAPON_SLOT_ID,
            LoadoutSlotKind.WEAPON,
            required_item_tags=TagSet.of("item.weapon"),
        )
    )
    for slot_id in sorted(EQUIPMENT_SLOT_IDS):
        catalog.register(
            LoadoutSlotDefinition(
                slot_id,
                LoadoutSlotKind.EQUIPMENT,
                required_item_tags=TagSet.of("item.equipment"),
            )
        )
    catalog.finalize()
    return catalog


@dataclass(frozen=True)
class QualityDefinition:
    """武器与装备共用的稳定品质身份；玩家可见名称由世界包提供。"""

    id: StableId
    rank: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="quality id"))
        if self.rank < 0:
            raise ValueError("QualityDefinition.rank 不能小于 0")


class QualityCatalog:
    def __init__(self) -> None:
        self.definitions = DefinitionRegistry[QualityDefinition]("Quality")
        self._finalized = False

    def register(self, definition: QualityDefinition) -> QualityDefinition:
        if self._finalized:
            raise RuntimeError("品质目录已经完成组装")
        if any(value.rank == definition.rank for value in self.definitions):
            raise ValueError(f"品质排序重复：{definition.rank}")
        return self.definitions.register(definition)

    def require(self, quality_id: StableId) -> QualityDefinition:
        return self.definitions.require(quality_id)

    def finalize(self) -> None:
        if not len(self.definitions):
            raise ValueError("品质目录不能为空")
        self.definitions.freeze()
        self._finalized = True

    @property
    def finalized(self) -> bool:
        return self._finalized


@dataclass(frozen=True)
class LoadoutItemComponent:
    """物品定义声明自己可以进入哪些装配槽。"""

    allowed_slot_ids: frozenset[StableId]

    def __post_init__(self) -> None:
        slots = frozenset(stable_id(value, field="loadout slot id") for value in self.allowed_slot_ids)
        if not slots:
            raise ValueError("LoadoutItemComponent.allowed_slot_ids 不能为空")
        object.__setattr__(self, "allowed_slot_ids", slots)


def register_loadout_item_component(registry: ItemComponentRegistry) -> None:
    registry.register(ItemComponentType(LOADOUT_ITEM_COMPONENT_ID, LoadoutItemComponent))


@dataclass(frozen=True)
class LoadoutPreset:
    """一套可原子激活的七槽资产快照。"""

    id: StableId
    slots: Mapping[StableId, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="loadout preset id"))
        object.__setattr__(self, "slots", _validated_slots(self.slots))


@dataclass(frozen=True)
class LoadoutState:
    """角色当前激活的一把武器和最多六件装备。"""

    character_id: str
    slots: Mapping[StableId, str] = field(default_factory=dict)
    revision: int = 0
    presets: Mapping[StableId, LoadoutPreset] = field(default_factory=dict)
    active_preset_id: StableId | None = None

    def __post_init__(self) -> None:
        if not self.character_id.strip():
            raise ValueError("LoadoutState 缺少 character_id")
        slots = _validated_slots(self.slots)
        if self.revision < 0:
            raise ValueError("LoadoutState.revision 不能小于 0")
        presets: dict[StableId, LoadoutPreset] = {}
        for key, preset in self.presets.items():
            preset_id = stable_id(key, field="loadout preset id")
            if preset_id != preset.id:
                raise ValueError("配装映射键与预设 id 不一致")
            presets[preset_id] = preset
        active = self.active_preset_id
        if active is not None:
            active = stable_id(active, field="loadout preset id")
            if active not in presets:
                raise ValueError("当前激活配装不存在")
            if dict(presets[active].slots) != dict(slots):
                raise ValueError("当前槽位与激活配装不一致")
        object.__setattr__(self, "slots", MappingProxyType(slots))
        object.__setattr__(self, "presets", MappingProxyType(presets))
        object.__setattr__(self, "active_preset_id", active)

    @property
    def weapon_asset_id(self) -> str | None:
        return self.slots.get(WEAPON_SLOT_ID)

    @property
    def equipment_asset_ids(self) -> tuple[str, ...]:
        return tuple(
            self.slots[slot_id]
            for slot_id in sorted(EQUIPMENT_SLOT_IDS)
            if slot_id in self.slots
        )


def _validated_slots(values: Mapping[StableId, str]) -> Mapping[StableId, str]:
    slots: dict[StableId, str] = {}
    for key, asset_id in values.items():
        slot_id = stable_id(key, field="loadout slot id")
        if slot_id not in STANDARD_LOADOUT_SLOT_IDS:
            raise ValueError(f"未知标准装配槽：{slot_id}")
        if not str(asset_id).strip():
            raise ValueError(f"装配槽 {slot_id} 缺少资产 id")
        slots[slot_id] = str(asset_id)
    if len(set(slots.values())) != len(slots):
        raise ValueError("同一个物品资产不能同时占用多个装配槽")
    return MappingProxyType(slots)


__all__ = [
    "ACCESSORY_SLOT_ID",
    "BODY_SLOT_ID",
    "EQUIPMENT_SLOT_IDS",
    "FEET_SLOT_ID",
    "HANDS_SLOT_ID",
    "HEAD_SLOT_ID",
    "LOADOUT_ITEM_COMPONENT_ID",
    "LoadoutItemComponent",
    "LoadoutPreset",
    "LoadoutSlotCatalog",
    "LoadoutSlotDefinition",
    "LoadoutSlotKind",
    "LoadoutState",
    "QualityCatalog",
    "QualityDefinition",
    "STANDARD_LOADOUT_SLOT_IDS",
    "STANDARD_LOADOUT_SLOT_ORDER",
    "WAIST_SLOT_ID",
    "WEAPON_SLOT_ID",
    "register_loadout_item_component",
    "standard_loadout_slot_catalog",
]
