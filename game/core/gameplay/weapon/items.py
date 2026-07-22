"""把武器成长类消耗品声明为可注册的类型化组件。"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

from ..inventory import ItemComponentType
from ..ids import stable_id
from .models import WEAPON_ABSOLUTE_MAXIMUM_LEVEL


WEAPON_MAXIMUM_LEVEL_ITEM_COMPONENT_ID = "item_component.use_weapon_maximum_level"
WEAPON_EXPERIENCE_ITEM_COMPONENT_ID = "item_component.use_weapon_experience"


@dataclass(frozen=True)
class WeaponMaximumLevelItemComponent:
    delta: int = 1
    cap: int = WEAPON_ABSOLUTE_MAXIMUM_LEVEL

    def __post_init__(self) -> None:
        if isinstance(self.delta, bool) or not isinstance(self.delta, int):
            raise TypeError("WeaponMaximumLevelItemComponent.delta 必须是整数")
        if isinstance(self.cap, bool) or not isinstance(self.cap, int):
            raise TypeError("WeaponMaximumLevelItemComponent.cap 必须是整数")
        if self.delta != 1:
            raise ValueError("武器上限道具第一版每次只能提升 1 级")
        if not 1 <= self.cap <= WEAPON_ABSOLUTE_MAXIMUM_LEVEL:
            raise ValueError("武器上限道具封顶值无效")


@dataclass(frozen=True)
class WeaponExperienceItemComponent:
    maximum_experience: int = 40_000

    def __post_init__(self) -> None:
        if isinstance(self.maximum_experience, bool) or not isinstance(
            self.maximum_experience,
            int,
        ):
            raise TypeError("WeaponExperienceItemComponent.maximum_experience 必须是整数")
        if self.maximum_experience < 1:
            raise ValueError("武器经验物品的单次经验上限必须大于 0")


WEAPON_MAXIMUM_LEVEL_ITEM_COMPONENT_TYPE = ItemComponentType(
    WEAPON_MAXIMUM_LEVEL_ITEM_COMPONENT_ID,
    WeaponMaximumLevelItemComponent,
)
WEAPON_EXPERIENCE_ITEM_COMPONENT_TYPE = ItemComponentType(
    WEAPON_EXPERIENCE_ITEM_COMPONENT_ID,
    WeaponExperienceItemComponent,
)


@dataclass(frozen=True)
class WeaponItemUseCommand:
    id: str
    actor_id: str
    item_asset_id: str
    weapon_asset_id: str

    def __post_init__(self) -> None:
        for field_name in ("id", "actor_id", "item_asset_id", "weapon_asset_id"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"WeaponItemUseCommand 缺少 {field_name}")


@dataclass(frozen=True)
class WeaponItemUseReceipt:
    transaction_id: str
    actor_id: str
    item_asset_id: str
    item_definition_id: str
    weapon_asset_id: str
    weapon_definition_id: str
    level_before: int
    level_after: int
    maximum_level_before: int
    maximum_level_after: int
    experience_before: int = 0
    experience_after: int = 0
    experience_granted: int = 0
    replayed: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "transaction_id",
            "actor_id",
            "item_asset_id",
            "weapon_asset_id",
        ):
            if not getattr(self, field_name).strip():
                raise ValueError(f"WeaponItemUseReceipt 缺少 {field_name}")
        object.__setattr__(
            self,
            "item_definition_id",
            stable_id(self.item_definition_id, field="item definition id"),
        )
        object.__setattr__(
            self,
            "weapon_definition_id",
            stable_id(self.weapon_definition_id, field="weapon definition id"),
        )
        levels = (
            self.level_before,
            self.level_after,
            self.maximum_level_before,
            self.maximum_level_after,
        )
        if any(isinstance(value, bool) or not isinstance(value, int) for value in levels):
            raise TypeError("WeaponItemUseReceipt 等级字段必须是整数")
        if min(levels) < 1:
            raise ValueError("WeaponItemUseReceipt 等级字段必须大于 0")
        if self.level_after < self.level_before:
            raise ValueError("武器使用回执不能降低等级")
        if self.maximum_level_after < self.maximum_level_before:
            raise ValueError("武器使用回执不能降低等级上限")
        experiences = (
            self.experience_before,
            self.experience_after,
            self.experience_granted,
        )
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in experiences
        ):
            raise ValueError("WeaponItemUseReceipt 经验字段必须是非负整数")
        if not isinstance(self.replayed, bool):
            raise TypeError("WeaponItemUseReceipt.replayed 必须是布尔值")


def weapon_item_use_fingerprint(command: WeaponItemUseCommand) -> str:
    payload = json.dumps(
        {
            "id": command.id,
            "actor_id": command.actor_id,
            "item_asset_id": command.item_asset_id,
            "weapon_asset_id": command.weapon_asset_id,
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(payload.encode("utf-8")).hexdigest()


__all__ = [
    "WEAPON_EXPERIENCE_ITEM_COMPONENT_ID",
    "WEAPON_EXPERIENCE_ITEM_COMPONENT_TYPE",
    "WEAPON_MAXIMUM_LEVEL_ITEM_COMPONENT_ID",
    "WEAPON_MAXIMUM_LEVEL_ITEM_COMPONENT_TYPE",
    "WeaponExperienceItemComponent",
    "WeaponMaximumLevelItemComponent",
    "WeaponItemUseCommand",
    "WeaponItemUseReceipt",
    "weapon_item_use_fingerprint",
]
