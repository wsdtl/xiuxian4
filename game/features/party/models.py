"""队伍业务对命令层公开的稳定结果。"""

from __future__ import annotations

from dataclasses import dataclass

from game.core.gameplay import Party, SocialRequest


@dataclass(frozen=True)
class PartyView:
    party: Party | None = None
    incoming_requests: tuple[SocialRequest, ...] = ()
    state_revision: int = 0


@dataclass(frozen=True)
class PartyOperationResult:
    status: str
    party: Party | None = None
    request: SocialRequest | None = None
    incoming_requests: tuple[SocialRequest, ...] = ()
    failure_message: str = ""
    replayed: bool = False


__all__ = ["PartyOperationResult", "PartyView"]
