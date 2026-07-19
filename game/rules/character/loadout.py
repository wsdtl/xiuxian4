"""把当前装配转换为角色规则贡献。"""

from __future__ import annotations

from game.core.gameplay import (
    EquipmentContributionProvider,
    InventoryState,
    LoadoutState,
    WeaponContributionProvider,
    equipment_state_from_instance,
    weapon_state_from_instance,
)


def equipped_character_contributions(content, inventory: InventoryState, loadout: LoadoutState):
    """返回当前生效武器、装备和套装的完整贡献。"""

    contributions = []
    if loadout.weapon_asset_id is not None:
        contributions.append(
            WeaponContributionProvider(content.weapons).contribution(
                weapon_state_from_instance(
                    inventory.instances[loadout.weapon_asset_id]
                )
            )
        )
    equipment_states = tuple(
        equipment_state_from_instance(inventory.instances[asset_id])
        for asset_id in loadout.equipment_asset_ids
    )
    contributions.extend(
        EquipmentContributionProvider(content.equipment).contributions(
            equipment_states
        )
    )
    return tuple(contributions)


__all__ = ["equipped_character_contributions"]
