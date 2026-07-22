"""物品资产、容器、预约与库存快照。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from ..ids import StableId, stable_id
from ..tags import EMPTY_TAGS, TagSet


class ItemAssetKind(str, Enum):
    """物品在资产账中的保存形态。"""

    STACK = "stack"
    INSTANCE = "instance"


class ReservationMode(str, Enum):
    """业务占用资产的强度。"""

    RESERVED = "reserved"
    LOCKED = "locked"
    ESCROWED = "escrowed"


class AssetAvailability(str, Enum):
    """供业务查询使用的资产当前占用状态。"""

    AVAILABLE = "available"
    RESERVED = "reserved"
    LOCKED = "locked"
    ESCROWED = "escrowed"


@dataclass(frozen=True)
class SourceReceipt:
    """物品进入系统时的来源凭据。"""

    id: str
    source_kind: StableId
    source_id: str
    logical_time: datetime
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("SourceReceipt 缺少 id")
        object.__setattr__(self, "source_kind", stable_id(self.source_kind, field="source kind"))
        if not self.source_id.strip():
            raise ValueError("SourceReceipt 缺少 source_id")
        if self.logical_time.tzinfo is None or self.logical_time.utcoffset() is None:
            raise ValueError("SourceReceipt.logical_time 必须包含时区")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class ProvenanceLot:
    """可堆叠物资中的一个来源批次。"""

    receipt: SourceReceipt
    quantity: int

    def __post_init__(self) -> None:
        if self.quantity < 1:
            raise ValueError("ProvenanceLot.quantity 必须大于 0")


@dataclass(frozen=True)
class ItemStack:
    """可拆分、可合并的同类物资资产。"""

    id: str
    definition_id: StableId
    container_id: str
    lots: tuple[ProvenanceLot, ...]
    revision: int = 0

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("ItemStack 缺少 id")
        object.__setattr__(self, "definition_id", stable_id(self.definition_id, field="item id"))
        if not self.container_id.strip():
            raise ValueError("ItemStack 缺少 container_id")
        if not self.lots:
            raise ValueError("ItemStack 至少需要一个来源批次")
        if self.revision < 0:
            raise ValueError("ItemStack.revision 不能小于 0")

    @property
    def quantity(self) -> int:
        return sum(lot.quantity for lot in self.lots)


@dataclass(frozen=True)
class ItemInstance:
    """拥有独立身份和可扩展实例数据的物品。"""

    id: str
    definition_id: StableId
    container_id: str
    receipt: SourceReceipt
    data: Mapping[str, object] = field(default_factory=dict)
    revision: int = 0

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("ItemInstance 缺少 id")
        object.__setattr__(self, "definition_id", stable_id(self.definition_id, field="item id"))
        if not self.container_id.strip():
            raise ValueError("ItemInstance 缺少 container_id")
        if self.revision < 0:
            raise ValueError("ItemInstance.revision 不能小于 0")
        object.__setattr__(self, "data", MappingProxyType(dict(self.data)))


@dataclass(frozen=True)
class ItemContainer:
    """资产唯一的位置和所有权边界。"""

    id: str
    kind: StableId
    owner_id: str
    accepted_kinds: frozenset[ItemAssetKind] = frozenset(ItemAssetKind)
    required_item_tags: TagSet = EMPTY_TAGS
    blocked_item_tags: TagSet = EMPTY_TAGS
    maximum_assets: int | None = None
    maximum_space: int | None = None

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("ItemContainer 缺少 id")
        object.__setattr__(self, "kind", stable_id(self.kind, field="container kind"))
        if not self.owner_id.strip():
            raise ValueError("ItemContainer 缺少 owner_id")
        kinds = frozenset(ItemAssetKind(value) for value in self.accepted_kinds)
        if not kinds:
            raise ValueError("ItemContainer.accepted_kinds 不能为空")
        object.__setattr__(self, "accepted_kinds", kinds)
        if self.maximum_assets is not None and self.maximum_assets < 1:
            raise ValueError("ItemContainer.maximum_assets 必须大于 0")
        if self.maximum_space is not None and self.maximum_space < 1:
            raise ValueError("ItemContainer.maximum_space 必须大于 0")


@dataclass(frozen=True)
class AssetReservation:
    """一个业务流程对资产的显式占用。"""

    id: str
    asset_id: str
    mode: ReservationMode
    business_kind: StableId
    business_id: str
    quantity: int
    created_at: datetime
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("AssetReservation 缺少 id")
        if not self.asset_id.strip():
            raise ValueError("AssetReservation 缺少 asset_id")
        object.__setattr__(self, "mode", ReservationMode(self.mode))
        object.__setattr__(
            self,
            "business_kind",
            stable_id(self.business_kind, field="reservation business kind"),
        )
        if not self.business_id.strip():
            raise ValueError("AssetReservation 缺少 business_id")
        if self.quantity < 1:
            raise ValueError("AssetReservation.quantity 必须大于 0")
        for field_name, value in (("created_at", self.created_at), ("expires_at", self.expires_at)):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError(f"AssetReservation.{field_name} 必须包含时区")
        if self.expires_at is not None and self.expires_at <= self.created_at:
            raise ValueError("AssetReservation.expires_at 必须晚于 created_at")

    def expired_at(self, logical_time: datetime) -> bool:
        return self.expires_at is not None and self.expires_at <= logical_time


@dataclass(frozen=True)
class InventoryState:
    """一次事务前后可直接替换的完整库存快照。"""

    containers: Mapping[str, ItemContainer] = field(default_factory=dict)
    stacks: Mapping[str, ItemStack] = field(default_factory=dict)
    instances: Mapping[str, ItemInstance] = field(default_factory=dict)
    reservations: Mapping[str, AssetReservation] = field(default_factory=dict)
    revision: int = 0
    asset_references: Mapping[str, int] = field(default_factory=dict)
    next_reference_number: int = 1
    protected_asset_ids: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        containers = dict(self.containers)
        stacks = dict(self.stacks)
        instances = dict(self.instances)
        reservations = dict(self.reservations)
        asset_references = dict(self.asset_references)
        protected_asset_ids = frozenset(self.protected_asset_ids)
        if self.revision < 0:
            raise ValueError("InventoryState.revision 不能小于 0")
        if isinstance(self.next_reference_number, bool) or not isinstance(
            self.next_reference_number,
            int,
        ):
            raise TypeError("InventoryState.next_reference_number 必须是整数")
        if self.next_reference_number < 1:
            raise ValueError("InventoryState.next_reference_number 必须大于 0")
        for key, value in containers.items():
            if key != value.id:
                raise ValueError(f"容器映射键与 id 不一致：{key}")
        for key, value in (*stacks.items(), *instances.items()):
            if key != value.id:
                raise ValueError(f"资产映射键与 id 不一致：{key}")
            if value.container_id not in containers:
                raise ValueError(f"资产 {value.id} 引用了未知容器：{value.container_id}")
        duplicated = set(stacks) & set(instances)
        if duplicated:
            raise ValueError(f"资产 id 在堆叠物与实例物中重复：{sorted(duplicated)[0]}")
        asset_ids = set(stacks) | set(instances)
        unknown_protected = protected_asset_ids - set(instances)
        if unknown_protected:
            raise ValueError(
                f"珍藏状态引用了未知的独立实例：{sorted(unknown_protected)[0]}"
            )
        if not asset_references and asset_ids:
            asset_references = {
                asset_id: number
                for number, asset_id in enumerate(sorted(asset_ids), start=1)
            }
        if set(asset_references) != asset_ids:
            raise ValueError("物品编号映射必须完整覆盖当前全部资产")
        reference_numbers = tuple(asset_references.values())
        if any(
            isinstance(number, bool) or not isinstance(number, int) or number < 1
            for number in reference_numbers
        ):
            raise ValueError("物品编号必须是大于 0 的整数")
        if len(set(reference_numbers)) != len(reference_numbers):
            raise ValueError("同一库存中的物品编号不能重复")
        required_next = max(reference_numbers, default=0) + 1
        next_reference_number = max(self.next_reference_number, required_next)
        reserved_totals: dict[str, int] = {}
        for key, value in reservations.items():
            if key != value.id:
                raise ValueError(f"预约映射键与 id 不一致：{key}")
            if value.asset_id not in stacks and value.asset_id not in instances:
                raise ValueError(f"预约 {value.id} 引用了未知资产：{value.asset_id}")
            reserved_totals[value.asset_id] = reserved_totals.get(value.asset_id, 0) + value.quantity
        for asset_id, total in reserved_totals.items():
            maximum = stacks[asset_id].quantity if asset_id in stacks else 1
            if total > maximum:
                raise ValueError(f"资产 {asset_id} 的预约数量超过实际数量")
        asset_counts: dict[str, int] = {}
        for asset in (*stacks.values(), *instances.values()):
            asset_counts[asset.container_id] = asset_counts.get(asset.container_id, 0) + 1
        for container_id, count in asset_counts.items():
            maximum = containers[container_id].maximum_assets
            if maximum is not None and count > maximum:
                raise ValueError(f"容器 {container_id} 的资产数量超过容量")
        object.__setattr__(self, "containers", MappingProxyType(containers))
        object.__setattr__(self, "stacks", MappingProxyType(stacks))
        object.__setattr__(self, "instances", MappingProxyType(instances))
        object.__setattr__(self, "reservations", MappingProxyType(reservations))
        object.__setattr__(self, "asset_references", MappingProxyType(asset_references))
        object.__setattr__(self, "next_reference_number", next_reference_number)
        object.__setattr__(self, "protected_asset_ids", protected_asset_ids)

    def asset(self, asset_id: str) -> ItemStack | ItemInstance:
        if asset_id in self.stacks:
            return self.stacks[asset_id]
        try:
            return self.instances[asset_id]
        except KeyError as exc:
            raise KeyError(f"未知物品资产：{asset_id}") from exc

    def owner_of(self, asset_id: str) -> str:
        return self.containers[self.asset(asset_id).container_id].owner_id

    def reference_number(self, asset_id: str) -> int:
        """返回账号库存内稳定、永久不复用的物品编号。"""

        try:
            return self.asset_references[asset_id]
        except KeyError as exc:
            raise KeyError(f"未知物品资产：{asset_id}") from exc

    def asset_id_for_reference(self, reference_number: int) -> str:
        """由玩家编号反查当前仍存在的资产。"""

        for asset_id, number in self.asset_references.items():
            if number == reference_number:
                return asset_id
        raise KeyError(f"未知物品编号：{reference_number}")

    def reservations_for(self, asset_id: str) -> tuple[AssetReservation, ...]:
        return tuple(
            sorted(
                (value for value in self.reservations.values() if value.asset_id == asset_id),
                key=lambda value: value.id,
            )
        )

    def is_protected(self, asset_id: str) -> bool:
        """返回独立物品是否处于玩家珍藏保护中。"""

        return asset_id in self.protected_asset_ids

    def reserved_quantity(self, asset_id: str) -> int:
        return sum(value.quantity for value in self.reservations_for(asset_id))

    def available_quantity(self, asset_id: str) -> int:
        asset = self.asset(asset_id)
        quantity = asset.quantity if isinstance(asset, ItemStack) else 1
        return quantity - self.reserved_quantity(asset_id)

    def availability(
        self,
        asset_id: str,
        *,
        logical_time: datetime | None = None,
    ) -> AssetAvailability:
        """返回未过期预约中的最高占用强度。"""

        reservations = self.reservations_for(asset_id)
        if logical_time is not None:
            reservations = tuple(
                value for value in reservations if not value.expired_at(logical_time)
            )
        if not reservations:
            return AssetAvailability.AVAILABLE
        modes = {value.mode for value in reservations}
        if ReservationMode.ESCROWED in modes:
            return AssetAvailability.ESCROWED
        if ReservationMode.LOCKED in modes:
            return AssetAvailability.LOCKED
        return AssetAvailability.RESERVED


__all__ = [
    "AssetAvailability",
    "AssetReservation",
    "InventoryState",
    "ItemAssetKind",
    "ItemContainer",
    "ItemInstance",
    "ItemStack",
    "ProvenanceLot",
    "ReservationMode",
    "SourceReceipt",
]
