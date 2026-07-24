"""Party sparring request metadata and public operation results."""

from __future__ import annotations

from dataclasses import dataclass

from game.core.gameplay import Party, SocialRequest
from game.rules.battle_report import BattleReportReference


@dataclass(frozen=True)
class PartySignature:
    party_id: str
    leader_id: str
    members: str

    @classmethod
    def from_party(cls, party: Party) -> "PartySignature":
        members = ",".join(
            f"{value.subject_id}:{value.slot}"
            for value in sorted(party.members.values(), key=lambda item: item.subject_id)
        )
        return cls(party.id, party.leader_id, members)

    def matches(self, party: Party) -> bool:
        return self == self.from_party(party)


@dataclass(frozen=True)
class PartySparringRequestMetadata:
    challenger: PartySignature
    defender: PartySignature

    def to_mapping(self) -> dict[str, str]:
        return {
            "challenger_party_id": self.challenger.party_id,
            "challenger_leader_id": self.challenger.leader_id,
            "challenger_members": self.challenger.members,
            "defender_party_id": self.defender.party_id,
            "defender_leader_id": self.defender.leader_id,
            "defender_members": self.defender.members,
        }

    @classmethod
    def from_request(cls, request: SocialRequest) -> "PartySparringRequestMetadata":
        values = request.metadata
        required = (
            "challenger_party_id",
            "challenger_leader_id",
            "challenger_members",
            "defender_party_id",
            "defender_leader_id",
            "defender_members",
        )
        if any(not isinstance(values.get(key), str) or not str(values[key]).strip() for key in required):
            raise ValueError("组队切磋请求缺少完整队伍快照")
        return cls(
            PartySignature(
                str(values["challenger_party_id"]),
                str(values["challenger_leader_id"]),
                str(values["challenger_members"]),
            ),
            PartySignature(
                str(values["defender_party_id"]),
                str(values["defender_leader_id"]),
                str(values["defender_members"]),
            ),
        )


@dataclass(frozen=True)
class PartySparringStorageKinds:
    party: str
    character: str
    inventory: str
    loadout: str
    companion_roster: str
    character_world: str
    inscription_preference: str


@dataclass(frozen=True)
class PartySparringRequestResult:
    status: str
    request: SocialRequest | None = None
    challenger_party: Party | None = None
    defender_party: Party | None = None
    failure_message: str = ""


@dataclass(frozen=True)
class PartySparringResult:
    status: str
    request: SocialRequest | None = None
    report: BattleReportReference | None = None
    challenger_party: Party | None = None
    defender_party: Party | None = None
    winner_party_id: str | None = None
    draw: bool = False
    turns: int = 0
    failure_message: str = ""


__all__ = [
    "PartySignature",
    "PartySparringRequestMetadata",
    "PartySparringRequestResult",
    "PartySparringResult",
    "PartySparringStorageKinds",
]
