"""全服次元灾厄名录、来源审计和两阶段稳定抽取。"""

from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
import random

from game.core.gameplay import StableId, stable_id

from .models import (
    DISASTER_ORIGIN_DOCUMENTED,
    DimensionalDisasterDefinition,
    DisasterContentAudit,
    DisasterSourceAudit,
)


DOCUMENTED_SOURCE_SOFT_RATIO = 0.70


class DimensionalDisasterCatalog:
    def __init__(self, definitions: tuple[DimensionalDisasterDefinition, ...]) -> None:
        values: dict[StableId, DimensionalDisasterDefinition] = {}
        by_source: dict[StableId, list[DimensionalDisasterDefinition]] = defaultdict(list)
        names: set[str] = set()
        for definition in definitions:
            if definition.id in values:
                raise ValueError(f"次元灾厄 ID 重复: {definition.id}")
            if definition.name in names:
                raise ValueError(f"次元灾厄正式名称重复: {definition.name}")
            values[definition.id] = definition
            names.add(definition.name)
            by_source[definition.source_world_id].append(definition)
        if not values:
            raise ValueError("次元灾厄名录不能为空")
        self._definitions = values
        self._by_source = {
            key: tuple(sorted(items, key=lambda value: value.id))
            for key, items in by_source.items()
        }

    def require(self, definition_id: StableId) -> DimensionalDisasterDefinition:
        return self._definitions[stable_id(definition_id, field="disaster id")]

    def definitions(self) -> tuple[DimensionalDisasterDefinition, ...]:
        return tuple(self._definitions[key] for key in sorted(self._definitions))

    def source_ids(self) -> tuple[StableId, ...]:
        return tuple(sorted(self._by_source))

    def for_source(self, source_world_id: StableId) -> tuple[DimensionalDisasterDefinition, ...]:
        return self._by_source.get(
            stable_id(source_world_id, field="source world id"),
            (),
        )

    def validate(self, content, playable_world_ids: tuple[StableId, ...]) -> None:
        playable = tuple(
            stable_id(value, field="playable world id")
            for value in playable_world_ids
        )
        for source_id in playable:
            if not self.for_source(source_id):
                raise ValueError(f"可进入世界没有贡献次元灾厄: {source_id}")
        unknown_sources = set(self.source_ids()) - set(playable)
        if unknown_sources:
            raise ValueError(
                "灾厄来源引用了非启用世界: " + ", ".join(sorted(unknown_sources))
            )
        enemy_owners: dict[StableId, StableId] = {}
        for definition in self.definitions():
            enemy = content.enemies.require(definition.enemy_definition_id)
            if not enemy.tags.has("enemy.identity.dimensional_disaster"):
                raise ValueError(
                    f"灾厄 {definition.id} 没有引用灾厄专属战斗定义"
                )
            owner = enemy_owners.get(definition.enemy_definition_id)
            if owner is not None:
                raise ValueError(
                    f"灾厄 {owner} 与 {definition.id} 共享了敌人身份"
                )
            enemy_owners[definition.enemy_definition_id] = definition.id

    def audit(self) -> DisasterContentAudit:
        sources = []
        warnings = []
        for source_id in self.source_ids():
            values = self.for_source(source_id)
            documented = sum(
                value.origin_kind == DISASTER_ORIGIN_DOCUMENTED for value in values
            )
            audit = DisasterSourceAudit(
                source_id,
                len(values),
                documented,
                len(values) - documented,
            )
            sources.append(audit)
            if audit.documented_ratio < DOCUMENTED_SOURCE_SOFT_RATIO:
                warnings.append(
                    f"{source_id} 文献灾厄占比 {audit.documented_ratio:.0%}, "
                    f"低于软线 {DOCUMENTED_SOURCE_SOFT_RATIO:.0%}"
                )
        return DisasterContentAudit(tuple(sources), tuple(warnings))

    def select(
        self,
        window_id: str,
        *,
        source_world_ids: tuple[StableId, ...],
        recent_definition_ids: tuple[StableId, ...] = (),
    ) -> DimensionalDisasterDefinition:
        """先抽来源再抽灾厄，避免内容较多的世界挤压其他来源。"""

        sources = tuple(
            sorted(
                stable_id(value, field="source world id")
                for value in source_world_ids
                if self.for_source(value)
            )
        )
        if not sources:
            raise ValueError("当前没有可抽取的次元灾厄来源")
        seed = int.from_bytes(
            sha256(f"dimensional-disaster.v1\0{window_id}".encode("utf-8")).digest(),
            "big",
        )
        rng = random.Random(seed)
        source_id = rng.choice(sources)
        recent = set(recent_definition_ids)
        candidates = tuple(
            value for value in self.for_source(source_id) if value.id not in recent
        ) or self.for_source(source_id)
        total = sum(value.weight for value in candidates)
        roll = rng.randrange(total)
        for value in candidates:
            roll -= value.weight
            if roll < 0:
                return value
        return candidates[-1]


__all__ = [
    "DOCUMENTED_SOURCE_SOFT_RATIO",
    "DimensionalDisasterCatalog",
]
