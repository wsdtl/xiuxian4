"""次元灾厄的固定叙事定义和来源审计模型。"""

from __future__ import annotations

from dataclasses import dataclass

from game.core.gameplay import StableId, stable_id


DISASTER_ORIGIN_DOCUMENTED = "documented"
DISASTER_ORIGIN_ORIGINAL = "original"
DISASTER_ORIGIN_KINDS = frozenset(
    {DISASTER_ORIGIN_DOCUMENTED, DISASTER_ORIGIN_ORIGINAL}
)


@dataclass(frozen=True)
class DimensionalDisasterDefinition:
    """一只不受世界皮肤投影的次元灾厄。"""

    id: StableId
    source_skin_id: StableId
    enemy_definition_id: StableId
    combat_behavior_keys: tuple[str, ...]
    origin_kind: str
    source_note: str
    name: str
    title: str
    scene: str
    story: str
    farewell: str
    feather_text: str
    weight: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="disaster id"))
        object.__setattr__(
            self,
            "source_skin_id",
            stable_id(self.source_skin_id, field="source skin id"),
        )
        object.__setattr__(
            self,
            "enemy_definition_id",
            stable_id(self.enemy_definition_id, field="enemy id"),
        )
        behavior_keys = tuple(
            str(value or "").strip() for value in self.combat_behavior_keys
        )
        if not behavior_keys or any(not value for value in behavior_keys):
            raise ValueError(f"次元灾厄缺少战斗行为模板：{self.id}")
        if len(behavior_keys) != len(set(behavior_keys)):
            raise ValueError(f"次元灾厄战斗行为模板重复：{self.id}")
        object.__setattr__(self, "combat_behavior_keys", behavior_keys)
        origin_kind = str(self.origin_kind or "").strip().lower()
        if origin_kind not in DISASTER_ORIGIN_KINDS:
            raise ValueError(f"未知灾厄来源类型: {self.origin_kind}")
        object.__setattr__(self, "origin_kind", origin_kind)
        for field_name in (
            "source_note",
            "name",
            "title",
            "scene",
            "story",
            "farewell",
            "feather_text",
        ):
            value = str(getattr(self, field_name) or "").strip()
            if not value:
                raise ValueError(f"次元灾厄缺少 {field_name}: {self.id}")
            object.__setattr__(self, field_name, value)
        if self.weight < 1:
            raise ValueError("次元灾厄抽取权重必须大于 0")


@dataclass(frozen=True)
class DisasterSourceAudit:
    source_skin_id: StableId
    total: int
    documented: int
    original: int

    @property
    def documented_ratio(self) -> float:
        return self.documented / self.total if self.total else 0.0


@dataclass(frozen=True)
class DisasterContentAudit:
    sources: tuple[DisasterSourceAudit, ...]
    warnings: tuple[str, ...] = ()


__all__ = [
    "DISASTER_ORIGIN_DOCUMENTED",
    "DISASTER_ORIGIN_KINDS",
    "DISASTER_ORIGIN_ORIGINAL",
    "DimensionalDisasterDefinition",
    "DisasterContentAudit",
    "DisasterSourceAudit",
]
