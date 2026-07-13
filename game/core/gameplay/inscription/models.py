"""铭刻目标、实例数据、个人展示偏好和执行结果。"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping, TypeAlias

from ..events import RuleEvent
from ..ids import StableId, stable_id
from ..inventory import InventoryState


INSCRIPTION_DATA_KEY = "instance_data.inscription"
INSCRIPTION_MEDIUM_DATA_KEY = "instance_data.inscription_medium"
MAX_INSCRIPTION_NAME_LENGTH = 12
_FORBIDDEN_NAME_CHARACTERS = frozenset("[]()<>|*_`~#\\")


@dataclass(frozen=True)
class AssetInscriptionTarget:
    asset_id: str

    def __post_init__(self) -> None:
        if not self.asset_id.strip():
            raise ValueError("AssetInscriptionTarget.asset_id 不能为空")


@dataclass(frozen=True)
class WeaponAbilityInscriptionTarget:
    weapon_asset_id: str
    ability_id: StableId

    def __post_init__(self) -> None:
        if not self.weapon_asset_id.strip():
            raise ValueError("WeaponAbilityInscriptionTarget.weapon_asset_id 不能为空")
        object.__setattr__(self, "ability_id", stable_id(self.ability_id, field="ability id"))


InscriptionTarget: TypeAlias = AssetInscriptionTarget | WeaponAbilityInscriptionTarget


@dataclass(frozen=True)
class InscriptionData:
    """跟随具体物品实例保存的铭刻名，不保存铭刻之羽故事。"""

    asset_name: str = ""
    ability_names: Mapping[StableId, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        asset_name = clean_inscription_name(self.asset_name, allow_empty=True)
        abilities = {
            stable_id(key, field="ability id"): clean_inscription_name(value)
            for key, value in self.ability_names.items()
        }
        object.__setattr__(self, "asset_name", asset_name)
        object.__setattr__(self, "ability_names", MappingProxyType(abilities))


@dataclass(frozen=True)
class InscriptionMediumData:
    """一枚铭刻之羽自己的标题和一次性故事。"""

    title: str
    flavor_text: str

    def __post_init__(self) -> None:
        title = self.title.strip()
        flavor = self.flavor_text.strip()
        if not title or not flavor:
            raise ValueError("铭刻之羽必须同时包含标题和故事")
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "flavor_text", flavor)


@dataclass(frozen=True)
class InscriptionPreference:
    owner_id: str
    show_original_name: bool = True
    revision: int = 0

    def __post_init__(self) -> None:
        if not self.owner_id.strip():
            raise ValueError("InscriptionPreference.owner_id 不能为空")
        if not isinstance(self.show_original_name, bool):
            raise TypeError("show_original_name 必须是 bool")
        if self.revision < 0:
            raise ValueError("InscriptionPreference.revision 不能小于 0")

    def changed(self, show_original_name: bool) -> "InscriptionPreference":
        if not isinstance(show_original_name, bool):
            raise TypeError("show_original_name 必须是 bool")
        if show_original_name == self.show_original_name:
            return self
        return InscriptionPreference(
            self.owner_id,
            show_original_name,
            self.revision + 1,
        )


@dataclass(frozen=True)
class InscriptionCommand:
    id: str
    actor_id: str
    target: InscriptionTarget
    medium_asset_id: str
    custom_name: str
    expected_inventory_revision: int | None = None
    expected_asset_revision: int | None = None

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.actor_id.strip() or not self.medium_asset_id.strip():
            raise ValueError("InscriptionCommand 缺少事务、执行者或铭刻之羽资产 ID")
        if not isinstance(
            self.target,
            (AssetInscriptionTarget, WeaponAbilityInscriptionTarget),
        ):
            raise TypeError("InscriptionCommand.target 类型不正确")
        object.__setattr__(self, "custom_name", clean_inscription_name(self.custom_name))
        for field_name in ("expected_inventory_revision", "expected_asset_revision"):
            value = getattr(self, field_name)
            if value is not None and value < 0:
                raise ValueError(f"{field_name} 不能小于 0")


@dataclass(frozen=True)
class InscriptionReceipt:
    transaction_id: str
    actor_id: str
    target: InscriptionTarget
    medium_asset_id: str
    medium_title: str
    medium_flavor_text: str
    custom_name: str
    replayed: bool = False


@dataclass(frozen=True)
class InscriptionExecution:
    inventory: InventoryState
    receipt: InscriptionReceipt
    events: tuple[RuleEvent, ...]


def clean_inscription_name(value: object, *, allow_empty: bool = False) -> str:
    name = str(value or "").strip()
    if not name and allow_empty:
        return ""
    if not name:
        raise ValueError("铭刻名不能为空")
    if len(name) > MAX_INSCRIPTION_NAME_LENGTH:
        raise ValueError(f"铭刻名不能超过 {MAX_INSCRIPTION_NAME_LENGTH} 个字符")
    if any(character.isspace() or ord(character) < 32 for character in name):
        raise ValueError("铭刻名不能包含空白或控制字符")
    if any(character in _FORBIDDEN_NAME_CHARACTERS for character in name):
        raise ValueError("铭刻名不能包含 Markdown 结构字符")
    return name


def inscription_data(value: object) -> InscriptionData:
    if value is None:
        return InscriptionData()
    if not isinstance(value, InscriptionData):
        raise TypeError("物品实例中的铭刻数据类型不正确")
    return value


__all__ = [
    "INSCRIPTION_DATA_KEY",
    "INSCRIPTION_MEDIUM_DATA_KEY",
    "MAX_INSCRIPTION_NAME_LENGTH",
    "AssetInscriptionTarget",
    "InscriptionCommand",
    "InscriptionData",
    "InscriptionExecution",
    "InscriptionMediumData",
    "InscriptionPreference",
    "InscriptionReceipt",
    "InscriptionTarget",
    "WeaponAbilityInscriptionTarget",
    "clean_inscription_name",
    "inscription_data",
]
