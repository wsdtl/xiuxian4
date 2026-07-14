"""临时队伍成员、队长、站位和准备状态的纯规则状态机。"""

from __future__ import annotations

from dataclasses import replace

from ..context import RuleContext
from ..errors import RuleOutcome, RuleViolation
from ..events import RuleEvent
from .models import (
    AddPartyMember,
    CreateParty,
    DisbandParty,
    LeaveParty,
    Party,
    PartyCatalog,
    PartyCommand,
    PartyExecution,
    PartyMember,
    PartyState,
    PartyStatus,
    RemovePartyMember,
    SetPartyMemberReady,
    SetPartyMemberSlot,
    TransferPartyLeadership,
)


class PartyEngine:
    def __init__(self, catalog: PartyCatalog) -> None:
        if not catalog.finalized:
            catalog.finalize()
        self.catalog = catalog

    def execute(
        self,
        command: PartyCommand,
        *,
        state: PartyState,
        context: RuleContext,
    ) -> RuleOutcome[PartyExecution]:
        checkpoint = context.random.checkpoint()
        try:
            if state.revision != command.expected_revision:
                self._fail(
                    "party.revision_conflict",
                    "队伍状态版本与命令预期不一致",
                    {"expected": command.expected_revision, "actual": state.revision},
                )
            parties = dict(state.parties)
            operation = command.operation
            if isinstance(operation, CreateParty):
                party, kind, values = self._create(command, operation, parties, context)
            elif isinstance(operation, AddPartyMember):
                party, kind, values = self._add(command, operation, parties, context)
            elif isinstance(operation, RemovePartyMember):
                party, kind, values = self._remove(command, operation, parties)
            elif isinstance(operation, LeaveParty):
                party, kind, values = self._leave(command, operation, parties)
            elif isinstance(operation, TransferPartyLeadership):
                party, kind, values = self._transfer(command, operation, parties)
            elif isinstance(operation, SetPartyMemberReady):
                party, kind, values = self._ready(command, operation, parties)
            elif isinstance(operation, SetPartyMemberSlot):
                party, kind, values = self._slot(command, operation, parties)
            elif isinstance(operation, DisbandParty):
                party, kind, values = self._disband(command, operation, parties)
            else:
                raise TypeError(f"未知队伍操作：{type(operation).__name__}")
            next_state = PartyState(state.scope_id, parties, state.revision + 1)
            event = RuleEvent.from_context(
                context,
                kind=kind,
                source_id=command.actor_id,
                target_id=party.id,
                subject_id=party.definition_id,
                values={"command_id": command.id, **values},
            )
            return RuleOutcome.success(PartyExecution(command.id, next_state, party, (event,)))
        except RuleViolation as exc:
            context.random.restore(checkpoint)
            return RuleOutcome.failed(exc.failure)

    def _create(self, command, operation, parties, context):
        if operation.party_id in parties:
            self._fail("party.exists", "队伍 ID 已经存在")
        self._require_unassigned(parties, command.actor_id)
        self.catalog.require(operation.definition_id)
        leader = PartyMember(command.actor_id, 0, context.logical_time)
        party = Party(
            operation.party_id,
            operation.definition_id,
            command.actor_id,
            {command.actor_id: leader},
            context.logical_time,
        )
        parties[party.id] = party
        return party, "party.created", {"leader_id": command.actor_id}

    def _add(self, command, operation, parties, context):
        party = self._active(parties, operation.party_id)
        self._require_leader(party, command.actor_id)
        if operation.subject_id in party.members:
            self._fail("party.already_member", "主体已经属于该队伍")
        self._require_unassigned(parties, operation.subject_id)
        definition = self.catalog.require(party.definition_id)
        if len(party.members) >= definition.capacity:
            self._fail("party.capacity_reached", "队伍人数已经达到上限")
        slot = next(value for value in range(definition.capacity) if value not in _slots(party))
        members = _reset_ready(party.members)
        members[operation.subject_id] = PartyMember(
            operation.subject_id,
            slot,
            context.logical_time,
        )
        party = replace(party, members=members)
        parties[party.id] = party
        return party, "party.member.joined", {
            "subject_id": operation.subject_id,
            "slot": slot,
        }

    def _remove(self, command, operation, parties):
        party = self._active(parties, operation.party_id)
        self._require_leader(party, command.actor_id)
        if operation.subject_id == party.leader_id:
            self._fail("party.leader_cannot_be_removed", "队长不能踢出自己")
        if operation.subject_id not in party.members:
            self._fail("party.member_unknown", "主体不属于该队伍")
        members = _reset_ready(party.members)
        del members[operation.subject_id]
        party = replace(party, members=members)
        parties[party.id] = party
        return party, "party.member.removed", {"subject_id": operation.subject_id}

    def _leave(self, command, operation, parties):
        party = self._active(parties, operation.party_id)
        if command.actor_id not in party.members:
            self._fail("party.member_unknown", "当前主体不属于该队伍")
        if command.actor_id == party.leader_id:
            if len(party.members) > 1:
                self._fail("party.leader_must_transfer", "队长离队前必须转让队长或解散队伍")
            return self._disband(command, DisbandParty(party.id), parties)
        members = _reset_ready(party.members)
        del members[command.actor_id]
        party = replace(party, members=members)
        parties[party.id] = party
        return party, "party.member.left", {"subject_id": command.actor_id}

    def _transfer(self, command, operation, parties):
        party = self._active(parties, operation.party_id)
        self._require_leader(party, command.actor_id)
        if operation.next_leader_id == party.leader_id:
            self._fail("party.leader_unchanged", "目标主体已经是队长")
        if operation.next_leader_id not in party.members:
            self._fail("party.member_unknown", "新队长不属于该队伍")
        party = replace(party, leader_id=operation.next_leader_id)
        parties[party.id] = party
        return party, "party.leadership.transferred", {
            "previous_leader_id": command.actor_id,
            "next_leader_id": operation.next_leader_id,
        }

    def _ready(self, command, operation, parties):
        party = self._active(parties, operation.party_id)
        try:
            member = party.members[command.actor_id]
        except KeyError:
            self._fail("party.member_unknown", "当前主体不属于该队伍")
        members = dict(party.members)
        members[command.actor_id] = replace(member, ready=bool(operation.ready))
        party = replace(party, members=members)
        parties[party.id] = party
        return party, "party.member.ready_changed", {
            "subject_id": command.actor_id,
            "ready": bool(operation.ready),
        }

    def _slot(self, command, operation, parties):
        party = self._active(parties, operation.party_id)
        self._require_leader(party, command.actor_id)
        definition = self.catalog.require(party.definition_id)
        if operation.slot >= definition.capacity:
            self._fail("party.slot_out_of_range", "队伍站位超过容量范围")
        try:
            member = party.members[operation.subject_id]
        except KeyError:
            self._fail("party.member_unknown", "待调整主体不属于该队伍")
        members = _reset_ready(party.members)
        occupant = next(
            (value for value in members.values() if value.slot == operation.slot),
            None,
        )
        members[operation.subject_id] = replace(member, slot=operation.slot, ready=False)
        if occupant is not None and occupant.subject_id != operation.subject_id:
            members[occupant.subject_id] = replace(occupant, slot=member.slot, ready=False)
        party = replace(party, members=members)
        parties[party.id] = party
        return party, "party.member.slot_changed", {
            "subject_id": operation.subject_id,
            "from_slot": member.slot,
            "to_slot": operation.slot,
            "swapped_subject_id": (
                occupant.subject_id
                if occupant is not None and occupant.subject_id != operation.subject_id
                else None
            ),
        }

    def _disband(self, command, operation, parties):
        party = self._active(parties, operation.party_id)
        self._require_leader(party, command.actor_id)
        party = replace(
            party,
            members=_reset_ready(party.members),
            status=PartyStatus.DISBANDED,
        )
        parties[party.id] = party
        return party, "party.disbanded", {"member_count": len(party.members)}

    def _active(self, parties, party_id: str) -> Party:
        try:
            party = parties[party_id]
        except KeyError:
            PartyEngine._fail("party.unknown", "找不到指定队伍")
        if party.status is not PartyStatus.ACTIVE:
            PartyEngine._fail("party.inactive", "队伍已经解散")
        definition = self.catalog.require(party.definition_id)
        if len(party.members) > definition.capacity or any(
            member.slot >= definition.capacity for member in party.members.values()
        ):
            PartyEngine._fail("party.state_invalid", "队伍人数或站位超过内容定义")
        return party

    @staticmethod
    def _require_leader(party: Party, actor_id: str) -> None:
        if party.leader_id != actor_id:
            PartyEngine._fail("party.permission_denied", "只有队长可以执行该操作")

    @staticmethod
    def _require_unassigned(parties, subject_id: str) -> None:
        if any(
            party.status is PartyStatus.ACTIVE and subject_id in party.members
            for party in parties.values()
        ):
            PartyEngine._fail("party.exclusive_membership", "主体已经加入其他活跃队伍")

    @staticmethod
    def _fail(code, message, details=None) -> None:
        raise RuleViolation(code, message, details or {})


def _slots(party: Party) -> set[int]:
    return {value.slot for value in party.members.values()}


def _reset_ready(members) -> dict[str, PartyMember]:
    return {
        key: replace(value, ready=False) if value.ready else value
        for key, value in members.items()
    }


__all__ = ["PartyEngine"]
