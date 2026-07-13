"""平台身份到内部账号及游戏归属的公共底座。"""

ACCOUNT_FOUNDATION_VERSION = "account.foundation.v1"

from .engine import (
    AccountEngine,
    AccountMutation,
    AccountResolution,
    AccountStatusTransaction,
    AccountViolation,
    UnbindIdentityTransaction,
)
from .models import (
    AccountDirectoryState,
    AccountEvent,
    AccountState,
    AccountStatus,
    EvidenceRecord,
    ExternalIdentity,
    IdentityBinding,
    IdentityConflict,
    IdentityEvidence,
    IdentityKey,
)
from .ownership import (
    ACCOUNT_PRINCIPAL,
    BUSINESS_PRINCIPAL,
    CHARACTER_PRINCIPAL,
    PRINCIPAL_KINDS,
    SYSTEM_PRINCIPAL,
    AccountOwned,
    PrincipalRef,
    account_owns,
    require_account_owner,
)
from .qq_bridge import (
    QQ_ACTOR_KIND,
    QQ_GROUP_MEMBER_KIND,
    QQ_PROVIDER_ID,
    QQ_USER_KIND,
    build_qq_identity_evidence,
)

__all__ = [
    "ACCOUNT_FOUNDATION_VERSION",
    "ACCOUNT_PRINCIPAL",
    "BUSINESS_PRINCIPAL",
    "CHARACTER_PRINCIPAL",
    "PRINCIPAL_KINDS",
    "QQ_ACTOR_KIND",
    "QQ_GROUP_MEMBER_KIND",
    "QQ_PROVIDER_ID",
    "QQ_USER_KIND",
    "SYSTEM_PRINCIPAL",
    "AccountDirectoryState",
    "AccountEngine",
    "AccountEvent",
    "AccountMutation",
    "AccountOwned",
    "AccountResolution",
    "AccountState",
    "AccountStatus",
    "AccountStatusTransaction",
    "AccountViolation",
    "EvidenceRecord",
    "ExternalIdentity",
    "IdentityBinding",
    "IdentityConflict",
    "IdentityEvidence",
    "IdentityKey",
    "PrincipalRef",
    "UnbindIdentityTransaction",
    "account_owns",
    "build_qq_identity_evidence",
    "require_account_owner",
]
