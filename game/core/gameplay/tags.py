"""具有父子关系的规则标签。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .ids import StableId, stable_id


@dataclass(frozen=True, order=True)
class Tag:
    """描述实体性质的稳定标签。

    ``damage.physical.bleed`` 同时满足 ``damage.physical`` 查询。这样新增更
    细的标签时，已有规则不需要逐个认识所有子类。
    """

    value: StableId

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", stable_id(self.value, field="tag"))

    def matches(self, query: "Tag") -> bool:
        """当前标签是否等于查询标签或属于它的子级。"""

        return self.value == query.value or self.value.startswith(f"{query.value}.")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class TagSet:
    """不可变标签集合，统一处理条件匹配。"""

    values: frozenset[Tag] = frozenset()

    @classmethod
    def of(cls, *values: str | Tag) -> "TagSet":
        return cls(frozenset(value if isinstance(value, Tag) else Tag(value) for value in values))

    @classmethod
    def from_iterable(cls, values: Iterable[str | Tag]) -> "TagSet":
        return cls(frozenset(value if isinstance(value, Tag) else Tag(value) for value in values))

    def has(self, query: str | Tag) -> bool:
        expected = query if isinstance(query, Tag) else Tag(query)
        return any(value.matches(expected) for value in self.values)

    def allows(self, *, required: "TagSet" = None, blocked: "TagSet" = None) -> bool:
        """检查必需标签全部存在，并且排除标签全部不存在。"""

        required = required or EMPTY_TAGS
        blocked = blocked or EMPTY_TAGS
        return all(self.has(tag) for tag in required.values) and not any(
            self.has(tag) for tag in blocked.values
        )

    def merged(self, *others: "TagSet") -> "TagSet":
        values = set(self.values)
        for other in others:
            values.update(other.values)
        return TagSet(frozenset(values))

    def without(self, other: "TagSet") -> "TagSet":
        return TagSet(self.values - other.values)

    def strings(self) -> tuple[str, ...]:
        return tuple(sorted(str(value) for value in self.values))


EMPTY_TAGS = TagSet()


__all__ = ["EMPTY_TAGS", "Tag", "TagSet"]
