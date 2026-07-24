"""世界志的内容定义与只读目录。"""

from __future__ import annotations

from dataclasses import dataclass

from game.core.gameplay import StableId, stable_id


@dataclass(frozen=True)
class WorldLoreRecord:
    id: StableId
    threshold: int
    title: str
    paragraphs: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="world lore record id"))
        if not 0 <= int(self.threshold) <= 100:
            raise ValueError("世界志阶段必须位于 0% 到 100%")
        title = str(self.title or "").strip()
        paragraphs = tuple(
            text
            for value in self.paragraphs
            if (text := str(value or "").strip())
        )
        if not title or not paragraphs:
            raise ValueError("世界志记录缺少标题或正文")
        object.__setattr__(self, "threshold", int(self.threshold))
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "paragraphs", paragraphs)


@dataclass(frozen=True)
class WorldLoreDefinition:
    world_id: StableId
    overview: str
    records: tuple[WorldLoreRecord, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "world_id", stable_id(self.world_id, field="world id"))
        overview = str(self.overview or "").strip()
        records = tuple(self.records)
        thresholds = tuple(value.threshold for value in records)
        if not overview:
            raise ValueError("世界志缺少世界概览")
        if thresholds != (0, 25, 50, 75, 100):
            raise ValueError("正式世界志必须按 0/25/50/75/100 五阶段定义")
        if len({value.id for value in records}) != len(records):
            raise ValueError("同一世界志存在重复记录 ID")
        object.__setattr__(self, "overview", overview)
        object.__setattr__(self, "records", records)

    def unlocked(self, percent: int) -> tuple[WorldLoreRecord, ...]:
        progress = max(0, min(100, int(percent)))
        return tuple(value for value in self.records if value.threshold <= progress)


class WorldLoreCatalog:
    def __init__(self, definitions: tuple[WorldLoreDefinition, ...]) -> None:
        values = tuple(definitions)
        by_world = {value.world_id: value for value in values}
        if len(by_world) != len(values):
            raise ValueError("世界志目录存在重复 world_id")
        self._definitions = values
        self._by_world = by_world

    def require(self, world_id: StableId) -> WorldLoreDefinition:
        key = stable_id(world_id, field="world id")
        try:
            return self._by_world[key]
        except KeyError as exc:
            raise KeyError(f"当前世界没有正式世界志：{key}") from exc

    def definitions(self) -> tuple[WorldLoreDefinition, ...]:
        return self._definitions

    def world_ids(self) -> tuple[StableId, ...]:
        return tuple(value.world_id for value in self._definitions)


__all__ = ["WorldLoreCatalog", "WorldLoreDefinition", "WorldLoreRecord"]
