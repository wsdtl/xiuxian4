"""玩家库存内永久物品编号的统一解析与展示。"""

from __future__ import annotations

import re

from game.core.gameplay import InventoryState, ItemInstance, ItemStack


_REFERENCE = re.compile(r"^([WEIT])?(\d+)$", re.IGNORECASE)


def asset_reference(inventory: InventoryState, asset, item_catalog) -> str:
    """返回带类型提示的角色内永久编号。"""

    definition = item_catalog.require(asset.definition_id)
    return f"{_prefix(definition)}{inventory.reference_number(asset.id)}"


def resolve_asset_reference(
    inventory: InventoryState,
    token: object,
    item_catalog,
) -> ItemStack | ItemInstance:
    """只在当前库存中解析编号，并校验可选类型前缀。"""

    match = _REFERENCE.fullmatch(str(token or "").strip())
    if match is None:
        raise ValueError("物品编号格式不正确")
    try:
        asset = inventory.asset(
            inventory.asset_id_for_reference(int(match.group(2)))
        )
    except KeyError as exc:
        raise ValueError("当前角色没有这个物品编号") from exc
    requested_prefix = str(match.group(1) or "").upper()
    actual_prefix = _prefix(item_catalog.require(asset.definition_id))
    if requested_prefix and requested_prefix != actual_prefix:
        raise ValueError(f"物品编号前缀应为 {actual_prefix}")
    return asset


def _prefix(definition) -> str:
    if definition.tags.has("item.weapon"):
        return "W"
    if definition.tags.has("item.equipment"):
        return "E"
    if definition.tags.has("storage.backpack"):
        return "T"
    return "I"


__all__ = ["asset_reference", "resolve_asset_reference"]
