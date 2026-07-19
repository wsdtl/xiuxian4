"""正式装备实例的随机词条与套装印记联合生成规则。"""

from __future__ import annotations

from dataclasses import dataclass

from game.content.catalog.equipment import EQUIPMENT_SET_MARK_CHANCE
from game.core.gameplay import (
    EquipmentCatalog,
    EquipmentState,
    ItemGenerationCommand,
    ItemRollState,
    ItemizationEngine,
    RuleContext,
)


EQUIPMENT_GENERATION_PROTOCOL_VERSION = "rules.equipment_generation.v1"


@dataclass(frozen=True)
class EquipmentGenerationRequest:
    id: str
    asset_id: str
    definition_id: str
    content_fingerprint: str

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (
                self.id,
                self.asset_id,
                self.definition_id,
                self.content_fingerprint,
            )
        ):
            raise ValueError("装备生成请求缺少身份或内容指纹")


@dataclass(frozen=True)
class EquipmentGenerationResult:
    state: EquipmentState
    roll: ItemRollState
    set_roll: float


class EquipmentInstanceGenerator:
    """先生成开放随机词条，再独立判定套装印记。"""

    def __init__(
        self,
        equipment: EquipmentCatalog,
        itemization: ItemizationEngine,
        *,
        set_mark_chance: float = EQUIPMENT_SET_MARK_CHANCE,
    ) -> None:
        if not 0 <= set_mark_chance <= 1:
            raise ValueError("装备套装印记概率必须在 0 到 1 之间")
        if not equipment.finalized:
            equipment.finalize()
        self.equipment = equipment
        self.itemization = itemization
        self.set_mark_chance = float(set_mark_chance)

    def generate(
        self,
        request: EquipmentGenerationRequest,
        *,
        context: RuleContext,
        force_set_mark: bool = False,
    ) -> EquipmentGenerationResult:
        if not isinstance(force_set_mark, bool):
            raise TypeError("force_set_mark 必须是布尔值")
        definition = self.equipment.require(request.definition_id)
        if definition.generation_profile_id is None:
            raise ValueError(f"装备 {definition.id} 没有随机生成策略")
        checkpoint = context.random.checkpoint()
        try:
            execution = self.itemization.generate(
                ItemGenerationCommand(
                    request.id,
                    definition.generation_profile_id,
                    request.content_fingerprint,
                ),
                context=context,
            )
            set_roll = context.random.random()
            set_id = None
            if force_set_mark or set_roll < self.set_mark_chance:
                set_id = context.random.choice(self.equipment.sets.ids())
            state = self.equipment.create_state(
                asset_id=request.asset_id,
                definition_id=definition.id,
                quality_id=execution.roll.quality_id,
                roll=execution.roll,
                set_id=set_id,
            )
            return EquipmentGenerationResult(state, execution.roll, set_roll)
        except Exception:
            context.random.restore(checkpoint)
            raise


__all__ = [
    "EQUIPMENT_GENERATION_PROTOCOL_VERSION",
    "EquipmentGenerationRequest",
    "EquipmentGenerationResult",
    "EquipmentInstanceGenerator",
]
