"""角色数量与名称来源策略，不涉及初始属性或资产。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from game.core.gameplay import normalize_character_name


CHARACTERS_PER_ACCOUNT = 1


class CharacterNameSource(str, Enum):
    REQUESTED = "requested"
    PLATFORM = "platform"


class CharacterIdentityViolation(ValueError):
    """角色身份策略拒绝；code 可直接映射为组件提示。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class PreparedCharacterIdentity:
    account_id: str
    name: str
    name_source: CharacterNameSource


class CharacterIdentityPolicy:
    """准备角色身份；角色初始化服务必须在事务内使用本策略。"""

    def prepare_creation(
        self,
        *,
        account_id: str,
        requested_name: object = "",
        platform_name: object = "",
        existing_character_ids: tuple[str, ...] = (),
    ) -> PreparedCharacterIdentity:
        owner = str(account_id or "").strip()
        if not owner:
            raise CharacterIdentityViolation(
                "character.account_required",
                "创建角色缺少账号",
            )
        existing = tuple(
            character_id
            for value in existing_character_ids
            if (character_id := str(value or "").strip())
        )
        if len(existing) >= CHARACTERS_PER_ACCOUNT:
            raise CharacterIdentityViolation(
                "character.account_already_has_character",
                "一个账号只能拥有一个角色",
            )

        requested = " ".join(str(requested_name or "").split())
        platform = " ".join(str(platform_name or "").split())
        if requested:
            source = CharacterNameSource.REQUESTED
            raw_name = requested
        elif platform:
            source = CharacterNameSource.PLATFORM
            raw_name = platform
        else:
            raise CharacterIdentityViolation(
                "character.name_required",
                "当前消息没有提供角色名，QQ 事件也没有携带可用名称",
            )
        try:
            name = normalize_character_name(raw_name)
        except ValueError as exc:
            raise CharacterIdentityViolation(
                "character.name_invalid",
                str(exc),
            ) from exc
        return PreparedCharacterIdentity(owner, name, source)


__all__ = [
    "CHARACTERS_PER_ACCOUNT",
    "CharacterIdentityPolicy",
    "CharacterIdentityViolation",
    "CharacterNameSource",
    "PreparedCharacterIdentity",
]
