"""归航兑换业务结果。"""

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class CovenantExchangeReceipt:
    transaction_id: str
    actor_id: str
    set_id: str
    material_definition_id: str
    material_quantity: int
    blueprint_definition_id: str
    blueprint_asset_id: str
    replayed: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "transaction_id",
            "actor_id",
            "set_id",
            "material_definition_id",
            "blueprint_definition_id",
            "blueprint_asset_id",
        ):
            if not getattr(self, field_name).strip():
                raise ValueError(f"CovenantExchangeReceipt 缺少 {field_name}")
        if self.material_quantity < 1:
            raise ValueError("归航兑换材料数量必须大于 0")

    def as_replayed(self) -> "CovenantExchangeReceipt":
        return replace(self, replayed=True)


@dataclass(frozen=True)
class CovenantExchangeResult:
    status: str
    receipt: CovenantExchangeReceipt | None = None
    failure_message: str = ""


@dataclass(frozen=True)
class CovenantExchangeHistory:
    owner_id: str
    records: tuple[CovenantExchangeReceipt, ...] = ()
    revision: int = 0

    def __post_init__(self) -> None:
        if not self.owner_id.strip():
            raise ValueError("归航兑换记录缺少所有者")
        if self.revision < 0:
            raise ValueError("归航兑换记录 revision 不能小于 0")
        if len(self.records) > 20:
            raise ValueError("归航兑换记录最多保留 20 条")


__all__ = [
    "CovenantExchangeHistory",
    "CovenantExchangeReceipt",
    "CovenantExchangeResult",
]
