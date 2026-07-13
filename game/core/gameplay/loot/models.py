"""版本化掉落表、保底状态、抽取命令与审计凭据。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from ..events import RuleEvent
from ..ids import StableId, stable_id
from ..registry import DefinitionRegistry
from ..tags import EMPTY_TAGS, TagSet


LOOT_CHANCE_SCALE = 1_000_000
LOOT_MODIFIER_SCALE = 10_000


class LootGroupMode(str, Enum):
    WEIGHTED_ONE = "weighted_one"
    INDEPENDENT = "independent"
    ALL = "all"


@dataclass(frozen=True)
class LootEntry:
    id: StableId
    award_id: StableId | None
    weight: int = 0
    chance: int = 0
    minimum_quantity: int = 1
    maximum_quantity: int = 1
    required_tags: TagSet = EMPTY_TAGS
    blocked_tags: TagSet = EMPTY_TAGS

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="loot entry id"))
        if self.award_id is not None:
            object.__setattr__(self, "award_id", stable_id(self.award_id, field="award id"))
        if self.weight < 0 or not 0 <= self.chance <= LOOT_CHANCE_SCALE:
            raise ValueError("LootEntry 权重或概率超出边界")
        if self.minimum_quantity < 1 or self.maximum_quantity < self.minimum_quantity:
            raise ValueError("LootEntry 数量区间无效")

    def eligible(self, tags: TagSet) -> bool:
        return tags.allows(required=self.required_tags, blocked=self.blocked_tags)


@dataclass(frozen=True)
class LootGroup:
    id: StableId
    mode: LootGroupMode
    entries: tuple[LootEntry, ...]
    draws: int = 1
    unique: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="loot group id"))
        mode = LootGroupMode(self.mode)
        entries = tuple(self.entries)
        if not entries or self.draws < 1:
            raise ValueError("LootGroup 必须包含条目且抽取次数大于 0")
        ids = [entry.id for entry in entries]
        if len(ids) != len(set(ids)):
            raise ValueError("LootGroup 条目 ID 不能重复")
        if mode is LootGroupMode.WEIGHTED_ONE:
            if any(entry.weight < 1 or entry.chance for entry in entries):
                raise ValueError("加权组只能使用正整数 weight")
        elif mode is LootGroupMode.INDEPENDENT:
            if any(entry.weight or entry.chance < 0 for entry in entries):
                raise ValueError("独立判定组只能使用 chance")
        elif any(entry.weight or entry.chance for entry in entries):
            raise ValueError("必得组不能设置 weight 或 chance")
        if self.unique and self.draws > len(entries):
            raise ValueError("不重复抽取次数不能超过条目数")
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "entries", entries)


@dataclass(frozen=True)
class LootPityDefinition:
    group_id: StableId
    threshold: int
    qualifying_entry_ids: frozenset[StableId]
    guaranteed_entry_ids: frozenset[StableId]

    def __post_init__(self) -> None:
        object.__setattr__(self, "group_id", stable_id(self.group_id, field="loot group id"))
        qualifying = frozenset(
            stable_id(value, field="loot entry id") for value in self.qualifying_entry_ids
        )
        guaranteed = frozenset(
            stable_id(value, field="loot entry id") for value in self.guaranteed_entry_ids
        )
        if self.threshold < 1 or not qualifying or not guaranteed:
            raise ValueError("保底阈值和条目集合不能为空")
        if not guaranteed.issubset(qualifying):
            raise ValueError("保底候选必须属于保底命中集合")
        object.__setattr__(self, "qualifying_entry_ids", qualifying)
        object.__setattr__(self, "guaranteed_entry_ids", guaranteed)


@dataclass(frozen=True)
class LootTableDefinition:
    id: StableId
    version: int
    groups: tuple[LootGroup, ...]
    pity: LootPityDefinition | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="loot table id"))
        groups = tuple(self.groups)
        if self.version < 1 or not groups:
            raise ValueError("掉落表版本必须大于 0 且至少包含一个组")
        group_ids = [group.id for group in groups]
        if len(group_ids) != len(set(group_ids)):
            raise ValueError("掉落表组 ID 不能重复")
        entry_ids = [entry.id for group in groups for entry in group.entries]
        if len(entry_ids) != len(set(entry_ids)):
            raise ValueError("同一掉落表中的条目 ID 必须全局唯一")
        if self.pity is not None:
            group = next((value for value in groups if value.id == self.pity.group_id), None)
            if group is None or group.mode is not LootGroupMode.WEIGHTED_ONE:
                raise ValueError("保底只能引用加权组")
            known = {entry.id for entry in group.entries if entry.award_id is not None}
            if not self.pity.qualifying_entry_ids.issubset(known):
                raise ValueError("保底引用了未知或空结果条目")
        object.__setattr__(self, "groups", groups)


class LootCatalog:
    def __init__(self) -> None:
        self.definitions = DefinitionRegistry[LootTableDefinition]("LootTable")
        self._finalized = False

    def register(self, definition: LootTableDefinition) -> LootTableDefinition:
        if self._finalized:
            raise RuntimeError("掉落目录已经完成组装")
        return self.definitions.register(definition)

    def require(self, table_id: StableId) -> LootTableDefinition:
        return self.definitions.require(table_id)

    def finalize(self) -> None:
        if self._finalized:
            return
        self.definitions.freeze()
        self._finalized = True

    @property
    def finalized(self) -> bool:
        return self._finalized


@dataclass(frozen=True)
class LootState:
    owner_id: str
    pity_counters: Mapping[StableId, int] = field(default_factory=dict)
    revision: int = 0

    def __post_init__(self) -> None:
        if not self.owner_id.strip() or self.revision < 0:
            raise ValueError("LootState 所有者或 revision 无效")
        counters = {
            stable_id(key, field="loot table id"): int(value)
            for key, value in self.pity_counters.items()
        }
        if any(value < 0 for value in counters.values()):
            raise ValueError("保底计数不能小于 0")
        object.__setattr__(self, "pity_counters", MappingProxyType(counters))


@dataclass(frozen=True)
class LootRollCommand:
    id: str
    actor_id: str
    table_id: StableId
    expected_revision: int
    rolls: int = 1
    modifier_basis_points: Mapping[StableId, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.actor_id.strip():
            raise ValueError("LootRollCommand 缺少身份")
        object.__setattr__(self, "table_id", stable_id(self.table_id, field="loot table id"))
        if self.expected_revision < 0 or not 1 <= self.rolls <= 100:
            raise ValueError("掉落 revision 或批量次数无效")
        modifiers = {
            stable_id(key, field="loot entry id"): int(value)
            for key, value in self.modifier_basis_points.items()
        }
        if any(not 0 <= value <= 100_000 for value in modifiers.values()):
            raise ValueError("掉落修正必须处于 0 到 100000 基点")
        object.__setattr__(self, "modifier_basis_points", MappingProxyType(modifiers))


@dataclass(frozen=True)
class LootAward:
    roll_index: int
    draw_index: int
    group_id: StableId
    entry_id: StableId
    award_id: StableId
    quantity: int

    def __post_init__(self) -> None:
        if self.roll_index < 0 or self.draw_index < 0 or self.quantity < 1:
            raise ValueError("掉落奖励序号或数量无效")
        object.__setattr__(self, "group_id", stable_id(self.group_id, field="loot group id"))
        object.__setattr__(self, "entry_id", stable_id(self.entry_id, field="loot entry id"))
        object.__setattr__(self, "award_id", stable_id(self.award_id, field="award id"))


@dataclass(frozen=True)
class LootDecision:
    roll_index: int
    draw_index: int
    group_id: StableId
    entry_id: StableId
    sampled: int
    scale: int
    hit: bool
    forced: bool = False

    def __post_init__(self) -> None:
        if self.roll_index < 0 or self.draw_index < 0:
            raise ValueError("掉落判定序号无效")
        if self.scale < 1 or not 1 <= self.sampled <= self.scale:
            raise ValueError("掉落判定采样值无效")
        object.__setattr__(self, "group_id", stable_id(self.group_id, field="loot group id"))
        object.__setattr__(self, "entry_id", stable_id(self.entry_id, field="loot entry id"))


@dataclass(frozen=True)
class LootRollReceipt:
    command_id: str
    actor_id: str
    table_id: StableId
    table_version: int
    awards: tuple[LootAward, ...]
    decisions: tuple[LootDecision, ...]
    empty_count: int
    pity_before: int
    pity_after: int
    logical_time: datetime
    trace_id: str


@dataclass(frozen=True)
class LootExecution:
    state: LootState
    receipt: LootRollReceipt
    events: tuple[RuleEvent, ...]


__all__ = [
    "LOOT_CHANCE_SCALE",
    "LOOT_MODIFIER_SCALE",
    "LootAward",
    "LootCatalog",
    "LootDecision",
    "LootEntry",
    "LootExecution",
    "LootGroup",
    "LootGroupMode",
    "LootPityDefinition",
    "LootRollCommand",
    "LootRollReceipt",
    "LootState",
    "LootTableDefinition",
]
