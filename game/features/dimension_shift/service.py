"""跃迁条件、凭证扣除和界相更新的唯一联合事务。"""

from game.content.catalog.item import (
    DIMENSION_SHIFT_ITEM_COMPONENT_ID,
    DIMENSION_SHIFT_ITEM_ID,
    DimensionShiftItemComponent,
)
from game.core.gameplay import (
    ActionSlotKind,
    ActionState,
    ConsumeStack,
    InventoryEngine,
    InventoryState,
    InventoryTransaction,
    RuleContext,
    Ruleset,
    SeededRandomSource,
)
from game.rules.character import (
    CharacterDimensionState,
    DimensionShiftResult,
    shift_dimension,
)
from game.rules.exploration import ExplorationState, ExplorationStatus

from .models import DimensionShiftStorageKinds


class DimensionShiftFeature:
    """不改变世界规则，只原子切换角色采用的世界投影。"""

    def __init__(
        self,
        database,
        content,
        world_views,
        snapshots,
        inventory_engine: InventoryEngine,
        storage: DimensionShiftStorageKinds,
    ) -> None:
        self.database = database
        self.content = content
        self.world_views = world_views
        self.snapshots = snapshots
        self.inventory_engine = inventory_engine
        self.storage = storage

    def shift(
        self,
        character_id: str,
        target_skin_id: str,
        *,
        logical_time,
    ) -> DimensionShiftResult:
        target = self.world_views.require(target_skin_id).skin.id
        normalized_id = str(character_id or "").strip()
        with self.database.unit_of_work() as uow:
            current = self.snapshots.require(
                uow,
                self.storage.dimension,
                normalized_id,
                CharacterDimensionState,
            )
            if current.skin_id == target:
                return shift_dimension(current, target, logical_time=logical_time)
            action = self.snapshots.load(
                uow, self.storage.action, normalized_id, ActionState
            )
            exploration = self.snapshots.load(
                uow, self.storage.exploration, normalized_id, ExplorationState
            )
            if (
                action is not None
                and action.running(ActionSlotKind.MAIN)
            ) or (
                exploration is not None
                and exploration.status is ExplorationStatus.RUNNING
            ):
                return DimensionShiftResult("main_action_occupied", current)
            inventory = self.snapshots.require(
                uow,
                self.storage.inventory,
                normalized_id,
                InventoryState,
            )
            definition = self.content.catalog.items.require(DIMENSION_SHIFT_ITEM_ID)
            component = definition.component(
                DIMENSION_SHIFT_ITEM_COMPONENT_ID,
                DimensionShiftItemComponent,
            )
            item_asset = next(
                (
                    value
                    for value in sorted(
                        inventory.stacks.values(), key=lambda item: item.id
                    )
                    if value.definition_id == definition.id
                    and inventory.available_quantity(value.id) >= component.quantity
                ),
                None,
            )
            if item_asset is None:
                return DimensionShiftResult("item_missing", current)
            result = shift_dimension(current, target, logical_time=logical_time)
            if result.status != "shifted" or result.current is None:
                return result
            trace_id = f"dimension-shift:{normalized_id}:{current.revision}:{target}"
            inventory_outcome = self.inventory_engine.execute(
                InventoryTransaction(
                    f"{trace_id}:inventory",
                    normalized_id,
                    "dimension.shift",
                    (ConsumeStack(item_asset.id, component.quantity),),
                ),
                state=inventory,
                context=RuleContext(
                    trace_id,
                    "feature.dimension_shift.v1",
                    Ruleset("ruleset.dimension_shift"),
                    logical_time,
                    SeededRandomSource(trace_id),
                ),
            )
            if inventory_outcome.failure or inventory_outcome.value is None:
                raise RuntimeError(
                    inventory_outcome.failure.message
                    if inventory_outcome.failure
                    else "跃迁凭证扣除失败"
                )
            self.snapshots.update(
                uow,
                self.storage.inventory,
                normalized_id,
                inventory,
                inventory_outcome.value.state,
                logical_time,
            )
            self.snapshots.update(
                uow,
                self.storage.dimension,
                normalized_id,
                current,
                result.current,
                logical_time,
            )
            uow.commit()
            return result


__all__ = ["DimensionShiftFeature"]
