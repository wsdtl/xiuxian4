"""探险批次之间的自动用药选择与原子状态写入。"""

from dataclasses import replace

from game.content.catalog.combat import (
    LARGE_MEDICINE_RECOVERY_RATIO,
    MEDIUM_MEDICINE_RECOVERY_RATIO,
    SMALL_MEDICINE_RECOVERY_RATIO,
)
from game.content.catalog.item import (
    LARGE_HEALTH_MEDICINE_ITEM_ID,
    LARGE_SPIRIT_MEDICINE_ITEM_ID,
    MEDIUM_HEALTH_MEDICINE_ITEM_ID,
    MEDIUM_SPIRIT_MEDICINE_ITEM_ID,
    SMALL_HEALTH_MEDICINE_ITEM_ID,
    SMALL_SPIRIT_MEDICINE_ITEM_ID,
)
from game.content.catalog.character import (
    AUTO_HEALTH_TARGET_RATIO,
    AUTO_HEALTH_TRIGGER_RATIO,
    AUTO_SPIRIT_TARGET_RATIO,
    AUTO_SPIRIT_TRIGGER_RATIO,
)
from game.core.gameplay import (
    HEALTH_CURRENT,
    SPIRIT_CURRENT,
    ConsumeStack,
    InventoryState,
    InventoryTransaction,
)
from game.rules.exploration import ExplorationRewardKind, ExplorationRewardReference

from .models import ExplorationStorageKinds


class ExplorationMedicineService:
    """按最少浪费原则选择药物，并在调用方工作单元内写入结果。"""

    def __init__(self, content, snapshots, inventory_engine, storage: ExplorationStorageKinds) -> None:
        self.content = content
        self.snapshots = snapshots
        self.inventory_engine = inventory_engine
        self.storage = storage

    def apply(self, uow, character, health_maximum, spirit_maximum, context):
        inventory = self.snapshots.require(
            uow, self.storage.inventory, character.id, InventoryState
        )
        consumed: dict[str, int] = {}
        resources = dict(character.resources)
        plans = (
            (
                HEALTH_CURRENT,
                health_maximum,
                AUTO_HEALTH_TRIGGER_RATIO,
                AUTO_HEALTH_TARGET_RATIO,
                (
                    (SMALL_HEALTH_MEDICINE_ITEM_ID, SMALL_MEDICINE_RECOVERY_RATIO),
                    (MEDIUM_HEALTH_MEDICINE_ITEM_ID, MEDIUM_MEDICINE_RECOVERY_RATIO),
                    (LARGE_HEALTH_MEDICINE_ITEM_ID, LARGE_MEDICINE_RECOVERY_RATIO),
                ),
            ),
            (
                SPIRIT_CURRENT,
                spirit_maximum,
                AUTO_SPIRIT_TRIGGER_RATIO,
                AUTO_SPIRIT_TARGET_RATIO,
                (
                    (SMALL_SPIRIT_MEDICINE_ITEM_ID, SMALL_MEDICINE_RECOVERY_RATIO),
                    (MEDIUM_SPIRIT_MEDICINE_ITEM_ID, MEDIUM_MEDICINE_RECOVERY_RATIO),
                    (LARGE_SPIRIT_MEDICINE_ITEM_ID, LARGE_MEDICINE_RECOVERY_RATIO),
                ),
            ),
        )
        operations = []
        for resource_id, maximum, trigger, target, medicines in plans:
            if maximum <= 0 or resources[resource_id] / maximum >= trigger:
                continue
            available = {
                definition_id: sum(
                    stack.quantity
                    for stack in inventory.stacks.values()
                    if stack.definition_id == definition_id
                )
                for definition_id, _ in medicines
            }
            while resources[resource_id] / maximum < target:
                remaining = target * maximum - resources[resource_id]
                candidates = [
                    (definition_id, ratio)
                    for definition_id, ratio in medicines
                    if available[definition_id] > 0
                ]
                if not candidates:
                    break
                definition_id, ratio = min(
                    candidates,
                    key=lambda value: (
                        max(0.0, value[1] * maximum - remaining),
                        abs(value[1] * maximum - remaining),
                    ),
                )
                stack = next(
                    value
                    for value in inventory.stacks.values()
                    if value.definition_id == definition_id
                    and value.quantity - consumed.get(value.id, 0) > 0
                )
                operations.append(ConsumeStack(stack.id, 1))
                consumed[stack.id] = consumed.get(stack.id, 0) + 1
                available[definition_id] -= 1
                resources[resource_id] = min(
                    maximum,
                    resources[resource_id] + ratio * maximum,
                )
        if not operations:
            return character, []

        outcome = self.inventory_engine.execute(
            InventoryTransaction(
                f"{context.trace_id}:auto_medicine",
                character.id,
                "inventory.exploration_auto_medicine",
                tuple(operations),
            ),
            state=inventory,
            context=context,
        )
        if outcome.failure or outcome.value is None:
            raise RuntimeError(outcome.failure.message if outcome.failure else "探险自动用药失败")
        self.snapshots.update(
            uow,
            self.storage.inventory,
            character.id,
            inventory,
            outcome.value.state,
            context.logical_time,
        )
        updated = replace(
            character,
            resources=resources,
            revision=character.revision + 1,
        )
        self.snapshots.update(
            uow,
            self.storage.character,
            character.id,
            character,
            updated,
            context.logical_time,
        )
        references = [
            ExplorationRewardReference(
                ExplorationRewardKind.ITEM,
                inventory.stacks[asset_id].definition_id,
                quantity=quantity,
            )
            for asset_id, quantity in consumed.items()
        ]
        return updated, references


__all__ = ["ExplorationMedicineService"]
