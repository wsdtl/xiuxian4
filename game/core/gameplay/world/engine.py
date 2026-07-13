"""世界位置验证、移动、占用预约和共享计量事务。"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from heapq import heappop, heappush

from ..context import RuleContext
from ..errors import RuleOutcome, RuleViolation
from ..events import RuleEvent
from .models import (
    AddPresence,
    AdjustWorldMeter,
    MeterOverflowPolicy,
    MovePresence,
    ReleaseWorldReservation,
    RemovePresence,
    ReserveWorldPosition,
    WorldCatalog,
    WorldExecution,
    WorldPosition,
    WorldPresence,
    WorldReservation,
    WorldScopeKind,
    WorldScopeRef,
    WorldState,
    WorldTopologyKind,
    WorldTransaction,
    _validate_grid_position,
    meter_key,
)


class WorldEngine:
    def __init__(self, catalog: WorldCatalog) -> None:
        if not catalog.finalized:
            catalog.finalize()
        self.catalog = catalog

    def execute(
        self,
        transaction: WorldTransaction,
        *,
        state: WorldState,
        context: RuleContext,
    ) -> RuleOutcome[WorldExecution]:
        checkpoint = context.random.checkpoint()
        try:
            if state.revision != transaction.expected_revision:
                self._fail(
                    "world.revision_conflict",
                    "世界状态版本与事务预期不一致",
                    {"expected": transaction.expected_revision, "actual": state.revision},
                )
            presences = dict(state.presences)
            reservations = {
                key: value
                for key, value in state.reservations.items()
                if value.expires_at is None or value.expires_at > context.logical_time
            }
            meters = dict(state.meters)
            events: list[RuleEvent] = []
            for operation in transaction.operations:
                if isinstance(operation, AddPresence):
                    self._add_presence(operation, transaction, presences, context, events)
                elif isinstance(operation, MovePresence):
                    self._move_presence(operation, transaction, presences, context, events)
                elif isinstance(operation, RemovePresence):
                    self._remove_presence(operation, transaction, presences, context, events)
                elif isinstance(operation, ReserveWorldPosition):
                    self._reserve(operation, transaction, reservations, context, events)
                elif isinstance(operation, ReleaseWorldReservation):
                    self._release(operation, transaction, reservations, context, events)
                elif isinstance(operation, AdjustWorldMeter):
                    self._adjust_meter(operation, transaction, meters, context, events)
                else:
                    raise TypeError(f"未知世界操作：{type(operation).__name__}")
            next_state = WorldState(
                state.world_id,
                presences,
                reservations,
                meters,
                state.revision + 1,
            )
            return RuleOutcome.success(WorldExecution(transaction.id, next_state, tuple(events)))
        except RuleViolation as exc:
            context.random.restore(checkpoint)
            return RuleOutcome.failed(exc.failure)

    def movement_cost(self, origin: WorldPosition, destination: WorldPosition) -> int:
        self._validate_position(origin)
        self._validate_position(destination)
        if origin.space_id != destination.space_id:
            self._fail("world.cross_space_move", "不能直接跨世界空间移动")
        space = self.catalog.spaces.require(origin.space_id)
        if space.topology is WorldTopologyKind.GRID:
            ox, oy = self._coordinates(origin)
            dx, dy = self._coordinates(destination)
            return abs(ox - dx) + abs(oy - dy)
        if origin.location_id is None or destination.location_id is None:
            self._fail("world.graph_requires_location", "节点世界移动必须使用登记地点")
        return self._graph_cost(space.id, origin.location_id, destination.location_id)

    def presences_at(
        self,
        state: WorldState,
        position: WorldPosition,
    ) -> tuple[WorldPresence, ...]:
        """按稳定 ID 返回指定位置的存在体，不推进世界状态。"""

        self._validate_position(position)
        return tuple(
            sorted(
                (
                    presence
                    for presence in state.presences.values()
                    if presence.position.key == position.key
                ),
                key=lambda presence: presence.id,
            )
        )

    def presences_within(
        self,
        state: WorldState,
        center: WorldPosition,
        maximum_cost: int,
        *,
        kind_ids: frozenset[str] = frozenset(),
        owner_ids: frozenset[str] = frozenset(),
    ) -> tuple[tuple[WorldPresence, int], ...]:
        """查询同一空间内可达且成本不超过上限的存在体。"""

        if maximum_cost < 0:
            raise ValueError("世界范围查询成本不能小于 0")
        self._validate_position(center)
        found: list[tuple[WorldPresence, int]] = []
        for presence in state.presences.values():
            if presence.position.space_id != center.space_id:
                continue
            if kind_ids and presence.kind_id not in kind_ids:
                continue
            if owner_ids and presence.owner_id not in owner_ids:
                continue
            try:
                cost = self.movement_cost(center, presence.position)
            except RuleViolation as exc:
                if exc.failure.code == "world.path_unreachable":
                    continue
                raise
            if cost <= maximum_cost:
                found.append((presence, cost))
        return tuple(sorted(found, key=lambda item: (item[1], item[0].id)))

    def active_reservations_at(
        self,
        state: WorldState,
        position: WorldPosition,
        *,
        logical_time: datetime,
    ) -> tuple[WorldReservation, ...]:
        """只读查询指定位置尚未过期的预约。"""

        if logical_time.tzinfo is None or logical_time.utcoffset() is None:
            raise ValueError("世界预约查询时间必须包含时区")
        self._validate_position(position)
        return tuple(
            sorted(
                (
                    reservation
                    for reservation in state.reservations.values()
                    if reservation.position.key == position.key
                    and (
                        reservation.expires_at is None
                        or reservation.expires_at > logical_time
                    )
                ),
                key=lambda reservation: reservation.id,
            )
        )

    def _add_presence(self, operation, transaction, presences, context, events) -> None:
        presence = operation.presence
        if presence.id in presences:
            self._fail("world.presence_exists", "世界存在体已经存在")
        if presence.owner_id != transaction.actor_id:
            self._fail("world.presence_owner_mismatch", "不能创建其他主体的世界存在体")
        self._validate_position(presence.position)
        presences[presence.id] = presence
        events.append(self._event(context, transaction, "world.presence.added", presence.id, {
            "kind_id": presence.kind_id,
            "position": presence.position.key,
        }))

    def _move_presence(self, operation, transaction, presences, context, events) -> None:
        presence = self._presence(presences, operation.presence_id)
        if presence.owner_id != transaction.actor_id:
            self._fail("world.presence_owner_mismatch", "不能移动其他主体的世界存在体")
        cost = self.movement_cost(presence.position, operation.destination)
        if operation.maximum_cost is not None and cost > operation.maximum_cost:
            self._fail(
                "world.move_cost_exceeded",
                "移动成本超过本次允许上限",
                {"cost": cost, "maximum": operation.maximum_cost},
            )
        previous = presence.position
        current = replace(presence, position=operation.destination, revision=presence.revision + 1)
        presences[presence.id] = current
        events.append(self._event(context, transaction, "world.presence.moved", presence.id, {
            "origin": previous.key,
            "destination": current.position.key,
            "cost": cost,
        }))

    def _remove_presence(self, operation, transaction, presences, context, events) -> None:
        presence = self._presence(presences, operation.presence_id)
        if presence.owner_id != transaction.actor_id:
            self._fail("world.presence_owner_mismatch", "不能移除其他主体的世界存在体")
        del presences[presence.id]
        events.append(self._event(context, transaction, "world.presence.removed", presence.id, {}))

    def _reserve(self, operation, transaction, reservations, context, events) -> None:
        reservation = operation.reservation
        if reservation.id in reservations:
            self._fail("world.reservation_exists", "世界位置预约已经存在")
        if reservation.owner_id != transaction.actor_id:
            self._fail("world.reservation_owner_mismatch", "不能为其他主体预约世界位置")
        if reservation.created_at != context.logical_time:
            self._fail("world.reservation_time_mismatch", "预约创建时间必须等于逻辑时间")
        self._validate_position(reservation.position)
        existing = [
            value for value in reservations.values() if value.position.key == reservation.position.key
        ]
        if existing and (reservation.exclusive or any(value.exclusive for value in existing)):
            self._fail("world.position_occupied", "世界位置已经被排他占用")
        if reservation.position.location_id is not None:
            location = self.catalog.locations.require(reservation.position.location_id)
            if location.capacity is not None:
                used = sum(value.units for value in existing)
                if used + reservation.units > location.capacity:
                    self._fail(
                        "world.position_capacity_exceeded",
                        "世界地点容量不足",
                        {"capacity": location.capacity, "used": used},
                    )
        reservations[reservation.id] = reservation
        events.append(self._event(context, transaction, "world.position.reserved", reservation.id, {
            "position": reservation.position.key,
            "units": reservation.units,
            "exclusive": reservation.exclusive,
        }))

    def _release(self, operation, transaction, reservations, context, events) -> None:
        reservation = reservations.get(operation.reservation_id)
        if reservation is None:
            self._fail("world.reservation_unknown", "找不到世界位置预约")
        if reservation.owner_id != transaction.actor_id:
            self._fail("world.reservation_owner_mismatch", "不能释放其他主体的预约")
        del reservations[reservation.id]
        events.append(self._event(context, transaction, "world.position.released", reservation.id, {
            "position": reservation.position.key,
        }))

    def _adjust_meter(self, operation, transaction, meters, context, events) -> None:
        definition = self.catalog.meters.require(operation.meter_id)
        self._validate_scope(operation.scope)
        if operation.scope.kind not in definition.allowed_scopes:
            self._fail("world.meter_scope_rejected", "世界计量不允许用于该作用域")
        key = meter_key(operation.scope, definition.id)
        previous = meters.get(key, definition.initial)
        requested = previous + operation.amount
        if definition.overflow is MeterOverflowPolicy.CLAMP:
            current = max(definition.minimum, min(definition.maximum, requested))
        else:
            if not definition.minimum <= requested <= definition.maximum:
                self._fail(
                    "world.meter_out_of_range",
                    "世界计量变化超出范围",
                    {"minimum": definition.minimum, "maximum": definition.maximum},
                )
            current = requested
        meters[key] = current
        crossed = tuple(
            threshold
            for threshold in definition.thresholds
            if (previous < threshold <= current) or (current < threshold <= previous)
        )
        events.append(self._event(context, transaction, "world.meter.adjusted", operation.scope.key, {
            "meter_id": definition.id,
            "previous": previous,
            "current": current,
            "requested": requested,
            "crossed_thresholds": crossed,
        }))

    def _validate_position(self, position: WorldPosition) -> None:
        space = self.catalog.spaces.require(position.space_id)
        if position.location_id is not None:
            location = self.catalog.locations.require(position.location_id)
            if location.space_id != space.id:
                self._fail("world.position_space_mismatch", "地点不属于指定世界空间")
            return
        if space.topology is not WorldTopologyKind.GRID:
            self._fail("world.graph_requires_location", "节点世界不能使用自由坐标")
        _validate_grid_position(space, position.x, position.y)  # type: ignore[arg-type]

    def _validate_scope(self, scope: WorldScopeRef) -> None:
        if scope.kind is WorldScopeKind.SPACE:
            self.catalog.spaces.require(scope.id)
        elif scope.kind is WorldScopeKind.LOCATION:
            self.catalog.locations.require(scope.id)

    def _coordinates(self, position: WorldPosition) -> tuple[int, int]:
        if position.location_id is not None:
            location = self.catalog.locations.require(position.location_id)
            assert location.x is not None and location.y is not None
            return location.x, location.y
        assert position.x is not None and position.y is not None
        return position.x, position.y

    def _graph_cost(self, space_id: str, origin_id: str, destination_id: str) -> int:
        if origin_id == destination_id:
            return 0
        edges: dict[str, list[tuple[str, int]]] = {}
        for connection in self.catalog.connections:
            if connection.space_id != space_id:
                continue
            edges.setdefault(connection.origin_id, []).append(
                (connection.destination_id, connection.cost)
            )
            if connection.bidirectional:
                edges.setdefault(connection.destination_id, []).append(
                    (connection.origin_id, connection.cost)
                )
        queue = [(0, origin_id)]
        visited: dict[str, int] = {}
        while queue:
            cost, node = heappop(queue)
            if node in visited:
                continue
            visited[node] = cost
            if node == destination_id:
                return cost
            for target, edge_cost in edges.get(node, ()):
                if target not in visited:
                    heappush(queue, (cost + edge_cost, target))
        self._fail("world.path_unreachable", "两个地点之间不存在可达路径")

    @staticmethod
    def _presence(presences, presence_id: str) -> WorldPresence:
        presence = presences.get(presence_id)
        if presence is None:
            WorldEngine._fail("world.presence_unknown", "找不到世界存在体")
        return presence

    @staticmethod
    def _event(context, transaction, kind, target_id, values) -> RuleEvent:
        return RuleEvent.from_context(
            context,
            kind=kind,
            source_id=transaction.actor_id,
            target_id=target_id,
            subject_id="world.transaction",
            values={"transaction_id": transaction.id, **values},
        )

    @staticmethod
    def _fail(code: str, message: str, details: dict[str, object] | None = None) -> None:
        raise RuleViolation(code, message, details or {})


__all__ = ["WorldEngine"]
