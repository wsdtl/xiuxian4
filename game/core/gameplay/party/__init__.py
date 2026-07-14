"""跨玩法复用的临时队伍与战斗阵营投影。"""

PARTY_FOUNDATION_VERSION = "party.foundation.v1"

from .engine import PartyEngine
from .admission import (
    PARTY_INVITATION_PARTY_ID_KEY,
    PartyAdmissionCommand,
    PartyAdmissionExecution,
    party_invitation_metadata,
)
from .integration import PartyBattleProjector, party_team_id
from .models import (
    AddPartyMember,
    CreateParty,
    DisbandParty,
    LeaveParty,
    Party,
    PartyCatalog,
    PartyCommand,
    PartyDefinition,
    PartyExecution,
    PartyMember,
    PartyState,
    PartyStatus,
    RemovePartyMember,
    SetPartyMemberReady,
    SetPartyMemberSlot,
    TransferPartyLeadership,
)

__all__ = [
    "PARTY_FOUNDATION_VERSION",
    "PARTY_INVITATION_PARTY_ID_KEY",
    "AddPartyMember",
    "CreateParty",
    "DisbandParty",
    "LeaveParty",
    "Party",
    "PartyAdmissionCommand",
    "PartyAdmissionExecution",
    "PartyBattleProjector",
    "PartyCatalog",
    "PartyCommand",
    "PartyDefinition",
    "PartyEngine",
    "PartyExecution",
    "PartyMember",
    "PartyState",
    "PartyStatus",
    "RemovePartyMember",
    "SetPartyMemberReady",
    "SetPartyMemberSlot",
    "TransferPartyLeadership",
    "party_team_id",
    "party_invitation_metadata",
]
