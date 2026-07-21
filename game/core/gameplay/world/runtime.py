"""真实玩法世界、独立坐标锚点与世界地点绑定目录。"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable, Mapping

from ..ids import StableId, stable_id
from .models import WorldCatalog, WorldPosition


@dataclass(frozen=True)
class MapAnchorDefinition:
    """一个世界地图中的物理坐标锚点，本身不声明玩法或展示。"""

    id: StableId
    x: int
    y: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="map anchor id"))
        object.__setattr__(self, "x", int(self.x))
        object.__setattr__(self, "y", int(self.y))


@dataclass(frozen=True)
class WorldDefinition:
    """一个可进入的真实玩法世界；皮肤只由这里派生用于展示。"""

    id: StableId
    space_id: StableId
    skin_id: StableId
    spawn_anchor_id: StableId

    def __post_init__(self) -> None:
        for field_name, label in (
            ("id", "world id"),
            ("space_id", "world space id"),
            ("skin_id", "skin id"),
            ("spawn_anchor_id", "spawn anchor id"),
        ):
            object.__setattr__(
                self,
                field_name,
                stable_id(getattr(self, field_name), field=label),
            )


@dataclass(frozen=True)
class WorldLocationBinding:
    """声明某个世界在某个坐标提供的唯一主功能。"""

    world_id: StableId
    anchor_id: StableId
    function_id: StableId
    content_ref: StableId | None = None
    version: int = 1
    display_ref: StableId | None = None

    def __post_init__(self) -> None:
        for field_name, label in (
            ("world_id", "world id"),
            ("anchor_id", "map anchor id"),
            ("function_id", "location function id"),
        ):
            object.__setattr__(
                self,
                field_name,
                stable_id(getattr(self, field_name), field=label),
            )
        if self.content_ref is not None:
            object.__setattr__(
                self,
                "content_ref",
                stable_id(self.content_ref, field="location content ref"),
            )
        if self.display_ref is not None:
            object.__setattr__(
                self,
                "display_ref",
                stable_id(self.display_ref, field="location display ref"),
            )
        if self.version < 1:
            raise ValueError("世界地点绑定版本必须大于 0")

    @property
    def key(self) -> tuple[StableId, StableId]:
        return self.world_id, self.anchor_id

    @property
    def id(self) -> StableId:
        world_token = self.world_id.removeprefix("world.")
        anchor_token = self.anchor_id.removeprefix("location.")
        return stable_id(
            f"world_location_binding.{world_token}.{anchor_token}",
            field="world location binding id",
        )


@dataclass(frozen=True)
class ResolvedWorldLocation:
    """世界、锚点、功能与内容引用的一次性解析结果。"""

    world: WorldDefinition
    anchor: MapAnchorDefinition
    binding: WorldLocationBinding
    position: WorldPosition

    @property
    def display_id(self) -> StableId:
        """返回世界皮肤使用的地点身份；旧绑定回退物理锚点 ID。"""

        return self.binding.display_ref or self.anchor.id

    def require_content_ref(self) -> StableId:
        if self.binding.content_ref is None:
            raise KeyError(
                f"世界地点没有绑定玩法内容：{self.world.id}/{self.anchor.id}"
            )
        return self.binding.content_ref


class WorldRuntimeCatalog:
    """所有业务查询真实世界与地点功能的唯一入口。"""

    def __init__(
        self,
        worlds: Iterable[WorldDefinition],
        anchors: Iterable[MapAnchorDefinition],
        bindings: Iterable[WorldLocationBinding],
        *,
        world_catalog: WorldCatalog,
    ) -> None:
        world_values = tuple(worlds)
        anchor_values = tuple(anchors)
        binding_values = tuple(bindings)
        self._worlds = _unique(world_values, lambda value: value.id, "真实世界")
        self._anchors = _unique(anchor_values, lambda value: value.id, "地图锚点")
        self._bindings = _unique(binding_values, lambda value: value.key, "世界地点绑定")
        self._by_skin = _unique(world_values, lambda value: value.skin_id, "世界皮肤归属")
        _unique(world_values, lambda value: value.space_id, "真实世界空间归属")

        for world in world_values:
            world_catalog.spaces.require(world.space_id)
            if world.spawn_anchor_id not in self._anchors:
                raise KeyError(f"世界出生点引用未知锚点：{world.id}/{world.spawn_anchor_id}")
            if (world.id, world.spawn_anchor_id) not in self._bindings:
                raise KeyError(f"世界出生点没有地点绑定：{world.id}/{world.spawn_anchor_id}")

        positions: dict[tuple[StableId, int, int], StableId] = {}
        for binding in binding_values:
            world = self.require_world(binding.world_id)
            anchor = self.require_anchor(binding.anchor_id)
            position_key = (world.space_id, anchor.x, anchor.y)
            previous = positions.get(position_key)
            if previous is not None and previous != anchor.id:
                raise ValueError(
                    f"同一世界坐标不能绑定多个锚点：{world.id}/{previous}/{anchor.id}"
                )
            positions[position_key] = anchor.id
        self._position_anchors: Mapping[tuple[StableId, int, int], StableId] = (
            MappingProxyType(positions)
        )

        display_bindings: dict[tuple[StableId, StableId], WorldLocationBinding] = {}
        for binding in binding_values:
            if binding.display_ref is None:
                continue
            key = (binding.world_id, binding.display_ref)
            if key in display_bindings:
                raise ValueError(
                    f"同一世界展示地点不能绑定多个锚点：{binding.world_id}/{binding.display_ref}"
                )
            display_bindings[key] = binding
        self._display_bindings = MappingProxyType(display_bindings)

    def require_world(self, world_id: StableId) -> WorldDefinition:
        key = stable_id(world_id, field="world id")
        try:
            return self._worlds[key]
        except KeyError as exc:
            raise KeyError(f"未知真实世界：{key}") from exc

    def world_for_skin(self, skin_id: StableId) -> WorldDefinition:
        key = stable_id(skin_id, field="skin id")
        try:
            return self._by_skin[key]
        except KeyError as exc:
            raise KeyError(f"世界皮肤没有对应真实世界：{key}") from exc

    def require_anchor(self, anchor_id: StableId) -> MapAnchorDefinition:
        key = stable_id(anchor_id, field="map anchor id")
        try:
            return self._anchors[key]
        except KeyError as exc:
            raise KeyError(f"未知地图锚点：{key}") from exc

    def binding(
        self,
        world_id: StableId,
        anchor_id: StableId,
    ) -> WorldLocationBinding | None:
        key = (
            stable_id(world_id, field="world id"),
            stable_id(anchor_id, field="map anchor id"),
        )
        return self._bindings.get(key)

    def require_binding(
        self,
        world_id: StableId,
        anchor_id: StableId,
    ) -> WorldLocationBinding:
        value = self.binding(world_id, anchor_id)
        if value is None:
            raise KeyError(f"当前世界没有这个地点：{world_id}/{anchor_id}")
        return value

    def binding_for_display(
        self,
        world_id: StableId,
        display_id: StableId,
    ) -> WorldLocationBinding | None:
        return self._display_bindings.get(
            (
                stable_id(world_id, field="world id"),
                stable_id(display_id, field="location display id"),
            )
        )

    def require_binding_for_display(
        self,
        world_id: StableId,
        display_id: StableId,
    ) -> WorldLocationBinding:
        value = self.binding_for_display(world_id, display_id)
        if value is None:
            raise KeyError(f"当前世界没有这个展示地点：{world_id}/{display_id}")
        return value

    def resolve(
        self,
        world_id: StableId,
        anchor_id: StableId,
        *,
        function_id: StableId | None = None,
    ) -> ResolvedWorldLocation:
        world = self.require_world(world_id)
        binding = self.require_binding(world.id, anchor_id)
        if function_id is not None:
            expected = stable_id(function_id, field="location function id")
            if binding.function_id != expected:
                raise KeyError(
                    f"世界地点功能不匹配：{world.id}/{binding.anchor_id}/"
                    f"{binding.function_id} != {expected}"
                )
        anchor = self.require_anchor(binding.anchor_id)
        return ResolvedWorldLocation(
            world,
            anchor,
            binding,
            WorldPosition(world.space_id, x=anchor.x, y=anchor.y),
        )

    def bindings_for_world(
        self,
        world_id: StableId,
        *,
        function_id: StableId | None = None,
    ) -> tuple[WorldLocationBinding, ...]:
        world_key = stable_id(world_id, field="world id")
        function_key = (
            stable_id(function_id, field="location function id")
            if function_id is not None
            else None
        )
        return tuple(
            sorted(
                (
                    value
                    for value in self._bindings.values()
                    if value.world_id == world_key
                    and (function_key is None or value.function_id == function_key)
                ),
                key=lambda value: value.anchor_id,
            )
        )

    def position(self, world_id: StableId, anchor_id: StableId) -> WorldPosition:
        return self.resolve(world_id, anchor_id).position

    def spawn_position(self, world_id: StableId) -> WorldPosition:
        world = self.require_world(world_id)
        return self.position(world.id, world.spawn_anchor_id)

    def anchor_at(self, world_id: StableId, position: WorldPosition) -> StableId | None:
        world = self.require_world(world_id)
        if position.space_id != world.space_id:
            return None
        if position.location_id is not None:
            return None
        return self._position_anchors.get((world.space_id, position.x, position.y))

    def resolve_position(
        self,
        world_id: StableId,
        position: WorldPosition,
        *,
        function_id: StableId | None = None,
    ) -> ResolvedWorldLocation | None:
        anchor_id = self.anchor_at(world_id, position)
        if anchor_id is None:
            return None
        try:
            return self.resolve(world_id, anchor_id, function_id=function_id)
        except KeyError:
            return None

    def world_ids(self) -> tuple[StableId, ...]:
        return tuple(self._worlds)

    def skin_ids(self) -> tuple[StableId, ...]:
        return tuple(value.skin_id for value in self._worlds.values())


def _unique(values, key_factory, label: str):
    result = {}
    for value in values:
        key = key_factory(value)
        if key in result:
            raise ValueError(f"{label}不能重复：{key}")
        result[key] = value
    if not result:
        raise ValueError(f"{label}不能为空")
    return MappingProxyType(result)


__all__ = [
    "MapAnchorDefinition",
    "ResolvedWorldLocation",
    "WorldDefinition",
    "WorldLocationBinding",
    "WorldRuntimeCatalog",
]
