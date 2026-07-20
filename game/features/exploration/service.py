"""持续探险玩法的唯一公开入口。"""

from dataclasses import replace
from datetime import datetime

from game.core.gameplay import (
    ActionSlotKind,
    ActionState,
    HEALTH_CURRENT,
    CharacterState,
    MovePresence,
    RuleContext,
    Ruleset,
    SeededRandomSource,
    WorldPosition,
    WorldState,
    WorldTransaction,
)
from game.rules.character import PRIMARY_WORLD_ID
from game.rules.exploration import (
    EXPLORATION_AGGREGATE,
    EXPLORATION_RULESET_VERSION,
    ExplorationBatchResult,
    ExplorationState,
    ExplorationStatus,
    ExplorationStopReason,
    start_exploration,
    stop_exploration,
)

from .models import (
    MAX_CATCH_UP_BATCHES,
    MAX_DISCOVERABLE_EXPLORATIONS,
    ExplorationMovementResult,
    ExplorationOperationResult,
    ExplorationStorageKinds,
)
from .settlement import ExplorationSettlementService


class ExplorationFeature:
    """组织移动、启停和批次结算，不包含命令或展示协议。"""

    def __init__(
        self,
        database,
        content,
        snapshots,
        rewards,
        inventory_engine,
        player_lineup,
        battle_reports,
        storage: ExplorationStorageKinds,
        reward_keys_factory,
    ) -> None:
        self.database = database
        self.content = content
        self.snapshots = snapshots
        self.storage = storage
        self.settlement = ExplorationSettlementService(
            database,
            content,
            snapshots,
            rewards,
            inventory_engine,
            player_lineup,
            battle_reports,
            storage,
            reward_keys_factory,
        )

    def start(self, character_id: str, *, logical_time: datetime) -> ExplorationOperationResult:
        with self.database.unit_of_work() as uow:
            action_state = self.snapshots.load(
                uow, self.storage.action, character_id, ActionState
            )
            if action_state is not None and action_state.running(ActionSlotKind.MAIN):
                return ExplorationOperationResult("main_action_occupied")
            previous = self.snapshots.load(
                uow, EXPLORATION_AGGREGATE, character_id, ExplorationState
            )
            if previous is not None and previous.status is ExplorationStatus.RUNNING:
                return ExplorationOperationResult("already_running", previous)
            character = self.snapshots.require(
                uow, self.storage.character, character_id, CharacterState
            )
            if character.resources[HEALTH_CURRENT] <= 0:
                return ExplorationOperationResult("health_depleted", previous)
            world = self.snapshots.require(
                uow, self.storage.world, PRIMARY_WORLD_ID, WorldState
            )
            presence = _presence(world, character_id)
            location_id = presence.position.location_id
            if location_id is None:
                return ExplorationOperationResult("not_in_region", previous)
            try:
                region = self.content.exploration_regions.for_location(location_id)
            except KeyError:
                return ExplorationOperationResult("not_in_region", previous)
            session_id = f"exploration:{character_id}:{logical_time.isoformat()}"
            current = start_exploration(
                character_id,
                session_id,
                region.id,
                location_id,
                logical_time=logical_time,
            )
            if previous is None:
                self.snapshots.insert(
                    uow, EXPLORATION_AGGREGATE, character_id, current, logical_time
                )
            else:
                current = replace(current, revision=previous.revision + 1)
                self.snapshots.update(
                    uow,
                    EXPLORATION_AGGREGATE,
                    character_id,
                    previous,
                    current,
                    logical_time,
                )
            uow.commit()
            return ExplorationOperationResult("started", current)

    def move(
        self,
        character_id: str,
        location_id: str,
        *,
        logical_time: datetime,
    ) -> ExplorationMovementResult:
        location = self.content.catalog.world.locations.require(location_id)
        with self.database.unit_of_work() as uow:
            exploration = self.snapshots.load(
                uow, EXPLORATION_AGGREGATE, character_id, ExplorationState
            )
            if exploration is not None and exploration.status is ExplorationStatus.RUNNING:
                return ExplorationMovementResult("exploring")
            world = self.snapshots.require(
                uow, self.storage.world, PRIMARY_WORLD_ID, WorldState
            )
            presence = _presence(world, character_id)
            if presence.position.location_id == location.id:
                return ExplorationMovementResult("already_there", location.id)
            context = _context(
                f"exploration:move:{character_id}:{location.id}:{world.revision}",
                logical_time,
            )
            outcome = self.content.catalog.world_engine.execute(
                WorldTransaction(
                    context.trace_id,
                    character_id,
                    world.revision,
                    (
                        MovePresence(
                            presence.id,
                            WorldPosition(location.space_id, location_id=location.id),
                        ),
                    ),
                ),
                state=world,
                context=context,
            )
            if outcome.failure or outcome.value is None:
                return ExplorationMovementResult("failed")
            self.snapshots.update(
                uow,
                self.storage.world,
                PRIMARY_WORLD_ID,
                world,
                outcome.value.state,
                logical_time,
            )
            uow.commit()
            return ExplorationMovementResult("moved", location.id)

    def stop(self, character_id: str, *, logical_time: datetime) -> ExplorationOperationResult:
        settled = self.settle_due(character_id, logical_time=logical_time)
        with self.database.unit_of_work() as uow:
            current = self.snapshots.load(
                uow, EXPLORATION_AGGREGATE, character_id, ExplorationState
            )
            if current is None:
                return ExplorationOperationResult("not_started", batches=settled.batches)
            if current.status is ExplorationStatus.STOPPED:
                return ExplorationOperationResult("already_stopped", current, settled.batches)
            stopped = stop_exploration(
                current,
                ExplorationStopReason.MANUAL,
                logical_time=logical_time,
            )
            self.snapshots.update(
                uow,
                EXPLORATION_AGGREGATE,
                character_id,
                current,
                stopped,
                logical_time,
            )
            uow.commit()
            return ExplorationOperationResult("stopped", stopped, settled.batches)

    def load(
        self,
        character_id: str,
        *,
        logical_time: datetime,
        settle_due: bool = True,
    ) -> ExplorationOperationResult:
        batches: tuple[ExplorationBatchResult, ...] = ()
        if settle_due:
            batches = self.settle_due(character_id, logical_time=logical_time).batches
        state = self.settlement.load_state(character_id)
        return ExplorationOperationResult("ok" if state else "not_started", state, batches)

    def settle_due(
        self,
        character_id: str,
        *,
        logical_time: datetime,
        limit: int = MAX_CATCH_UP_BATCHES,
    ) -> ExplorationOperationResult:
        return self.settlement.settle_due(
            character_id,
            logical_time=logical_time,
            limit=limit,
        )

    def settle_all_due(
        self,
        *,
        logical_time: datetime,
        limit: int = MAX_DISCOVERABLE_EXPLORATIONS,
    ) -> int:
        return self.settlement.settle_all_due(logical_time=logical_time, limit=limit)


def _presence(world: WorldState, character_id: str):
    return next(value for value in world.presences.values() if value.owner_id == character_id)


def _context(trace_id: str, logical_time: datetime) -> RuleContext:
    return RuleContext(
        trace_id,
        EXPLORATION_RULESET_VERSION,
        Ruleset("ruleset.standard"),
        logical_time,
        SeededRandomSource(trace_id),
    )


__all__ = ["ExplorationFeature"]
