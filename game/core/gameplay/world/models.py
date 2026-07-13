"""世界空间、位置、存在体、占用和类型化共享计量状态。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from ..events import RuleEvent
from ..ids import StableId, stable_id
from ..registry import DefinitionRegistry
from ..tags import EMPTY_TAGS, TagSet


class WorldTopologyKind(str, Enum):
    GRID = "grid"
    GRAPH = "graph"


class WorldScopeKind(str, Enum):
    GLOBAL = "global"
    SPACE = "space"
    LOCATION = "location"


class MeterOverflowPolicy(str, Enum):
    REJECT = "reject"
    CLAMP = "clamp"


@dataclass(frozen=True)
class WorldSpaceDefinition:
    id: StableId
    topology: WorldTopologyKind
    minimum_x: int | None = None
    maximum_x: int | None = None
    minimum_y: int | None = None
    maximum_y: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="world space id"))
        topology = WorldTopologyKind(self.topology)
        bounds = (self.minimum_x, self.maximum_x, self.minimum_y, self.maximum_y)
        if topology is WorldTopologyKind.GRID:
            if any(value is None for value in bounds):
                raise ValueError("网格世界必须提供完整整数边界")
            if self.minimum_x > self.maximum_x or self.minimum_y > self.maximum_y:  # type: ignore[operator]
                raise ValueError("网格世界边界无效")
        elif any(value is not None for value in bounds):
            raise ValueError("节点世界不能声明网格边界")
        object.__setattr__(self, "topology", topology)


@dataclass(frozen=True)
class WorldLocationDefinition:
    id: StableId
    space_id: StableId
    x: int | None = None
    y: int | None = None
    capacity: int | None = None
    tags: TagSet = EMPTY_TAGS

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="world location id"))
        object.__setattr__(self, "space_id", stable_id(self.space_id, field="world space id"))
        if (self.x is None) != (self.y is None):
            raise ValueError("地点坐标必须同时提供 x 和 y")
        if self.capacity is not None and self.capacity < 1:
            raise ValueError("地点容量必须大于 0")


@dataclass(frozen=True)
class WorldConnectionDefinition:
    id: StableId
    space_id: StableId
    origin_id: StableId
    destination_id: StableId
    cost: int = 1
    bidirectional: bool = True
    tags: TagSet = EMPTY_TAGS

    def __post_init__(self) -> None:
        for field_name in ("id", "space_id", "origin_id", "destination_id"):
            object.__setattr__(
                self,
                field_name,
                stable_id(getattr(self, field_name), field=field_name),
            )
        if self.origin_id == self.destination_id or self.cost < 1:
            raise ValueError("世界连接端点或移动成本无效")


@dataclass(frozen=True)
class WorldMeterDefinition:
    id: StableId
    allowed_scopes: frozenset[WorldScopeKind]
    minimum: int = 0
    maximum: int = 2**63 - 1
    initial: int = 0
    thresholds: tuple[int, ...] = ()
    overflow: MeterOverflowPolicy = MeterOverflowPolicy.REJECT

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="world meter id"))
        scopes = frozenset(WorldScopeKind(value) for value in self.allowed_scopes)
        thresholds = tuple(sorted(set(int(value) for value in self.thresholds)))
        if not scopes or not self.minimum <= self.initial <= self.maximum:
            raise ValueError("世界计量定义范围无效")
        if any(not self.minimum <= value <= self.maximum for value in thresholds):
            raise ValueError("世界计量阈值超出范围")
        object.__setattr__(self, "allowed_scopes", scopes)
        object.__setattr__(self, "thresholds", thresholds)
        object.__setattr__(self, "overflow", MeterOverflowPolicy(self.overflow))


@dataclass(frozen=True, order=True)
class WorldPosition:
    space_id: StableId
    location_id: StableId | None = None
    x: int | None = None
    y: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "space_id", stable_id(self.space_id, field="world space id"))
        if self.location_id is not None:
            object.__setattr__(
                self,
                "location_id",
                stable_id(self.location_id, field="world location id"),
            )
        has_coordinates = self.x is not None or self.y is not None
        if has_coordinates and (self.x is None or self.y is None):
            raise ValueError("世界坐标必须同时提供 x 和 y")
        if (self.location_id is None) == (not has_coordinates):
            raise ValueError("世界位置必须且只能使用地点或坐标")

    @property
    def key(self) -> str:
        if self.location_id is not None:
            return f"{self.space_id}:location:{self.location_id}"
        return f"{self.space_id}:coordinate:{self.x}:{self.y}"


@dataclass(frozen=True, order=True)
class WorldScopeRef:
    kind: WorldScopeKind
    id: str

    def __post_init__(self) -> None:
        kind = WorldScopeKind(self.kind)
        value = str(self.id or "").strip()
        if kind is WorldScopeKind.GLOBAL:
            if value != "global":
                raise ValueError("全局世界作用域 ID 必须是 global")
        elif not value:
            raise ValueError("世界作用域缺少 ID")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "id", value)

    @property
    def key(self) -> str:
        return f"{self.kind.value}:{self.id}"


@dataclass(frozen=True)
class WorldPresence:
    id: str
    owner_id: str
    kind_id: StableId
    position: WorldPosition
    revision: int = 0

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.owner_id.strip() or self.revision < 0:
            raise ValueError("世界存在体身份或 revision 无效")
        object.__setattr__(self, "kind_id", stable_id(self.kind_id, field="presence kind id"))


@dataclass(frozen=True)
class WorldReservation:
    id: str
    owner_id: str
    position: WorldPosition
    units: int
    exclusive: bool
    created_at: datetime
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.owner_id.strip() or self.units < 1:
            raise ValueError("世界占用预约身份或数量无效")
        _aware(self.created_at, "WorldReservation.created_at")
        if self.expires_at is not None:
            _aware(self.expires_at, "WorldReservation.expires_at")
            if self.expires_at <= self.created_at:
                raise ValueError("世界占用预约期限必须晚于创建时间")


@dataclass(frozen=True)
class WorldState:
    world_id: str
    presences: Mapping[str, WorldPresence] = field(default_factory=dict)
    reservations: Mapping[str, WorldReservation] = field(default_factory=dict)
    meters: Mapping[str, int] = field(default_factory=dict)
    revision: int = 0

    def __post_init__(self) -> None:
        if not self.world_id.strip() or self.revision < 0:
            raise ValueError("WorldState 身份或 revision 无效")
        presences = dict(self.presences)
        reservations = dict(self.reservations)
        meters = {str(key): int(value) for key, value in self.meters.items()}
        if any(key != value.id for key, value in presences.items()):
            raise ValueError("存在体映射键与 ID 不一致")
        if any(key != value.id for key, value in reservations.items()):
            raise ValueError("预约映射键与 ID 不一致")
        object.__setattr__(self, "presences", MappingProxyType(presences))
        object.__setattr__(self, "reservations", MappingProxyType(reservations))
        object.__setattr__(self, "meters", MappingProxyType(meters))


@dataclass(frozen=True)
class WorldTransaction:
    id: str
    actor_id: str
    expected_revision: int
    operations: tuple[object, ...]

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.actor_id.strip() or self.expected_revision < 0:
            raise ValueError("WorldTransaction 身份或 revision 无效")
        if not self.operations:
            raise ValueError("WorldTransaction.operations 不能为空")


@dataclass(frozen=True)
class AddPresence:
    presence: WorldPresence


@dataclass(frozen=True)
class MovePresence:
    presence_id: str
    destination: WorldPosition
    maximum_cost: int | None = None


@dataclass(frozen=True)
class RemovePresence:
    presence_id: str


@dataclass(frozen=True)
class ReserveWorldPosition:
    reservation: WorldReservation


@dataclass(frozen=True)
class ReleaseWorldReservation:
    reservation_id: str


@dataclass(frozen=True)
class AdjustWorldMeter:
    scope: WorldScopeRef
    meter_id: StableId
    amount: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "meter_id", stable_id(self.meter_id, field="world meter id"))
        if not self.amount:
            raise ValueError("世界计量变化不能为 0")


@dataclass(frozen=True)
class WorldExecution:
    transaction_id: str
    state: WorldState
    events: tuple[RuleEvent, ...]


class WorldCatalog:
    def __init__(self) -> None:
        self.spaces = DefinitionRegistry[WorldSpaceDefinition]("WorldSpace")
        self.locations = DefinitionRegistry[WorldLocationDefinition]("WorldLocation")
        self.connections = DefinitionRegistry[WorldConnectionDefinition]("WorldConnection")
        self.meters = DefinitionRegistry[WorldMeterDefinition]("WorldMeter")
        self._finalized = False

    def finalize(self) -> None:
        if self._finalized:
            return
        for location in self.locations:
            space = self.spaces.require(location.space_id)
            if space.topology is WorldTopologyKind.GRID:
                if location.x is None:
                    raise ValueError(f"网格地点缺少坐标：{location.id}")
                _validate_grid_position(space, location.x, location.y)
            elif location.x is not None:
                raise ValueError(f"节点世界地点不能携带坐标：{location.id}")
        occupied = set()
        for location in self.locations:
            if location.x is None:
                continue
            key = (location.space_id, location.x, location.y)
            if key in occupied:
                raise ValueError("同一世界空间不能登记重复地点坐标")
            occupied.add(key)
        for connection in self.connections:
            origin = self.locations.require(connection.origin_id)
            destination = self.locations.require(connection.destination_id)
            if origin.space_id != connection.space_id or destination.space_id != connection.space_id:
                raise ValueError("世界连接端点不属于声明空间")
        for registry in (self.spaces, self.locations, self.connections, self.meters):
            registry.freeze()
        self._finalized = True

    @property
    def finalized(self) -> bool:
        return self._finalized


def meter_key(scope: WorldScopeRef, meter_id: StableId) -> str:
    return f"{scope.key}:{stable_id(meter_id, field='world meter id')}"


def _validate_grid_position(space: WorldSpaceDefinition, x: int, y: int) -> None:
    if not (space.minimum_x <= x <= space.maximum_x and space.minimum_y <= y <= space.maximum_y):  # type: ignore[operator]
        raise ValueError("世界坐标超出空间边界")


def _aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} 必须包含时区")


__all__ = [
    "AddPresence",
    "AdjustWorldMeter",
    "MeterOverflowPolicy",
    "MovePresence",
    "ReleaseWorldReservation",
    "RemovePresence",
    "ReserveWorldPosition",
    "WorldCatalog",
    "WorldConnectionDefinition",
    "WorldExecution",
    "WorldLocationDefinition",
    "WorldMeterDefinition",
    "WorldPosition",
    "WorldPresence",
    "WorldReservation",
    "WorldScopeKind",
    "WorldScopeRef",
    "WorldSpaceDefinition",
    "WorldState",
    "WorldTopologyKind",
    "WorldTransaction",
    "meter_key",
]
