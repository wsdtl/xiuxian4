"""可由后续玩法包扩展的物品组件类型注册表。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

from ..ids import StableId, stable_id


ComponentT = TypeVar("ComponentT")
ComponentValidator = Callable[[object], None]


@dataclass(frozen=True)
class ItemComponentType(Generic[ComponentT]):
    """一个物品组件槽位允许保存的数据类型。"""

    id: StableId
    value_type: type[ComponentT]
    validator: Callable[[ComponentT], None] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="item component id"))


class ItemComponentRegistry:
    """启动期登记组件类型，运行期只负责严格校验。"""

    def __init__(self) -> None:
        self._types: dict[StableId, ItemComponentType[object]] = {}
        self._frozen = False

    def register(self, definition: ItemComponentType[object]) -> ItemComponentType[object]:
        if self._frozen:
            raise RuntimeError("物品组件注册表已经冻结")
        if definition.id in self._types:
            raise ValueError(f"物品组件类型重复：{definition.id}")
        self._types[definition.id] = definition
        return definition

    def validate(self, component_id: StableId, value: object) -> None:
        key = stable_id(component_id, field="item component id")
        try:
            definition = self._types[key]
        except KeyError as exc:
            raise KeyError(f"未知物品组件类型：{key}") from exc
        if not isinstance(value, definition.value_type):
            raise TypeError(
                f"物品组件 {key} 必须是 {definition.value_type.__name__}，"
                f"当前是 {type(value).__name__}"
            )
        if definition.validator is not None:
            definition.validator(value)

    def freeze(self) -> None:
        self._frozen = True

    @property
    def frozen(self) -> bool:
        return self._frozen

    def ids(self) -> tuple[StableId, ...]:
        return tuple(sorted(self._types))


__all__ = ["ItemComponentRegistry", "ItemComponentType"]
