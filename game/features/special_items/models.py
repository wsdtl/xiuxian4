"""非武器目标特殊物品的稳定请求与回执。"""

from dataclasses import dataclass
from hashlib import sha256
import json

from game.core.gameplay import StableId, stable_id


@dataclass(frozen=True)
class SpecialItemUseCommand:
    id: str
    actor_id: str
    item_asset_id: str

    def __post_init__(self) -> None:
        for field_name in ("id", "actor_id", "item_asset_id"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"SpecialItemUseCommand 缺少 {field_name}")


@dataclass(frozen=True)
class SpecialItemUseReceipt:
    transaction_id: str
    actor_id: str
    item_asset_id: str
    item_definition_id: StableId
    effect_kind: StableId
    value_before: int
    value_after: int
    replayed: bool = False

    def __post_init__(self) -> None:
        for field_name in ("transaction_id", "actor_id", "item_asset_id"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"SpecialItemUseReceipt 缺少 {field_name}")
        object.__setattr__(
            self,
            "item_definition_id",
            stable_id(self.item_definition_id, field="item definition id"),
        )
        object.__setattr__(
            self,
            "effect_kind",
            stable_id(self.effect_kind, field="special item effect kind"),
        )
        for field_name in ("value_before", "value_after"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"SpecialItemUseReceipt.{field_name} 必须是整数")
        if self.value_after < self.value_before:
            raise ValueError("特殊物品使用回执不能降低目标值")
        if not isinstance(self.replayed, bool):
            raise TypeError("SpecialItemUseReceipt.replayed 必须是布尔值")


def special_item_use_fingerprint(command: SpecialItemUseCommand) -> str:
    payload = json.dumps(
        {
            "id": command.id,
            "actor_id": command.actor_id,
            "item_asset_id": command.item_asset_id,
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(payload.encode("utf-8")).hexdigest()


__all__ = [
    "SpecialItemUseCommand",
    "SpecialItemUseReceipt",
    "special_item_use_fingerprint",
]
