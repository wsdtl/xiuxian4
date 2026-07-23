"""套装图纸使用业务的稳定结果。"""

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class EquipmentBlueprintReceipt:
    transaction_id: str
    actor_id: str
    blueprint_asset_id: str
    blueprint_definition_id: str
    equipment_asset_id: str
    equipment_definition_id: str
    equipment_item_definition_id: str
    set_id: str
    quality_id: str
    replayed: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "transaction_id",
            "actor_id",
            "blueprint_asset_id",
            "blueprint_definition_id",
            "equipment_asset_id",
            "equipment_definition_id",
            "equipment_item_definition_id",
            "set_id",
            "quality_id",
        ):
            if not getattr(self, field_name).strip():
                raise ValueError(f"EquipmentBlueprintReceipt 缺少 {field_name}")

    def as_replayed(self) -> "EquipmentBlueprintReceipt":
        return replace(self, replayed=True)


@dataclass(frozen=True)
class EquipmentBlueprintResult:
    status: str
    receipt: EquipmentBlueprintReceipt | None = None
    failure_message: str = ""


__all__ = ["EquipmentBlueprintReceipt", "EquipmentBlueprintResult"]
