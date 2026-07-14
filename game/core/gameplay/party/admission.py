"""社会请求与队伍加入之间的类型化联合命令。"""

from __future__ import annotations

from dataclasses import dataclass

from ..ids import StableId, stable_id
from ..social import SocialExecution
from .models import PartyExecution


PARTY_INVITATION_PARTY_ID_KEY = "party_id"


def party_invitation_metadata(party_id: str) -> dict[str, str]:
    if not party_id.strip():
        raise ValueError("队伍邀请缺少 party_id")
    return {PARTY_INVITATION_PARTY_ID_KEY: party_id}


@dataclass(frozen=True)
class PartyAdmissionCommand:
    id: str
    actor_id: str
    social_scope_id: str
    party_scope_id: str
    request_id: str
    request_kind_id: StableId
    party_id: str
    expected_social_revision: int
    expected_party_revision: int

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (
                self.id,
                self.actor_id,
                self.social_scope_id,
                self.party_scope_id,
                self.request_id,
                self.party_id,
            )
        ):
            raise ValueError("PartyAdmissionCommand 缺少必要身份")
        if self.expected_social_revision < 0 or self.expected_party_revision < 0:
            raise ValueError("队伍邀请接力 revision 不能小于 0")
        object.__setattr__(
            self,
            "request_kind_id",
            stable_id(self.request_kind_id, field="social request kind id"),
        )


@dataclass(frozen=True)
class PartyAdmissionExecution:
    command_id: str
    social: SocialExecution
    party: PartyExecution

    def __post_init__(self) -> None:
        if not self.command_id.strip():
            raise ValueError("PartyAdmissionExecution 缺少 command_id")


__all__ = [
    "PARTY_INVITATION_PARTY_ID_KEY",
    "PartyAdmissionCommand",
    "PartyAdmissionExecution",
    "party_invitation_metadata",
]
