"""把 QQ 驱动已验证字段转换成协议中立身份凭据。"""

from __future__ import annotations

from datetime import datetime

from .models import ExternalIdentity, IdentityEvidence


QQ_PROVIDER_ID = "platform.qq"
QQ_USER_KIND = "identity.qq_user"
QQ_GROUP_MEMBER_KIND = "identity.qq_group_member"
QQ_COMPAT_ACTOR_KIND = "identity.qq_actor_compat"


def build_qq_identity_evidence(
    *,
    bot_app_id: str,
    event_id: str,
    logical_time: datetime,
    conversation_type: str,
    actor_openid: str = "",
    user_openid: str = "",
    member_openid: str = "",
    group_openid: str = "",
) -> IdentityEvidence:
    """同一 QQ 签名事件提供 user/member 时，把两者作为一组可靠别名。"""

    tenant = str(bot_app_id or "").strip()
    if not tenant:
        raise ValueError("QQ 身份凭据缺少 bot_app_id")
    source_event_id = str(event_id or "").strip()
    if not source_event_id:
        raise ValueError("QQ 身份凭据缺少 event_id")
    conversation = str(conversation_type or "").strip()
    user = str(user_openid or "").strip()
    member = str(member_openid or "").strip()
    group = str(group_openid or "").strip()
    actor = str(actor_openid or "").strip()
    identities: list[ExternalIdentity] = []
    if user:
        identities.append(
            ExternalIdentity(QQ_PROVIDER_ID, tenant, QQ_USER_KIND, "", user)
        )
    if member:
        if not group:
            raise ValueError("QQ 群成员身份缺少 group_openid 作用域")
        identities.append(
            ExternalIdentity(
                QQ_PROVIDER_ID,
                tenant,
                QQ_GROUP_MEMBER_KIND,
                group,
                member,
            )
        )
    if not identities:
        if not actor:
            raise ValueError("QQ 身份凭据没有可用的 openid")
        identities.append(
            ExternalIdentity(
                QQ_PROVIDER_ID,
                tenant,
                QQ_COMPAT_ACTOR_KIND,
                group if conversation == "group" else "",
                actor,
            )
        )
    if conversation == "group" and member:
        primary = next(
            identity for identity in identities if identity.subject_kind == QQ_GROUP_MEMBER_KIND
        )
    elif user:
        primary = next(identity for identity in identities if identity.subject_kind == QQ_USER_KIND)
    else:
        primary = identities[0]
    aliases = tuple(identity for identity in identities if identity != primary)
    return IdentityEvidence(
        id=f"qq:{tenant}:{source_event_id}",
        primary=primary,
        aliases=aliases,
        source_kind="identity.qq_signed_event",
        logical_time=logical_time,
    )


__all__ = [
    "QQ_COMPAT_ACTOR_KIND",
    "QQ_GROUP_MEMBER_KIND",
    "QQ_PROVIDER_ID",
    "QQ_USER_KIND",
    "build_qq_identity_evidence",
]
