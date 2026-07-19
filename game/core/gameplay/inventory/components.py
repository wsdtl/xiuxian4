"""可由后续玩法包扩展的物品组件类型注册表。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

from ..ids import StableId, stable_id


ComponentT = TypeVar("ComponentT")
ComponentValidator = Callable[[object], None]
ITEM_STORAGE_COMPONENT_ID = "item_component.storage"
ITEM_CONTAINER_CAPACITY_COMPONENT_ID = "item_component.use_container_capacity"


@dataclass(frozen=True)
class ItemStorageComponent:
    """物品进入空间受限容器时，每一件占用的整数空间。"""

    unit_space: int

    def __post_init__(self) -> None:
        if not isinstance(self.unit_space, int) or isinstance(self.unit_space, bool):
            raise TypeError("ItemStorageComponent.unit_space 必须是整数")
        if self.unit_space < 1:
            raise ValueError("ItemStorageComponent.unit_space 必须大于 0")


@dataclass(frozen=True)
class ContainerCapacityItemComponent:
    """一次使用对指定容器增加的容量及其绝对上限。"""

    container_kind: StableId
    amount: int
    maximum_space: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "container_kind",
            stable_id(self.container_kind, field="container kind"),
        )
        for field_name in ("amount", "maximum_space"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"ContainerCapacityItemComponent.{field_name} 必须是整数")
        if self.amount < 1 or self.maximum_space < self.amount:
            raise ValueError("容器扩容数量和绝对上限无效")


@dataclass(frozen=True)
class ItemComponentType(Generic[ComponentT]):
    """一个物品组件槽位允许保存的数据类型。"""

    id: StableId
    value_type: type[ComponentT]
    validator: Callable[[ComponentT], None] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="item component id"))


ITEM_CONTAINER_CAPACITY_COMPONENT_TYPE = ItemComponentType(
    ITEM_CONTAINER_CAPACITY_COMPONENT_ID,
    ContainerCapacityItemComponent,
)


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


def register_item_storage_component(registry: ItemComponentRegistry) -> None:
    """注册公共空间占用组件；重复注册仍由注册表拒绝。"""

    registry.register(
        ItemComponentType(ITEM_STORAGE_COMPONENT_ID, ItemStorageComponent)
    )


__all__ = [
    "ITEM_STORAGE_COMPONENT_ID",
    "ITEM_CONTAINER_CAPACITY_COMPONENT_ID",
    "ITEM_CONTAINER_CAPACITY_COMPONENT_TYPE",
    "ContainerCapacityItemComponent",
    "ItemComponentRegistry",
    "ItemComponentType",
    "ItemStorageComponent",
    "register_item_storage_component",
]
