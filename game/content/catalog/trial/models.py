"""构筑试炼模式与稳定目标的内容模型。"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from game.core.gameplay import StableId, stable_id


@dataclass(frozen=True)
class BuildTrialModeDefinition:
    """一类可重复比较的无收益构筑试炼。"""

    id: StableId
    name: str
    summary: str
    target_definition_id: StableId
    target_name: str
    target_count: int
    maximum_rounds: int
    maximum_turns: int
    random_seed: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="build trial mode id"))
        object.__setattr__(
            self,
            "target_definition_id",
            stable_id(self.target_definition_id, field="build trial target id"),
        )
        for field_name in ("name", "summary", "target_name", "random_seed"):
            value = str(getattr(self, field_name) or "").strip()
            if not value:
                raise ValueError(f"构筑试炼缺少 {field_name}")
            object.__setattr__(self, field_name, value)
        if self.target_count < 1:
            raise ValueError("构筑试炼目标数量必须大于 0")
        if self.maximum_rounds < 1 or self.maximum_turns < self.maximum_rounds:
            raise ValueError("构筑试炼回合或行动上限无效")


class BuildTrialCatalog:
    """按稳定 ID、中文名称和短别名解析试炼模式。"""

    def __init__(
        self,
        definitions: tuple[BuildTrialModeDefinition, ...],
        aliases: dict[str, StableId],
    ) -> None:
        values = tuple(definitions)
        by_id = {value.id: value for value in values}
        if not values or len(by_id) != len(values):
            raise ValueError("构筑试炼模式不能为空或重复")
        normalized_aliases = {
            _token(alias): stable_id(mode_id, field="build trial mode id")
            for alias, mode_id in aliases.items()
        }
        normalized_aliases.update({_token(value.name): value.id for value in values})
        normalized_aliases.update({_token(value.id): value.id for value in values})
        unknown = set(normalized_aliases.values()) - set(by_id)
        if unknown:
            raise KeyError("构筑试炼别名引用未知模式")
        self._definitions = values
        self._by_id = MappingProxyType(by_id)
        self._aliases = MappingProxyType(normalized_aliases)

    def definitions(self) -> tuple[BuildTrialModeDefinition, ...]:
        return self._definitions

    def require(self, mode_id: object) -> BuildTrialModeDefinition:
        return self._by_id[stable_id(mode_id, field="build trial mode id")]

    def resolve(self, value: object) -> BuildTrialModeDefinition | None:
        mode_id = self._aliases.get(_token(value))
        return self._by_id.get(mode_id) if mode_id is not None else None


def _token(value: object) -> str:
    return " ".join(str(value or "").strip().casefold().split())


__all__ = ["BuildTrialCatalog", "BuildTrialModeDefinition"]
