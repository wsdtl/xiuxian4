"""固定物品市场政策与抽奖期望值的快速审计。"""

from __future__ import annotations

from dataclasses import dataclass

from game.core.gameplay import ItemAssetKind

from .market_items import MARKET_ITEM_POLICIES


@dataclass(frozen=True)
class MarketPriceAuditReport:
    policy_count: int
    draw_base_expected_value: float
    draw_ticket_reference_price: int


def audit_market_prices(item_catalog, draw_content) -> MarketPriceAuditReport:
    required = {
        str(definition.id)
        for definition in (
            item_catalog.require(item_id) for item_id in item_catalog.definitions.ids()
        )
        if definition.tags.has("storage.special")
        or definition.tags.has("storage.inscription")
    }
    configured = set(MARKET_ITEM_POLICIES)
    missing = sorted(required - configured)
    extra = sorted(configured - required)
    if missing:
        raise ValueError(f"可交易物品缺少市场参考价：{missing[0]}")
    if extra:
        raise ValueError(f"市场参考价引用了不可交易物品：{extra[0]}")

    for item_id, policy in MARKET_ITEM_POLICIES.items():
        definition = item_catalog.require(item_id)
        maximum = (
            1 if definition.asset_kind is ItemAssetKind.INSTANCE else definition.stack_limit
        )
        if maximum is None or policy.maximum_quantity > maximum:
            raise ValueError(f"市场最大交易数量超过物品堆叠上限：{item_id}")

    _require_monotonic(
        "血气药",
        (
            "item.consumable.small_health_medicine",
            "item.consumable.medium_health_medicine",
            "item.consumable.large_health_medicine",
        ),
    )
    _require_monotonic(
        "灵力药",
        (
            "item.consumable.small_spirit_medicine",
            "item.consumable.medium_spirit_medicine",
            "item.consumable.large_spirit_medicine",
        ),
    )

    group = draw_content.loot_table.groups[0]
    total_weight = sum(entry.weight for entry in group.entries)
    weighted_value = 0
    for entry in group.entries:
        quantity = entry.minimum_quantity
        if entry.minimum_quantity != entry.maximum_quantity:
            raise ValueError(f"抽奖奖励数量不是固定值：{entry.id}")
        if entry.award_id in {"draw_reward.currency.low", "draw_reward.currency.mid"}:
            value = quantity
        else:
            policy = MARKET_ITEM_POLICIES.get(str(entry.award_id))
            if policy is None:
                raise ValueError(f"抽奖奖励缺少市场参考价：{entry.award_id}")
            value = policy.unit_reference_price * quantity
        weighted_value += entry.weight * value
    expected = weighted_value / total_weight
    ticket_price = MARKET_ITEM_POLICIES["item.draw.ticket"].unit_reference_price
    if not expected <= ticket_price <= expected * 2:
        raise ValueError("抽奖签参考价偏离基础奖池期望值")
    return MarketPriceAuditReport(len(configured), expected, ticket_price)


def _require_monotonic(label: str, item_ids: tuple[str, ...]) -> None:
    prices = tuple(MARKET_ITEM_POLICIES[item_id].unit_reference_price for item_id in item_ids)
    if any(left >= right for left, right in zip(prices, prices[1:])):
        raise ValueError(f"{label}参考价必须随档位严格递增")


__all__ = ["MarketPriceAuditReport", "audit_market_prices"]
