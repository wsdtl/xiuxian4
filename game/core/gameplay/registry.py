"""内容定义注册表。"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from .ids import StableId, stable_id
from .tags import EMPTY_TAGS, TagSet


class IdentifiedDefinition(Protocol):
    """所有可注册定义都必须拥有稳定 id。"""

    id: StableId


DefinitionT = TypeVar("DefinitionT", bound=IdentifiedDefinition)


class DefinitionRegistry(Generic[DefinitionT]):
    """可在启动阶段登记、运行阶段只读的定义注册表。"""

    def __init__(self, kind: str) -> None:
        self.kind = str(kind).strip() or "内容"
        self._items: dict[StableId, DefinitionT] = {}
        self._frozen = False

    def register(self, definition: DefinitionT) -> DefinitionT:
        if self._frozen:
            raise RuntimeError(f"{self.kind}注册表已经冻结，不能在运行期增加定义")
        key = stable_id(definition.id, field=f"{self.kind} id")
        if key in self._items:
            raise ValueError(f"{self.kind}定义重复：{key}")
        self._items[key] = definition
        return definition

    def require(self, definition_id: StableId) -> DefinitionT:
        key = stable_id(definition_id, field=f"{self.kind} id")
        try:
            return self._items[key]
        except KeyError as exc:
            raise KeyError(f"未知{self.kind}定义：{key}") from exc

    def contains(self, definition_id: StableId) -> bool:
        return str(definition_id) in self._items

    def freeze(self) -> None:
        """冻结注册表，防止运行过程中规则集合悄悄变化。"""

        self._frozen = True

    @property
    def frozen(self) -> bool:
        return self._frozen

    def ids(self) -> tuple[StableId, ...]:
        return tuple(sorted(self._items))

    def __iter__(self) -> Iterator[DefinitionT]:
        return iter(self._items.values())

    def __len__(self) -> int:
        return len(self._items)


@dataclass(frozen=True)
class ContentDefinition:
    """只描述内容身份和规则性质，不保存玩家可见名称。"""

    id: StableId
    kind: StableId
    tags: TagSet = EMPTY_TAGS

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="content id"))
        object.__setattr__(self, "kind", stable_id(self.kind, field="content kind"))


__all__ = ["ContentDefinition", "DefinitionRegistry", "IdentifiedDefinition"]
