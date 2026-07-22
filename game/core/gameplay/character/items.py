"""人物成长类消耗品的类型化定义。"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

from ..ids import stable_id


CHARACTER_EXPERIENCE_ITEM_COMPONENT_ID = "item_component.use_character_experience"


@dataclass(frozen=True)
class CharacterExperienceItemComponent:
    maximum_experience: int = 1_000_000
    progression_id: str = "progression.character_level"

    def __post_init__(self) -> None:
        if isinstance(self.maximum_experience, bool) or not isinstance(
            self.maximum_experience,
            int,
        ):
            raise TypeError("CharacterExperienceItemComponent.maximum_experience 必须是整数")
        if self.maximum_experience < 1:
            raise ValueError("人物经验物品的单次经验上限必须大于 0")
        stable_id(self.progression_id, field="character progression id")


@dataclass(frozen=True)
class CharacterItemUseCommand:
    id: str
    actor_id: str
    item_asset_id: str

    def __post_init__(self) -> None:
        for field_name in ("id", "actor_id", "item_asset_id"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"CharacterItemUseCommand 缺少 {field_name}")


@dataclass(frozen=True)
class CharacterItemUseReceipt:
    transaction_id: str
    actor_id: str
    item_asset_id: str
    item_definition_id: str
    progression_id: str
    level_before: int
    level_after: int
    experience_before: int
    experience_after: int
    experience_granted: int
    replayed: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "transaction_id",
            "actor_id",
            "item_asset_id",
            "progression_id",
        ):
            if not getattr(self, field_name).strip():
                raise ValueError(f"CharacterItemUseReceipt 缺少 {field_name}")
        object.__setattr__(
            self,
            "item_definition_id",
            stable_id(self.item_definition_id, field="item definition id"),
        )
        object.__setattr__(
            self,
            "progression_id",
            stable_id(self.progression_id, field="progression id"),
        )
        integers = (
            self.level_before,
            self.level_after,
            self.experience_before,
            self.experience_after,
            self.experience_granted,
        )
        if any(isinstance(value, bool) or not isinstance(value, int) for value in integers):
            raise TypeError("CharacterItemUseReceipt 数值字段必须是整数")
        if min(integers) < 0 or self.level_before < 1 or self.level_after < 1:
            raise ValueError("CharacterItemUseReceipt 数值字段无效")
        if self.level_after < self.level_before:
            raise ValueError("人物经验物品不能降低等级")
        if not isinstance(self.replayed, bool):
            raise TypeError("CharacterItemUseReceipt.replayed 必须是布尔值")


def character_item_use_fingerprint(command: CharacterItemUseCommand) -> str:
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
    "CHARACTER_EXPERIENCE_ITEM_COMPONENT_ID",
    "CharacterExperienceItemComponent",
    "CharacterItemUseCommand",
    "CharacterItemUseReceipt",
    "character_item_use_fingerprint",
]
