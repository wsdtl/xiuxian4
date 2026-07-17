"""敌人身份、阶位和精英前缀的统一玩家展示投影。"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from types import MappingProxyType
from typing import Mapping

from game.core.gameplay import (
    ENEMY_RANK_ELITE_ID,
    EnemyInstance,
    SkinProjector,
    StableId,
    stable_id,
)


@dataclass(frozen=True)
class EnemyPresentationStyle:
    skin_id: StableId
    skin_version: int
    behavior_prefixes: Mapping[StableId, tuple[str, ...]]
    behavior_names: Mapping[StableId, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "skin_id", stable_id(self.skin_id, field="skin id"))
        if self.skin_version < 1:
            raise ValueError("敌人展示样式版本必须从 1 开始")
        prefixes = {
            stable_id(key, field="enemy behavior id"): tuple(
                str(value).strip() for value in values if str(value).strip()
            )
            for key, values in self.behavior_prefixes.items()
        }
        if any(not values or len(values) != len(set(values)) for values in prefixes.values()):
            raise ValueError("每个敌人行为必须提供不重复的精英前缀")
        names = {
            stable_id(key, field="enemy behavior id"): str(value).strip()
            for key, value in self.behavior_names.items()
        }
        if set(names) != set(prefixes) or any(not value for value in names.values()):
            raise ValueError("敌人行为短名必须完整覆盖精英前缀")
        object.__setattr__(self, "behavior_prefixes", MappingProxyType(prefixes))
        object.__setattr__(self, "behavior_names", MappingProxyType(names))


@dataclass(frozen=True)
class EnemyDisplay:
    name: str
    compact_name: str
    base_name: str
    rank_name: str
    behavior_names: tuple[str, ...]
    scope_name: str | None = None


class EnemyNameProjector:
    def __init__(self, projector: SkinProjector, style: EnemyPresentationStyle) -> None:
        if projector.pack.id != style.skin_id or projector.pack.version != style.skin_version:
            raise ValueError("敌人展示样式与世界皮肤不匹配")
        self.projector = projector
        self.style = style

    def enemy(
        self,
        instance: EnemyInstance,
        *,
        scope_id: StableId | None = None,
    ) -> EnemyDisplay:
        entry = self.projector.entry(instance.definition_id)
        base_name = entry.name
        name = base_name
        if instance.rank_id == ENEMY_RANK_ELITE_ID and instance.behavior_ids:
            primary = instance.behavior_ids[0]
            prefixes = self.style.behavior_prefixes[primary]
            digest = sha256(f"{instance.generation_seed}:{primary}".encode("utf-8")).digest()
            name = f"{prefixes[int.from_bytes(digest[:4], 'big') % len(prefixes)]}·{base_name}"
        return EnemyDisplay(
            name,
            entry.compact_name or base_name,
            base_name,
            self.projector.name(instance.rank_id),
            tuple(self.style.behavior_names[value] for value in instance.behavior_ids),
            self.projector.name(scope_id) if scope_id is not None else None,
        )


__all__ = ["EnemyDisplay", "EnemyNameProjector", "EnemyPresentationStyle"]
