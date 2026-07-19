"""从物品名录和库存快照生成不可变战利品回收报价。"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

from game.content.catalog.item import (
    ITEM_RECYCLE_COMPONENT_ID,
    ItemRecycleValue,
)
from game.core.gameplay import StableId


TROPHY_RECYCLE_RULESET_VERSION = "rules.trophy_recycle.v1"


@dataclass(frozen=True)
class TrophyRecycleQuoteLine:
    asset_id: str
    definition_id: StableId
    quantity: int
    unit_amount: int
    subtotal: int

    def __post_init__(self) -> None:
        if self.quantity < 1 or self.unit_amount < 1:
            raise ValueError("战利品回收报价数量和单价必须大于 0")
        if self.subtotal != self.quantity * self.unit_amount:
            raise ValueError("战利品回收报价小计不一致")


@dataclass(frozen=True)
class TrophyRecycleQuote:
    id: str
    owner_id: str
    currency_id: StableId | None
    inventory_revision: int
    lines: tuple[TrophyRecycleQuoteLine, ...]
    total_amount: int

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.owner_id.strip():
            raise ValueError("战利品回收报价缺少身份")
        if self.total_amount != sum(line.subtotal for line in self.lines):
            raise ValueError("战利品回收报价总额不一致")
        if bool(self.lines) != (self.currency_id is not None):
            raise ValueError("空报价不能携带币种，非空报价必须携带币种")


def quote_trophy_recycle(inventory, item_catalog, owner_id: str) -> TrophyRecycleQuote:
    """报价角色背包中全部未占用、允许系统回收的战利品。"""

    lines: list[TrophyRecycleQuoteLine] = []
    currency_id: StableId | None = None
    for stack in sorted(
        inventory.stacks.values(),
        key=lambda value: (value.definition_id, value.id),
    ):
        container = inventory.containers[stack.container_id]
        if container.owner_id != owner_id or container.kind != "container.backpack":
            continue
        definition = item_catalog.require(stack.definition_id)
        if not (
            definition.tags.has("item.trophy")
            and definition.tags.has("loot.recyclable")
        ):
            continue
        quantity = inventory.available_quantity(stack.id)
        if quantity < 1:
            continue
        recycle = definition.component(
            ITEM_RECYCLE_COMPONENT_ID,
            ItemRecycleValue,
        )
        if currency_id is None:
            currency_id = recycle.currency_id
        elif currency_id != recycle.currency_id:
            raise ValueError("一次战利品回收不能混用多个币种")
        lines.append(
            TrophyRecycleQuoteLine(
                stack.id,
                definition.id,
                quantity,
                recycle.unit_amount,
                quantity * recycle.unit_amount,
            )
        )
    payload = {
        "owner_id": owner_id,
        "inventory_revision": inventory.revision,
        "lines": [
            (line.asset_id, line.definition_id, line.quantity, line.unit_amount)
            for line in lines
        ],
    }
    fingerprint = sha256(
        json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
    ).hexdigest()[:24]
    return TrophyRecycleQuote(
        f"trophy-recycle:{fingerprint}",
        owner_id,
        currency_id,
        inventory.revision,
        tuple(lines),
        sum(line.subtotal for line in lines),
    )


__all__ = [
    "TROPHY_RECYCLE_RULESET_VERSION",
    "TrophyRecycleQuote",
    "TrophyRecycleQuoteLine",
    "quote_trophy_recycle",
]
