"""正式武器的静态价值估算与快速横向审计。"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Iterable, Mapping

from game.core.gameplay import ValueVector

from .blueprints import WEAPON_BLUEPRINTS, WeaponBlueprint


PRIMARY_HIT_FACTORS: Mapping[str, float] = MappingProxyType(
    {
        "heavy": 1.0,
        "swift": 1.0,
        "multi2": 2.0,
        "multi3": 3.0,
        "execute": 1.0,
        "missing_rage": 1.0,
        "max_health": 1.0,
        "true_strike": 1.0,
        "pierce": 1.0,
        "poison": 1.0,
        "bleed": 1.0,
        "burn": 1.0,
        "frost": 1.0,
        "spirit_drain": 1.0,
        "spirit_burst": 1.0,
        "element_cycle": 1.0,
        "detonate": 1.0,
        "mark": 1.0,
        "self_cost": 1.0,
        "volatile": 1.05,
        "borrowed_force": 1.50,
        "deferred_echo": 1.85,
    }
)


PRIMARY_VALUES: Mapping[str, ValueVector] = MappingProxyType(
    {
        "heavy": ValueVector(),
        "swift": ValueVector(tempo=3),
        "multi2": ValueVector(volatility=1),
        "multi3": ValueVector(volatility=2),
        "execute": ValueVector(offense=8, volatility=4),
        "missing_rage": ValueVector(offense=7, volatility=6),
        "max_health": ValueVector(offense=8),
        "true_strike": ValueVector(offense=8),
        "pierce": ValueVector(offense=6),
        "poison": ValueVector(offense=8, volatility=2),
        "bleed": ValueVector(offense=8, volatility=2),
        "burn": ValueVector(offense=8, volatility=2),
        "frost": ValueVector(offense=5, control=3),
        "spirit_drain": ValueVector(sustain=4, control=4),
        "spirit_burst": ValueVector(offense=6, volatility=4),
        "element_cycle": ValueVector(offense=7, volatility=3),
        "detonate": ValueVector(offense=11, volatility=7),
        "mark": ValueVector(offense=4, volatility=4),
        "self_cost": ValueVector(offense=7, volatility=8),
        "volatile": ValueVector(offense=4, volatility=14),
        "borrowed_force": ValueVector(offense=7, volatility=5),
        "deferred_echo": ValueVector(offense=8, tempo=5, volatility=3),
    }
)


SUPPORT_VALUES: Mapping[str, ValueVector] = MappingProxyType(
    {
        "none": ValueVector(),
        "sunder": ValueVector(offense=5, control=3),
        "crit": ValueVector(offense=7, tempo=2),
        "delay": ValueVector(tempo=3, control=5),
        "burn": ValueVector(offense=8, volatility=2),
        "stun": ValueVector(control=11, volatility=3),
        "lifesteal": ValueVector(sustain=11),
        "on_kill": ValueVector(tempo=10, volatility=5),
        "haste": ValueVector(tempo=8),
        "guard": ValueVector(survival=8),
        "extra_turn": ValueVector(tempo=14, volatility=5),
        "evasion": ValueVector(survival=7, tempo=2),
        "cooldown": ValueVector(tempo=8, volatility=4),
        "slow": ValueVector(tempo=2, control=6),
        "on_crit": ValueVector(offense=8, volatility=5),
        "mark": ValueVector(offense=5, volatility=4),
        "execute": ValueVector(offense=8, volatility=3),
        "poison": ValueVector(offense=8, volatility=2),
        "bleed": ValueVector(offense=8, volatility=2),
        "spirit_drain": ValueVector(sustain=4, control=4),
        "freeze": ValueVector(control=12, volatility=4),
        "weaken": ValueVector(survival=4, control=5),
        "detonate": ValueVector(offense=10, volatility=7),
        "heal": ValueVector(sustain=10),
        "mark_self": ValueVector(offense=5, tempo=3, volatility=3),
        "shield": ValueVector(survival=10),
        "death_guard": ValueVector(survival=12, volatility=5),
        "resource_balance": ValueVector(sustain=10, volatility=3),
        "dispel": ValueVector(control=9),
        "thorns": ValueVector(survival=4, offense=5, volatility=5),
        "block": ValueVector(survival=10),
        "on_kill_heal": ValueVector(sustain=9, volatility=5),
        "damage_cap": ValueVector(survival=14),
        "immunity": ValueVector(survival=15, volatility=5),
        "taunt": ValueVector(survival=3, control=9),
        "sleep": ValueVector(control=13, volatility=4),
        "cooldown_delay": ValueVector(tempo=3, control=10),
        "evasion_counter": ValueVector(offense=5, survival=6, volatility=4),
        "on_crit_stun": ValueVector(offense=6, control=8, volatility=6),
        "shield_counter": ValueVector(offense=5, survival=8, volatility=4),
        "self_cost": ValueVector(offense=5, volatility=8),
    }
)


TARGET_FACTORS: Mapping[str, float] = MappingProxyType(
    {
        "single": 1.0,
        "lowest": 1.08,
        "random": 1.0,
        "adjacent": 1.45,
        "all": 1.80,
    }
)


@dataclass(frozen=True)
class WeaponBalanceEntry:
    key: str
    declared: ValueVector
    estimated: ValueVector
    damage_points: float
    availability: float

    @property
    def total_delta(self) -> float:
        return self.declared.total - self.estimated.total


@dataclass(frozen=True)
class WeaponBalanceReport:
    entries: Mapping[str, WeaponBalanceEntry] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "entries", MappingProxyType(dict(self.entries)))

    @property
    def minimum_estimated_total(self) -> float:
        return min(value.estimated.total for value in self.entries.values())

    @property
    def maximum_estimated_total(self) -> float:
        return max(value.estimated.total for value in self.entries.values())

    def outliers(self, maximum_delta: float = 18.0) -> tuple[WeaponBalanceEntry, ...]:
        if maximum_delta < 0:
            raise ValueError("maximum_delta 不能小于 0")
        return tuple(
            sorted(
                (
                    value
                    for value in self.entries.values()
                    if abs(value.total_delta) > maximum_delta
                ),
                key=lambda value: abs(value.total_delta),
                reverse=True,
            )
        )


class WeaponBalanceAuditor:
    """按统一机制表快速估算武器，不运行完整战斗时间线。"""

    def audit(
        self,
        blueprints: Iterable[WeaponBlueprint] = WEAPON_BLUEPRINTS,
    ) -> WeaponBalanceReport:
        entries: dict[str, WeaponBalanceEntry] = {}
        for blueprint in blueprints:
            if blueprint.key in entries:
                raise ValueError(f"武器平衡审计发现重复键：{blueprint.key}")
            entries[blueprint.key] = estimate_weapon_value(blueprint)
        if not entries:
            raise ValueError("武器平衡审计不能为空")
        return WeaponBalanceReport(entries)


def estimate_weapon_value(blueprint: WeaponBlueprint) -> WeaponBalanceEntry:
    try:
        hit_factor = PRIMARY_HIT_FACTORS[blueprint.primary]
        primary = PRIMARY_VALUES[blueprint.primary]
        support = SUPPORT_VALUES[blueprint.support]
        target_factor = TARGET_FACTORS[blueprint.targeting]
    except KeyError as error:
        raise ValueError(
            f"武器 {blueprint.key} 存在未登记价值的机制：{error.args[0]}"
        ) from error
    availability = 1.0 / (
        1.0
        + blueprint.cooldown * 0.08
        + blueprint.spirit_cost * 0.006
    )
    damage_points = (
        blueprint.power
        * hit_factor
        * target_factor
        * availability
        * 42.0
    )
    estimated = ValueVector(offense=damage_points) + primary + support
    return WeaponBalanceEntry(
        blueprint.key,
        blueprint.value,
        estimated,
        damage_points,
        availability,
    )


__all__ = [
    "PRIMARY_HIT_FACTORS",
    "PRIMARY_VALUES",
    "SUPPORT_VALUES",
    "TARGET_FACTORS",
    "WeaponBalanceAuditor",
    "WeaponBalanceEntry",
    "WeaponBalanceReport",
    "estimate_weapon_value",
]

