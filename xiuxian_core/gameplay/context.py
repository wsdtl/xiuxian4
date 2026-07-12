"""规则版本、场景、逻辑时间和确定性随机源。"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Protocol, Sequence, TypeVar

from .ids import StableId, stable_id
from .phases import ExecutionPhase
from .tags import EMPTY_TAGS, TagSet


ChoiceT = TypeVar("ChoiceT")


class RandomSource(Protocol):
    """规则内核允许使用的随机源。"""

    def random(self) -> float: ...

    def randint(self, minimum: int, maximum: int) -> int: ...

    def choice(self, values: Sequence[ChoiceT]) -> ChoiceT: ...

    def checkpoint(self) -> object: ...

    def restore(self, checkpoint: object) -> None: ...


class SeededRandomSource:
    """由固定种子驱动的可重放随机源。"""

    def __init__(self, seed: int | str) -> None:
        self.seed = seed
        self._random = random.Random(seed)

    def random(self) -> float:
        return self._random.random()

    def randint(self, minimum: int, maximum: int) -> int:
        return self._random.randint(minimum, maximum)

    def choice(self, values: Sequence[ChoiceT]) -> ChoiceT:
        if not values:
            raise ValueError("随机选择的候选集合不能为空")
        return self._random.choice(values)

    def checkpoint(self) -> object:
        return self._random.getstate()

    def restore(self, checkpoint: object) -> None:
        self._random.setstate(checkpoint)


@dataclass(frozen=True)
class Ruleset:
    """当前执行场景允许共享的规则标签和保护边界。"""

    id: StableId
    tags: TagSet = EMPTY_TAGS
    max_trigger_depth: int = 16

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="ruleset id"))
        if self.max_trigger_depth < 1:
            raise ValueError("Ruleset.max_trigger_depth 必须大于 0")


@dataclass(frozen=True)
class RuleContext:
    """一次完整规则执行必须显式携带的上下文。"""

    trace_id: str
    rule_version: StableId
    ruleset: Ruleset
    logical_time: datetime
    random: RandomSource
    tags: TagSet = EMPTY_TAGS
    phase: ExecutionPhase = ExecutionPhase.PREPARE
    trigger_depth: int = 0

    def __post_init__(self) -> None:
        if not self.trace_id.strip():
            raise ValueError("RuleContext 缺少 trace_id")
        object.__setattr__(self, "rule_version", stable_id(self.rule_version, field="rule version"))
        if self.logical_time.tzinfo is None or self.logical_time.utcoffset() is None:
            raise ValueError("RuleContext.logical_time 必须包含时区")
        if self.trigger_depth < 0:
            raise ValueError("RuleContext.trigger_depth 不能小于 0")

    @property
    def effective_tags(self) -> TagSet:
        return self.ruleset.tags.merged(self.tags)

    def at_phase(self, phase: ExecutionPhase) -> "RuleContext":
        return replace(self, phase=phase)

    def with_tags(self, tags: TagSet) -> "RuleContext":
        return replace(self, tags=self.tags.merged(tags))

    def next_trigger(self) -> "RuleContext":
        depth = self.trigger_depth + 1
        if depth > self.ruleset.max_trigger_depth:
            from .errors import RuleViolation

            raise RuleViolation(
                "rule.recursion_limit",
                "触发链超过 Ruleset 允许的最大深度",
                {
                    "depth": depth,
                    "maximum": self.ruleset.max_trigger_depth,
                    "ruleset_id": self.ruleset.id,
                },
            )
        return replace(self, trigger_depth=depth)

    def at_trigger_depth(self, depth: int) -> "RuleContext":
        if depth < 0 or depth > self.ruleset.max_trigger_depth:
            from .errors import RuleViolation

            raise RuleViolation(
                "rule.recursion_limit",
                "触发链超过 Ruleset 允许的最大深度",
                {"depth": depth, "maximum": self.ruleset.max_trigger_depth},
            )
        return replace(self, trigger_depth=depth)


__all__ = ["RandomSource", "RuleContext", "Ruleset", "SeededRandomSource"]
