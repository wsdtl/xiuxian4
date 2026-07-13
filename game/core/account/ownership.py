"""账号、角色、系统和业务流程共用的类型化归属引用。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .models import _stable_id


ACCOUNT_PRINCIPAL = "principal.account"
CHARACTER_PRINCIPAL = "principal.character"
SYSTEM_PRINCIPAL = "principal.system"
BUSINESS_PRINCIPAL = "principal.business"
PRINCIPAL_KINDS = frozenset(
    {ACCOUNT_PRINCIPAL, CHARACTER_PRINCIPAL, SYSTEM_PRINCIPAL, BUSINESS_PRINCIPAL}
)


@dataclass(frozen=True)
class PrincipalRef:
    kind: str
    id: str

    def __post_init__(self) -> None:
        kind = _stable_id(self.kind, field_name="principal kind")
        if kind not in PRINCIPAL_KINDS:
            raise ValueError(f"未知归属主体类型：{kind}")
        if not self.id.strip():
            raise ValueError("PrincipalRef 缺少 id")
        object.__setattr__(self, "kind", kind)


class AccountOwned(Protocol):
    account_id: str


def account_owns(account_id: str, value: AccountOwned) -> bool:
    """只比较内部账号 ID，不读取任何平台身份。"""

    return bool(account_id.strip()) and value.account_id == account_id


def require_account_owner(account_id: str, value: AccountOwned) -> None:
    if not account_owns(account_id, value):
        raise PermissionError("当前账号不是该对象的所有者")


__all__ = [
    "ACCOUNT_PRINCIPAL",
    "BUSINESS_PRINCIPAL",
    "CHARACTER_PRINCIPAL",
    "PRINCIPAL_KINDS",
    "SYSTEM_PRINCIPAL",
    "AccountOwned",
    "PrincipalRef",
    "account_owns",
    "require_account_owner",
]
