"""角色身份、核心数值、成长轨道与持久资源状态。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Mapping
from unicodedata import east_asian_width

from ..ids import StableId, stable_id


HEALTH_MAXIMUM = "health.maximum"
SPIRIT_MAXIMUM = "spirit.maximum"
COMBAT_ATTACK = "combat.attack"
COMBAT_DEFENSE = "combat.defense.physical"
COMBAT_SPEED = "combat.speed"

HEALTH_CURRENT = "health.current"
SPIRIT_CURRENT = "spirit.current"

CORE_ATTRIBUTE_IDS = frozenset(
    {
        HEALTH_MAXIMUM,
        SPIRIT_MAXIMUM,
        COMBAT_ATTACK,
        COMBAT_DEFENSE,
        COMBAT_SPEED,
    }
)
PERSISTENT_RESOURCE_IDS = frozenset({HEALTH_CURRENT, SPIRIT_CURRENT})
MAX_CHARACTER_NAME_LENGTH = 64


class CharacterStatus(str, Enum):
    """角色档案的最小生命周期。"""

    ACTIVE = "active"
    RETIRED = "retired"


@dataclass(frozen=True)
class ProgressionState:
    """一条成长轨道的当前阶段和经验。"""

    definition_id: StableId
    level: int = 1
    experience: int = 0
    total_experience: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "definition_id",
            stable_id(self.definition_id, field="progression id"),
        )
        if self.level < 1:
            raise ValueError("ProgressionState.level 必须大于 0")
        if self.experience < 0 or self.total_experience < 0:
            raise ValueError("成长经验不能小于 0")
        if self.experience > self.total_experience:
            raise ValueError("当前成长经验不能大于累计经验")


@dataclass(frozen=True)
class CharacterState:
    """与平台、数据库和具体世界名称无关的角色永久状态。"""

    id: str
    account_id: str
    name: str
    template_id: StableId
    created_at: datetime
    core_attributes: Mapping[StableId, float]
    resources: Mapping[StableId, float]
    progressions: Mapping[StableId, ProgressionState] = field(default_factory=dict)
    features: frozenset[StableId] = frozenset()
    status: CharacterStatus = CharacterStatus.ACTIVE
    revision: int = 0

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("CharacterState 缺少 id")
        if not self.account_id.strip():
            raise ValueError("CharacterState 缺少 account_id")
        object.__setattr__(self, "name", normalize_character_name(self.name))
        object.__setattr__(self, "template_id", stable_id(self.template_id, field="template id"))
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("CharacterState.created_at 必须包含时区")
        attributes = {
            stable_id(key, field="core attribute id"): float(value)
            for key, value in self.core_attributes.items()
        }
        if set(attributes) != set(CORE_ATTRIBUTE_IDS):
            missing = CORE_ATTRIBUTE_IDS - set(attributes)
            extra = set(attributes) - CORE_ATTRIBUTE_IDS
            raise ValueError(
                "角色核心属性必须且只能包含五项标准值："
                f"missing={sorted(missing)}, extra={sorted(extra)}"
            )
        _validate_core_attributes(attributes)
        resources = {
            stable_id(key, field="persistent resource id"): float(value)
            for key, value in self.resources.items()
        }
        if set(resources) != set(PERSISTENT_RESOURCE_IDS):
            missing = PERSISTENT_RESOURCE_IDS - set(resources)
            extra = set(resources) - PERSISTENT_RESOURCE_IDS
            raise ValueError(
                "角色持久资源必须且只能包含当前血气和当前灵力："
                f"missing={sorted(missing)}, extra={sorted(extra)}"
            )
        if any(value < 0 for value in resources.values()):
            raise ValueError("角色持久资源不能小于 0")
        progressions = dict(self.progressions)
        for key, value in progressions.items():
            normalized = stable_id(key, field="progression id")
            if normalized != value.definition_id:
                raise ValueError(f"成长轨道映射键与定义 id 不一致：{key}")
        features = frozenset(stable_id(value, field="feature id") for value in self.features)
        if self.revision < 0:
            raise ValueError("CharacterState.revision 不能小于 0")
        object.__setattr__(self, "core_attributes", MappingProxyType(attributes))
        object.__setattr__(self, "resources", MappingProxyType(resources))
        object.__setattr__(self, "progressions", MappingProxyType(progressions))
        object.__setattr__(self, "features", features)
        object.__setattr__(self, "status", CharacterStatus(self.status))


@dataclass(frozen=True)
class CharacterRosterState:
    """一个账号拥有的角色 ID 目录；数量上限由具体游戏决定。"""

    account_id: str
    character_ids: tuple[str, ...] = ()
    revision: int = 0

    def __post_init__(self) -> None:
        account_id = str(self.account_id or "").strip()
        if not account_id:
            raise ValueError("CharacterRosterState 缺少 account_id")
        character_ids = tuple(
            character_id
            for value in self.character_ids
            if (character_id := str(value or "").strip())
        )
        if len(character_ids) != len(set(character_ids)):
            raise ValueError("账号角色目录存在重复角色 ID")
        if self.revision < 0:
            raise ValueError("CharacterRosterState.revision 不能小于 0")
        object.__setattr__(self, "account_id", account_id)
        object.__setattr__(self, "character_ids", character_ids)


def _validate_core_attributes(values: Mapping[StableId, float]) -> None:
    if values[HEALTH_MAXIMUM] < 1:
        raise ValueError("最大血气必须大于等于 1")
    for attribute_id in (SPIRIT_MAXIMUM, COMBAT_ATTACK, COMBAT_SPEED):
        if values[attribute_id] < 0:
            raise ValueError(f"角色核心属性 {attribute_id} 不能小于 0")
    # 防御刻意不设置下限，负防由战斗规则折算为增伤。


def normalize_character_name(value: object) -> str:
    """清理玩家角色名；具体名称来源由产品策略决定。"""

    name = " ".join(str(value or "").split())
    if not name:
        raise ValueError("角色名不能为空")
    if len(name) > MAX_CHARACTER_NAME_LENGTH:
        raise ValueError(f"角色名不能超过 {MAX_CHARACTER_NAME_LENGTH} 个字符")
    return name


def character_name_display_width(value: object) -> int:
    """按聊天界面占位计算名称宽度；全角字符计 2，其余字符计 1。"""

    return sum(
        2 if east_asian_width(character) in {"F", "W"} else 1
        for character in str(value or "")
    )


__all__ = [
    "COMBAT_ATTACK",
    "COMBAT_DEFENSE",
    "COMBAT_SPEED",
    "CORE_ATTRIBUTE_IDS",
    "CharacterState",
    "CharacterRosterState",
    "CharacterStatus",
    "HEALTH_CURRENT",
    "HEALTH_MAXIMUM",
    "MAX_CHARACTER_NAME_LENGTH",
    "PERSISTENT_RESOURCE_IDS",
    "ProgressionState",
    "SPIRIT_CURRENT",
    "SPIRIT_MAXIMUM",
    "character_name_display_width",
    "normalize_character_name",
]
