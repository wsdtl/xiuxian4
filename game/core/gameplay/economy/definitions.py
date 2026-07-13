"""货币静态定义与冻结目录。"""

from __future__ import annotations

from dataclasses import dataclass

from ..ids import StableId, stable_id


@dataclass(frozen=True)
class CurrencyDefinition:
    """一种只使用整数最小单位结算的货币。"""

    id: StableId
    decimal_places: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="currency id"))
        if not 0 <= self.decimal_places <= 6:
            raise ValueError("CurrencyDefinition.decimal_places 必须在 0 到 6 之间")


class CurrencyCatalog:
    """启动期登记、运行期只读的货币目录。"""

    def __init__(self) -> None:
        self._definitions: dict[StableId, CurrencyDefinition] = {}
        self._finalized = False

    @property
    def finalized(self) -> bool:
        return self._finalized

    def register(self, definition: CurrencyDefinition) -> None:
        if self._finalized:
            raise RuntimeError("货币目录已经冻结")
        if definition.id in self._definitions:
            raise ValueError(f"重复货币定义：{definition.id}")
        self._definitions[definition.id] = definition

    def require(self, currency_id: StableId) -> CurrencyDefinition:
        currency_id = stable_id(currency_id, field="currency id")
        try:
            return self._definitions[currency_id]
        except KeyError as exc:
            raise KeyError(f"未知货币：{currency_id}") from exc

    def ids(self) -> tuple[StableId, ...]:
        return tuple(sorted(self._definitions))

    def finalize(self) -> None:
        if not self._definitions:
            raise ValueError("货币目录不能为空")
        self._finalized = True


__all__ = ["CurrencyCatalog", "CurrencyDefinition"]
