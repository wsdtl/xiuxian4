"""物品静态定义与启动期目录。"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping, TypeVar

from ..ids import StableId, stable_id
from ..registry import DefinitionRegistry
from ..tags import EMPTY_TAGS, TagSet
from .components import ItemComponentRegistry
from .models import ItemAssetKind


ComponentT = TypeVar("ComponentT")


@dataclass(frozen=True)
class ItemDefinition:
    """物品的规则身份；名称、图标和描述由世界皮肤提供。"""

    id: StableId
    asset_kind: ItemAssetKind
    tags: TagSet = EMPTY_TAGS
    stack_limit: int | None = None
    components: Mapping[StableId, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="item id"))
        object.__setattr__(self, "asset_kind", ItemAssetKind(self.asset_kind))
        if self.asset_kind is ItemAssetKind.INSTANCE and self.stack_limit is not None:
            raise ValueError("独立实例物品不能设置 stack_limit")
        if self.stack_limit is not None and self.stack_limit < 1:
            raise ValueError("ItemDefinition.stack_limit 必须大于 0")
        components = {
            stable_id(key, field="item component id"): value
            for key, value in self.components.items()
        }
        object.__setattr__(self, "components", MappingProxyType(components))

    def component(self, component_id: StableId, expected_type: type[ComponentT]) -> ComponentT:
        key = stable_id(component_id, field="item component id")
        try:
            value = self.components[key]
        except KeyError as exc:
            raise KeyError(f"物品 {self.id} 不包含组件：{key}") from exc
        if not isinstance(value, expected_type):
            raise TypeError(f"物品 {self.id} 的组件 {key} 类型不正确")
        return value


class ItemCatalog:
    """把通用定义注册表与物品组件校验组合为完整目录。"""

    def __init__(self, components: ItemComponentRegistry | None = None) -> None:
        self.components = components or ItemComponentRegistry()
        self.definitions = DefinitionRegistry[ItemDefinition]("Item")
        self._finalized = False

    def register(self, definition: ItemDefinition) -> ItemDefinition:
        if self._finalized:
            raise RuntimeError("物品目录已经完成组装")
        for component_id, value in definition.components.items():
            self.components.validate(component_id, value)
        return self.definitions.register(definition)

    def require(self, definition_id: StableId) -> ItemDefinition:
        return self.definitions.require(definition_id)

    def finalize(self) -> None:
        self.components.freeze()
        self.definitions.freeze()
        self._finalized = True

    @property
    def finalized(self) -> bool:
        return self._finalized


__all__ = ["ItemCatalog", "ItemDefinition"]
