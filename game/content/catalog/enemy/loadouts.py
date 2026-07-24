"""World-weighted enemy behavior pools independent from enemy identities."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from game.core.gameplay import StableId, stable_id

from ..world import MAGIC_WORLD_ID, STELLAR_RING_WORLD_ID, TAIXUAN_WORLD_ID
from .behaviors import ENEMY_BEHAVIOR_CONTENT


@dataclass(frozen=True)
class EnemyBehaviorProfileDefinition:
    world_id: StableId
    behavior_weights: Mapping[StableId, int]

    def __post_init__(self) -> None:
        object.__setattr__(self, "world_id", stable_id(self.world_id, field="world id"))
        weights = {
            stable_id(key, field="enemy behavior id"): int(value)
            for key, value in self.behavior_weights.items()
        }
        if not weights or any(value < 1 for value in weights.values()):
            raise ValueError("世界敌人行为权重必须全部大于 0")
        object.__setattr__(self, "behavior_weights", MappingProxyType(weights))


class EnemyBehaviorProfileCatalog:
    def __init__(self, definitions: tuple[EnemyBehaviorProfileDefinition, ...]) -> None:
        values = {value.world_id: value for value in definitions}
        if len(values) != len(definitions):
            raise ValueError("世界敌人行为倾向不能重复")
        self._definitions = MappingProxyType(values)

    def require(self, world_id: StableId) -> EnemyBehaviorProfileDefinition:
        key = stable_id(world_id, field="world id")
        try:
            return self._definitions[key]
        except KeyError as exc:
            raise KeyError(f"世界没有登记敌人行为倾向：{key}") from exc

    def validate(self, playable_world_ids: tuple[StableId, ...]) -> None:
        worlds = frozenset(stable_id(value, field="world id") for value in playable_world_ids)
        if set(self._definitions) != set(worlds):
            raise ValueError("敌人行为倾向必须完整覆盖全部可进入世界")
        known = frozenset(value.id for value in ENEMY_BEHAVIOR_CONTENT.behaviors)
        for definition in self._definitions.values():
            if set(definition.behavior_weights) != set(known):
                raise ValueError(f"世界敌人行为倾向没有完整覆盖行为库：{definition.world_id}")


_ALL_BEHAVIOR_KEYS = tuple(
    value.id.removeprefix("enemy.behavior.")
    for value in ENEMY_BEHAVIOR_CONTENT.behaviors
)


def _profile(world_id: str, preferred: frozenset[str]) -> EnemyBehaviorProfileDefinition:
    unknown = preferred - set(_ALL_BEHAVIOR_KEYS)
    if unknown:
        raise KeyError("世界敌人行为倾向引用未知行为：" + ", ".join(sorted(unknown)))
    return EnemyBehaviorProfileDefinition(
        world_id,
        {
            f"enemy.behavior.{key}": 18 if key in preferred else 10
            for key in _ALL_BEHAVIOR_KEYS
        },
    )


ENEMY_BEHAVIOR_PROFILE_CATALOG = EnemyBehaviorProfileCatalog(
    (
        _profile(
            TAIXUAN_WORLD_ID,
            frozenset({"poison", "bleed", "mark_detonation", "counter", "lifesteal", "sleep", "slow", "sunder", "sacrifice"}),
        ),
        _profile(
            MAGIC_WORLD_ID,
            frozenset({"burn", "freeze", "area_attack", "resource_drain", "shield", "regeneration", "stun", "cooldown_lock", "charged_burst"}),
        ),
        _profile(
            STELLAR_RING_WORLD_ID,
            frozenset({"rapid_attack", "combo", "follow_up", "true_damage", "splash", "shield", "evasion", "mark_detonation", "cooldown_lock"}),
        ),
    )
)


__all__ = [
    "ENEMY_BEHAVIOR_PROFILE_CATALOG",
    "EnemyBehaviorProfileCatalog",
    "EnemyBehaviorProfileDefinition",
]
