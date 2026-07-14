"""把持久队伍投影为战斗阵营，不让队伍域接管战斗状态。"""

from __future__ import annotations

from hashlib import sha256

from ..combat import BattleParticipant
from .models import Party, PartyStatus


def party_team_id(party_id: str) -> str:
    if not party_id.strip():
        raise ValueError("队伍 ID 不能为空")
    digest = sha256(party_id.encode("utf-8")).hexdigest()[:24]
    return f"battle_team.party_{digest}"


class PartyBattleProjector:
    def participants(
        self,
        party: Party,
        *,
        require_all_ready: bool = False,
    ) -> tuple[BattleParticipant, ...]:
        if party.status is not PartyStatus.ACTIVE:
            raise ValueError("已经解散的队伍不能进入战斗")
        if require_all_ready and not all(value.ready for value in party.members.values()):
            raise ValueError("队伍仍有成员未准备")
        team_id = party_team_id(party.id)
        return tuple(
            BattleParticipant(member.subject_id, team_id, member.slot)
            for member in sorted(
                party.members.values(),
                key=lambda value: (value.slot, value.subject_id),
            )
        )


__all__ = ["PartyBattleProjector", "party_team_id"]
