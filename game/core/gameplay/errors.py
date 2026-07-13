"""规则失败码与统一执行结果。"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Generic, Mapping, TypeVar

from .ids import StableId, stable_id


ResultT = TypeVar("ResultT")


@dataclass(frozen=True)
class RuleFailure:
    """可以被 QQ、网页和测试稳定识别的规则失败。"""

    code: StableId
    message: str
    details: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", stable_id(self.code, field="failure code"))
        if not self.message.strip():
            raise ValueError("RuleFailure 缺少内部说明")
        object.__setattr__(self, "message", self.message.strip())
        object.__setattr__(self, "details", MappingProxyType(dict(self.details)))


class RuleViolation(Exception):
    """规则内核内部用于中断原子执行的预期失败。"""

    def __init__(
        self,
        code: StableId,
        message: str,
        details: Mapping[str, object] | None = None,
    ) -> None:
        self.failure = RuleFailure(code, message, details or {})
        super().__init__(f"{self.failure.code}: {self.failure.message}")


@dataclass(frozen=True)
class RuleOutcome(Generic[ResultT]):
    """规则执行的成功值或失败事实，两者必须且只能存在一个。"""

    value: ResultT | None = None
    failure: RuleFailure | None = None

    def __post_init__(self) -> None:
        if (self.value is None) == (self.failure is None):
            raise ValueError("RuleOutcome 必须且只能包含 value 或 failure")

    @property
    def ok(self) -> bool:
        return self.failure is None

    @classmethod
    def success(cls, value: ResultT) -> "RuleOutcome[ResultT]":
        return cls(value=value)

    @classmethod
    def failed(cls, failure: RuleFailure) -> "RuleOutcome[ResultT]":
        return cls(failure=failure)

    def unwrap(self) -> ResultT:
        if self.failure:
            raise RuleViolation(
                self.failure.code,
                self.failure.message,
                self.failure.details,
            )
        assert self.value is not None
        return self.value


__all__ = ["RuleFailure", "RuleOutcome", "RuleViolation"]
