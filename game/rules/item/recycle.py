"""从物品名录和库存快照生成不可变战利品回收报价。"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Mapping

from game.content.catalog.item import (
    ITEM_RECYCLE_COMPONENT_ID,
    CurrencyRecycleYield,
    ItemRecycleYield,
    StackItemRecycleYield,
)
from game.core.gameplay import StableId


TROPHY_RECYCLE_RULESET_VERSION = "rules.trophy_recycle.v1"


@dataclass(frozen=True)
class TrophyRecycleQuoteLine:
    asset_id: str
    definition_id: StableId
    quantity: int
    output_kind: str
    output_id: StableId
    unit_amount: int
    subtotal: int

    def __post_init__(self) -> None:
        if self.quantity < 1 or self.unit_amount < 1:
            raise ValueError("战利品回收报价数量和单价必须大于 0")
        if self.subtotal != self.quantity * self.unit_amount:
            raise ValueError("战利品回收报价小计不一致")
        if self.output_kind not in {"currency", "stack_item"}:
            raise ValueError("战利品回收报价产出类型无效")


@dataclass(frozen=True)
class TrophyRecycleQuote:
    id: str
    owner_id: str
    currency_id: StableId | None
    inventory_revision: int
    lines: tuple[TrophyRecycleQuoteLine, ...]
    total_amount: int
    stack_item_totals: Mapping[StableId, int]

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.owner_id.strip():
            raise ValueError("战利品回收报价缺少身份")
        currency_total = sum(
            line.subtotal for line in self.lines if line.output_kind == "currency"
        )
        if self.total_amount != currency_total:
            raise ValueError("战利品回收报价货币总额不一致")
        currency_lines = tuple(line for line in self.lines if line.output_kind == "currency")
        if bool(currency_lines) != (self.currency_id is not None):
            raise ValueError("货币报价行与币种不一致")
        if self.currency_id is not None and any(
            line.output_id != self.currency_id for line in currency_lines
        ):
            raise ValueError("战利品回收报价混用了多个币种")
        expected_stacks: dict[StableId, int] = {}
        for line in self.lines:
            if line.output_kind == "stack_item":
                expected_stacks[line.output_id] = (
                    expected_stacks.get(line.output_id, 0) + line.subtotal
                )
        normalized = {
            key: value for key, value in self.stack_item_totals.items() if value > 0
        }
        if normalized != expected_stacks:
            raise ValueError("战利品回收报价堆叠产出总额不一致")
        object.__setattr__(self, "stack_item_totals", MappingProxyType(normalized))


def quote_trophy_recycle(inventory, item_catalog, owner_id: str) -> TrophyRecycleQuote:
    """报价角色背包中全部未占用、允许系统回收的战利品。"""

    lines: list[TrophyRecycleQuoteLine] = []
    currency_id: StableId | None = None
    stack_item_totals: dict[StableId, int] = {}
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
            ItemRecycleYield,
        )
        if isinstance(recycle, CurrencyRecycleYield):
            if currency_id is None:
                currency_id = recycle.currency_id
            elif currency_id != recycle.currency_id:
                raise ValueError("一次战利品回收不能混用多个币种")
            output_kind = "currency"
            output_id = recycle.currency_id
            unit_amount = recycle.unit_amount
        elif isinstance(recycle, StackItemRecycleYield):
            output_kind = "stack_item"
            output_id = recycle.definition_id
            unit_amount = recycle.unit_quantity
            stack_item_totals[output_id] = (
                stack_item_totals.get(output_id, 0) + quantity * unit_amount
            )
        else:
            raise TypeError(f"未知战利品回收产出：{type(recycle).__name__}")
        lines.append(
            TrophyRecycleQuoteLine(
                stack.id,
                definition.id,
                quantity,
                output_kind,
                output_id,
                unit_amount,
                quantity * unit_amount,
            )
        )
    payload = {
        "owner_id": owner_id,
        "inventory_revision": inventory.revision,
        "lines": [
            (
                line.asset_id,
                line.definition_id,
                line.quantity,
                line.output_kind,
                line.output_id,
                line.unit_amount,
            )
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
        sum(line.subtotal for line in lines if line.output_kind == "currency"),
        stack_item_totals,
    )


__all__ = [
    "TROPHY_RECYCLE_RULESET_VERSION",
    "TrophyRecycleQuote",
    "TrophyRecycleQuoteLine",
    "quote_trophy_recycle",
]
