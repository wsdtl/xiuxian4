"""伙伴名册、实例和一次性秘境状态。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from game.core.gameplay import StableId, stable_id


COMPANION_ROSTER_AGGREGATE = "game.companion.roster"
COMPANION_SANCTUARY_AGGREGATE = "game.companion.sanctuary"
COMPANION_RULESET_VERSION = "ruleset.companion.v1"

APTITUDE_VITALITY = "companion.aptitude.vitality"
APTITUDE_OFFENSE = "companion.aptitude.offense"
APTITUDE_AGILITY = "companion.aptitude.agility"
APTITUDE_FOCUS = "companion.aptitude.focus"
COMPANION_APTITUDE_IDS = (
    APTITUDE_VITALITY,
    APTITUDE_OFFENSE,
    APTITUDE_AGILITY,
    APTITUDE_FOCUS,
)


class CompanionSanctuaryStatus(str, Enum):
    OPEN = "open"
    TRACKING = "tracking"
    CAPTURED = "captured"
    ABANDONED = "abandoned"
    EXPIRED = "expired"


@dataclass(frozen=True)
class CompanionInstance:
    """一只归属于玩家且不可复制的伙伴实例。"""

    id: str
    reference: str
    owner_id: str
    definition_id: StableId
    origin_skin_id: StableId
    quality_id: StableId
    level: int
    experience: int
    total_experience: int
    aptitudes: Mapping[StableId, int]
    trait_behavior_id: StableId
    captured_at: datetime
    sanctuary_id: StableId
    capture_session_id: str

    def __post_init__(self) -> None:
        if not str(self.id or "").strip() or not str(self.owner_id or "").strip():
            raise ValueError("伙伴实例缺少 id 或 owner_id")
        reference = str(self.reference or "").strip().upper()
        if not reference.startswith("C") or not reference[1:].isdigit():
            raise ValueError("伙伴实例引用必须使用 C数字")
        if self.level < 1 or self.level > 100:
            raise ValueError("伙伴等级必须位于 1 至 100")
        if self.experience < 0 or self.total_experience < self.experience:
            raise ValueError("伙伴经验无效")
        aptitudes = {
            stable_id(key, field="companion aptitude id"): int(value)
            for key, value in self.aptitudes.items()
        }
        if set(aptitudes) != set(COMPANION_APTITUDE_IDS):
            raise ValueError("伙伴实例必须完整保存四项资质")
        if any(value < 60 or value > 140 for value in aptitudes.values()):
            raise ValueError("伙伴单项资质必须位于 60 至 140")
        if self.captured_at.tzinfo is None or self.captured_at.utcoffset() is None:
            raise ValueError("伙伴捕获时间必须包含时区")
        if not str(self.capture_session_id or "").strip():
            raise ValueError("伙伴实例缺少捕获秘境会话")
        object.__setattr__(self, "reference", reference)
        object.__setattr__(self, "definition_id", stable_id(self.definition_id))
        object.__setattr__(self, "origin_skin_id", stable_id(self.origin_skin_id))
        object.__setattr__(self, "quality_id", stable_id(self.quality_id))
        object.__setattr__(
            self,
            "trait_behavior_id",
            stable_id(self.trait_behavior_id),
        )
        object.__setattr__(self, "sanctuary_id", stable_id(self.sanctuary_id))
        object.__setattr__(self, "aptitudes", MappingProxyType(aptitudes))


@dataclass(frozen=True)
class CompanionTrace:
    """开启秘境时已经完全固定、展示时只揭露部分信息的踪迹。"""

    index: int
    definition_id: StableId
    quality_id: StableId
    level: int
    aptitudes: Mapping[StableId, int]
    trait_behavior_id: StableId
    battle_seed: str

    def __post_init__(self) -> None:
        if self.index < 1 or self.level < 1 or self.level > 100:
            raise ValueError("伙伴踪迹编号或等级无效")
        aptitudes = {
            stable_id(key, field="companion aptitude id"): int(value)
            for key, value in self.aptitudes.items()
        }
        if set(aptitudes) != set(COMPANION_APTITUDE_IDS):
            raise ValueError("伙伴踪迹必须完整保存四项资质")
        if any(value < 60 or value > 140 for value in aptitudes.values()):
            raise ValueError("伙伴踪迹资质必须位于 60 至 140")
        if not str(self.battle_seed or "").strip():
            raise ValueError("伙伴踪迹缺少固定战斗种子")
        object.__setattr__(self, "definition_id", stable_id(self.definition_id))
        object.__setattr__(self, "quality_id", stable_id(self.quality_id))
        object.__setattr__(self, "trait_behavior_id", stable_id(self.trait_behavior_id))
        object.__setattr__(self, "aptitudes", MappingProxyType(aptitudes))


@dataclass(frozen=True)
class CompanionRosterState:
    """角色伙伴实例、历史图鉴和六套配装独占引用。"""

    character_id: str
    instances: Mapping[str, CompanionInstance] = field(default_factory=dict)
    bindings: Mapping[StableId, str] = field(default_factory=dict)
    captured_definition_ids: frozenset[StableId] = frozenset()
    next_sequence: int = 1
    revision: int = 0

    def __post_init__(self) -> None:
        character_id = str(self.character_id or "").strip()
        if not character_id:
            raise ValueError("伙伴名册缺少 character_id")
        if self.next_sequence < 1 or self.revision < 0:
            raise ValueError("伙伴名册序号或 revision 无效")
        instances = dict(self.instances)
        references = set()
        for key, instance in instances.items():
            if key != instance.id or instance.owner_id != character_id:
                raise ValueError("伙伴名册实例键或归属不一致")
            if instance.reference in references:
                raise ValueError("伙伴名册存在重复玩家引用")
            references.add(instance.reference)
        bindings = {
            stable_id(key, field="companion loadout preset id"): str(value)
            for key, value in self.bindings.items()
        }
        if any(instance_id not in instances for instance_id in bindings.values()):
            raise ValueError("伙伴配装引用了不存在的实例")
        if len(bindings.values()) != len(set(bindings.values())):
            raise ValueError("同一只伙伴不能同时属于多套配装")
        captured = frozenset(
            stable_id(value, field="captured companion definition id")
            for value in self.captured_definition_ids
        )
        object.__setattr__(self, "character_id", character_id)
        object.__setattr__(self, "instances", MappingProxyType(instances))
        object.__setattr__(self, "bindings", MappingProxyType(bindings))
        object.__setattr__(self, "captured_definition_ids", captured)

    def by_reference(self, reference: object) -> CompanionInstance | None:
        token = str(reference or "").strip().upper()
        return next(
            (value for value in self.instances.values() if value.reference == token),
            None,
        )

    def companion_for_preset(self, preset_id: StableId | None) -> CompanionInstance | None:
        if preset_id is None:
            return None
        instance_id = self.bindings.get(stable_id(preset_id))
        return self.instances.get(instance_id) if instance_id is not None else None

    def preset_for_companion(self, companion_id: str) -> StableId | None:
        return next(
            (preset_id for preset_id, value in self.bindings.items() if value == companion_id),
            None,
        )


@dataclass(frozen=True)
class CompanionSanctuaryState:
    """一个角色当前或最近一次伙伴秘境。"""

    character_id: str
    session_id: str
    sanctuary_id: StableId
    world_skin_id: StableId
    opened_at: datetime
    expires_at: datetime
    traces: tuple[CompanionTrace, ...]
    status: CompanionSanctuaryStatus = CompanionSanctuaryStatus.OPEN
    selected_trace_index: int | None = None
    attempt_count: int = 0
    captured_companion_id: str | None = None
    revision: int = 0

    def __post_init__(self) -> None:
        if not str(self.character_id or "").strip() or not str(self.session_id or "").strip():
            raise ValueError("伙伴秘境缺少角色或会话 id")
        if self.opened_at.tzinfo is None or self.opened_at.utcoffset() is None:
            raise ValueError("伙伴秘境时间必须包含时区")
        if self.expires_at <= self.opened_at:
            raise ValueError("伙伴秘境结束时间必须晚于开启时间")
        indices = tuple(value.index for value in self.traces)
        if not indices or len(indices) != len(set(indices)):
            raise ValueError("伙伴秘境踪迹不能为空或重复")
        status = CompanionSanctuaryStatus(self.status)
        if status is CompanionSanctuaryStatus.OPEN and self.selected_trace_index is not None:
            raise ValueError("未追踪秘境不能保存选中踪迹")
        if status is CompanionSanctuaryStatus.TRACKING and self.selected_trace_index not in indices:
            raise ValueError("追踪中的秘境必须保存有效目标")
        if status is CompanionSanctuaryStatus.CAPTURED and not self.captured_companion_id:
            raise ValueError("已捕获秘境必须保存伙伴实例 id")
        if self.attempt_count < 0 or self.revision < 0:
            raise ValueError("伙伴秘境尝试次数或 revision 无效")
        object.__setattr__(self, "sanctuary_id", stable_id(self.sanctuary_id))
        object.__setattr__(self, "world_skin_id", stable_id(self.world_skin_id))
        object.__setattr__(self, "status", status)

    @property
    def active(self) -> bool:
        return self.status in {
            CompanionSanctuaryStatus.OPEN,
            CompanionSanctuaryStatus.TRACKING,
        }

    @property
    def reserves_capacity(self) -> bool:
        return self.active

    def selected_trace(self) -> CompanionTrace | None:
        return next(
            (
                value
                for value in self.traces
                if value.index == self.selected_trace_index
            ),
            None,
        )


__all__ = [name for name in globals() if not name.startswith("_")]
