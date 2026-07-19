"""跨装备来源共享的下一件套装掉落保证状态。"""

from dataclasses import dataclass, replace

from game.core.gameplay import EquipmentSetGuaranteeItemComponent


EQUIPMENT_SET_GUARANTEE_AGGREGATE = "snapshot.equipment_set_guarantee"


@dataclass(frozen=True)
class EquipmentSetGuaranteeState:
    character_id: str
    charges: int = 0
    revision: int = 0

    def __post_init__(self) -> None:
        if not self.character_id.strip():
            raise ValueError("EquipmentSetGuaranteeState.character_id 不能为空")
        for field_name in ("charges", "revision"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"EquipmentSetGuaranteeState.{field_name} 必须是整数")
        if self.charges < 0 or self.revision < 0:
            raise ValueError("装备套装保证次数和 revision 不能小于 0")


def activate_equipment_set_guarantee(
    state: EquipmentSetGuaranteeState,
    component: EquipmentSetGuaranteeItemComponent,
) -> EquipmentSetGuaranteeState:
    if state.charges + component.charges > component.maximum_active_charges:
        raise ValueError("下一件装备的套装保证已经生效")
    return replace(
        state,
        charges=state.charges + component.charges,
        revision=state.revision + 1,
    )


def consume_equipment_set_guarantee(
    state: EquipmentSetGuaranteeState,
    amount: int,
) -> EquipmentSetGuaranteeState:
    if isinstance(amount, bool) or not isinstance(amount, int) or amount < 1:
        raise ValueError("消耗的装备套装保证次数必须是正整数")
    if amount > state.charges:
        raise ValueError("装备套装保证剩余次数不足")
    return replace(
        state,
        charges=state.charges - amount,
        revision=state.revision + 1,
    )


__all__ = [
    "EQUIPMENT_SET_GUARANTEE_AGGREGATE",
    "EquipmentSetGuaranteeState",
    "activate_equipment_set_guarantee",
    "consume_equipment_set_guarantee",
]
