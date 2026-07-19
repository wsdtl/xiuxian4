"""次元灾厄事件、挑战回执和不可复制的历史状态。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from game.core.gameplay import StableId, stable_id


DIMENSIONAL_DISASTER_AGGREGATE = "snapshot.dimensional_disaster"
DIMENSIONAL_DISASTER_RULESET_VERSION = "rules.dimensional_disaster.v1"


class DimensionalDisasterStatus(str, Enum):
    OPEN = "open"
    SETTLING = "settling"
    CLOSED = "closed"


class DimensionalDisasterOutcome(str, Enum):
    NONE = "none"
    DEFEATED = "defeated"
    ESCAPED = "escaped"


@dataclass(frozen=True)
class DisasterNarrativeSnapshot:
    name: str
    title: str
    scene: str
    story: str
    farewell: str
    feather_text: str
    source_note: str

    def __post_init__(self) -> None:
        for field_name in (
            "name",
            "title",
            "scene",
            "story",
            "farewell",
            "feather_text",
            "source_note",
        ):
            value = str(getattr(self, field_name) or "").strip()
            if not value:
                raise ValueError(f"灾厄叙事快照缺少 {field_name}")
            object.__setattr__(self, field_name, value)


@dataclass(frozen=True)
class DisasterCombatSnapshot:
    enemy_definition_id: StableId
    level: int
    rank_id: StableId
    behavior_ids: tuple[StableId, ...]
    generation_seed: str
    content_version: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "enemy_definition_id",
            stable_id(self.enemy_definition_id, field="enemy id"),
        )
        object.__setattr__(self, "rank_id", stable_id(self.rank_id, field="enemy rank id"))
        object.__setattr__(
            self,
            "behavior_ids",
            tuple(stable_id(value, field="enemy behavior id") for value in self.behavior_ids),
        )
        if self.level < 1 or not self.generation_seed.strip() or not self.content_version.strip():
            raise ValueError("灾厄战斗快照无效")


@dataclass(frozen=True)
class DisasterChallengeReceipt:
    operation_id: str
    character_id: str
    event_id: str
    business_day: str
    damage: int
    shared_health_before: int
    shared_health_after: int
    player_health_after: float
    player_spirit_after: float
    attempts_today: int
    turns: int
    player_victory: bool
    resolved_at: datetime
    replayed: bool = False

    def __post_init__(self) -> None:
        for field_name in ("operation_id", "character_id", "event_id", "business_day"):
            if not str(getattr(self, field_name) or "").strip():
                raise ValueError(f"灾厄挑战回执缺少 {field_name}")
        if min(
            self.damage,
            self.shared_health_before,
            self.shared_health_after,
            self.attempts_today,
            self.turns,
        ) < 0:
            raise ValueError("灾厄挑战回执包含负数")
        if self.shared_health_after > self.shared_health_before:
            raise ValueError("灾厄挑战不能恢复共享血量")
        _aware(self.resolved_at, "DisasterChallengeReceipt.resolved_at")

    def as_replay(self) -> "DisasterChallengeReceipt":
        return DisasterChallengeReceipt(
            self.operation_id,
            self.character_id,
            self.event_id,
            self.business_day,
            self.damage,
            self.shared_health_before,
            self.shared_health_after,
            self.player_health_after,
            self.player_spirit_after,
            self.attempts_today,
            self.turns,
            self.player_victory,
            self.resolved_at,
            True,
        )


@dataclass(frozen=True)
class DimensionalDisasterState:
    event_id: str
    window_id: str
    definition_id: StableId
    source_skin_id: StableId
    narrative: DisasterNarrativeSnapshot
    combat: DisasterCombatSnapshot
    opens_at: datetime
    closes_at: datetime
    maximum_health: int
    current_health: int
    attempts_by_day: Mapping[str, Mapping[str, int]] = field(default_factory=dict)
    challenge_receipts: Mapping[str, DisasterChallengeReceipt] = field(default_factory=dict)
    outcome: DimensionalDisasterOutcome = DimensionalDisasterOutcome.NONE
    status: DimensionalDisasterStatus = DimensionalDisasterStatus.OPEN
    defeated_at: datetime | None = None
    feather_owner_id: str | None = None
    feather_asset_id: str | None = None
    rewarded_character_ids: frozenset[str] = frozenset()
    revision: int = 0

    def __post_init__(self) -> None:
        if not self.event_id.strip() or not self.window_id.strip():
            raise ValueError("次元灾厄事件缺少身份")
        object.__setattr__(self, "definition_id", stable_id(self.definition_id, field="disaster id"))
        object.__setattr__(
            self,
            "source_skin_id",
            stable_id(self.source_skin_id, field="source skin id"),
        )
        _aware(self.opens_at, "DimensionalDisasterState.opens_at")
        _aware(self.closes_at, "DimensionalDisasterState.closes_at")
        if self.closes_at <= self.opens_at:
            raise ValueError("次元灾厄关闭时间必须晚于开放时间")
        if self.maximum_health < 1 or not 0 <= self.current_health <= self.maximum_health:
            raise ValueError("次元灾厄共享血量无效")
        attempts = {
            str(character_id): MappingProxyType(
                {str(day): int(count) for day, count in days.items()}
            )
            for character_id, days in self.attempts_by_day.items()
        }
        if any(count < 0 for days in attempts.values() for count in days.values()):
            raise ValueError("次元灾厄挑战次数不能小于 0")
        receipts = dict(self.challenge_receipts)
        if any(key != value.operation_id for key, value in receipts.items()):
            raise ValueError("次元灾厄挑战回执映射键不一致")
        outcome = DimensionalDisasterOutcome(self.outcome)
        status = DimensionalDisasterStatus(self.status)
        if outcome is DimensionalDisasterOutcome.DEFEATED and self.current_health != 0:
            raise ValueError("已击破灾厄的共享血量必须为零")
        if self.defeated_at is not None:
            _aware(self.defeated_at, "DimensionalDisasterState.defeated_at")
        if bool(self.feather_owner_id) != bool(self.feather_asset_id):
            raise ValueError("铭刻之羽归属与资产 ID 必须同时存在")
        if self.revision < 0:
            raise ValueError("次元灾厄 revision 不能小于 0")
        object.__setattr__(self, "attempts_by_day", MappingProxyType(attempts))
        object.__setattr__(self, "challenge_receipts", MappingProxyType(receipts))
        object.__setattr__(self, "rewarded_character_ids", frozenset(self.rewarded_character_ids))
        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "status", status)

    def attempts_today(self, character_id: str, business_day: str) -> int:
        return int(self.attempts_by_day.get(character_id, {}).get(business_day, 0))


def _aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} 必须包含时区")


__all__ = [
    "DIMENSIONAL_DISASTER_AGGREGATE",
    "DIMENSIONAL_DISASTER_RULESET_VERSION",
    "DimensionalDisasterOutcome",
    "DimensionalDisasterState",
    "DimensionalDisasterStatus",
    "DisasterChallengeReceipt",
    "DisasterCombatSnapshot",
    "DisasterNarrativeSnapshot",
]
