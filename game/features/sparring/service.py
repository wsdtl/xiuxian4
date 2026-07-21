"""切磋请求、双方快照读取和无损战斗结算。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from game.content.catalog.social import (
    SPARRING_REQUEST_ID,
    SPARRING_REQUEST_LIFETIME_SECONDS,
)
from game.core.gameplay import (
    CharacterState,
    CreateSocialRequest,
    HEALTH_CURRENT,
    InventoryState,
    LoadoutState,
    ResolveSocialRequest,
    RuleContext,
    Ruleset,
    SeededRandomSource,
    SocialCommand,
    SocialRequest,
    SocialRequestStatus,
    TagSet,
)
from game.rules.battle_report import (
    BattleReportDraft,
    BattleReportReference,
    BattleReportSegmentDraft,
    BattleReportSummary,
    capture_battle_participant,
    capture_battle_transitions,
)
from game.rules.character import CHARACTER_WORLD_AGGREGATE, CharacterWorldState
from game.rules.companion import CompanionRosterState
from game.rules.sparring import SparringBattleSimulator


SOCIAL_SCOPE_PREFIX = "social:sparring:"
SPARRING_RULE_VERSION = "rules.sparring.v1"


@dataclass(frozen=True)
class SparringRequestResult:
    status: str
    request: SocialRequest | None = None
    failure_message: str = ""


@dataclass(frozen=True)
class SparringStorageKinds:
    inventory: str
    loadout: str
    companion_roster: str


@dataclass(frozen=True)
class SparringResult:
    status: str
    request: SocialRequest | None = None
    report: BattleReportReference | None = None
    challenger: CharacterState | None = None
    defender: CharacterState | None = None
    winner_id: str | None = None
    draw: bool = False
    turns: int = 0
    failure_message: str = ""


class SparringFeature:
    """切磋只改变社会请求和战报，不改变任何玩家战斗资源。"""

    def __init__(
        self,
        database,
        content,
        world_views,
        snapshots,
        social,
        characters,
        battle_reports,
        simulator: SparringBattleSimulator,
        storage: SparringStorageKinds,
    ) -> None:
        self.database = database
        self.content = content
        self.world_views = world_views
        self.snapshots = snapshots
        self.social = social
        self.characters = characters
        self.battle_reports = battle_reports
        self.simulator = simulator
        self.storage = storage

    def create_request(
        self,
        request_id: str,
        challenger: CharacterState,
        defender: CharacterState,
        *,
        logical_time: datetime,
    ) -> SparringRequestResult:
        if challenger.id == defender.id:
            return SparringRequestResult("self", failure_message="不能向自己发起切磋")
        scope_id = sparring_social_scope_id(defender.id)
        state = self.social.initialize(scope_id, logical_time=logical_time)
        existing = next(
            (
                request
                for request in state.requests.values()
                if request.kind_id == SPARRING_REQUEST_ID
                and request.sender_id == challenger.id
                and request.recipient_id == defender.id
                and request.status is SocialRequestStatus.PENDING
                and logical_time < request.expires_at
            ),
            None,
        )
        if existing is not None:
            return SparringRequestResult("already_pending", existing)
        request = SocialRequest(
            request_id,
            SPARRING_REQUEST_ID,
            challenger.id,
            defender.id,
            logical_time,
            logical_time + timedelta(seconds=SPARRING_REQUEST_LIFETIME_SECONDS),
            metadata={"mode": "sparring"},
        )
        outcome = self.social.execute(
            scope_id,
            SocialCommand(
                f"{request_id}:create",
                challenger.id,
                state.revision,
                CreateSocialRequest(request),
            ),
            context=_context(f"{request_id}:create", logical_time, "create"),
        )
        if outcome.failure:
            return SparringRequestResult("failed", failure_message=outcome.failure.message)
        return SparringRequestResult("created", request)

    def reject_request(
        self,
        operation_id: str,
        request_id: str,
        defender: CharacterState,
        *,
        logical_time: datetime,
    ) -> SparringRequestResult:
        state = self.social.load(sparring_social_scope_id(defender.id))
        request = state.requests.get(request_id) if state is not None else None
        if request is None or request.kind_id != SPARRING_REQUEST_ID:
            return SparringRequestResult("unknown", failure_message="找不到这份切磋请求")
        if request.recipient_id != defender.id:
            return SparringRequestResult("forbidden", failure_message="只有应战者可以拒绝切磋")
        if logical_time >= request.expires_at:
            return SparringRequestResult("expired", request, "切磋请求已经过期")
        result = self._resolve(
            operation_id,
            request,
            SocialRequestStatus.REJECTED,
            defender,
            logical_time=logical_time,
        )
        if result is None:
            return SparringRequestResult("failed", failure_message="切磋请求处理失败")
        return SparringRequestResult("rejected", result)

    def accept_request(
        self,
        operation_id: str,
        request_id: str,
        defender: CharacterState,
        *,
        logical_time: datetime,
    ) -> SparringResult:
        state = self.social.load(sparring_social_scope_id(defender.id))
        request = state.requests.get(request_id) if state is not None else None
        if request is None or request.kind_id != SPARRING_REQUEST_ID:
            return SparringResult("unknown", failure_message="找不到这份切磋请求")
        if request.recipient_id != defender.id:
            return SparringResult("forbidden", request=request, failure_message="只有应战者可以接受切磋")
        if logical_time >= request.expires_at:
            return SparringResult("expired", request=request, failure_message="切磋请求已经过期")
        challenger = self.characters.load_character(request.sender_id)
        if challenger is None:
            return SparringResult("unavailable", request=request, failure_message="挑战者角色已不存在")
        report_id = self._report_id(request.id)
        existing = self.battle_reports.reference(report_id)
        if request.status is SocialRequestStatus.ACCEPTED and existing is not None:
            return SparringResult("replayed", request, existing, challenger, defender)
        if (
            challenger.resources[HEALTH_CURRENT] <= 0
            or defender.resources[HEALTH_CURRENT] <= 0
        ):
            return SparringResult(
                "unavailable",
                request,
                failure_message="双方血气必须大于 0 才能切磋",
            )
        if request.status is SocialRequestStatus.ACCEPTED:
            accepted = request
        elif request.status is SocialRequestStatus.PENDING:
            accepted = self._resolve(
                f"{operation_id}:accept",
                request,
                SocialRequestStatus.ACCEPTED,
                defender,
                logical_time=logical_time,
            )
            if accepted is None:
                return SparringResult("failed", request=request, failure_message="切磋请求已被其他操作处理")
        else:
            return SparringResult("terminal", request=request, failure_message="切磋请求已经处理")
        try:
            challenger_inventory, challenger_loadout, challenger_dimension, challenger_roster = self._snapshot_bundle(challenger.id)
            defender_inventory, defender_loadout, defender_dimension, defender_roster = self._snapshot_bundle(defender.id)
            outcome = self.simulator.simulate(
                challenger,
                challenger_inventory,
                challenger_loadout,
                challenger_roster,
                defender,
                defender_inventory,
                defender_loadout,
                defender_roster,
                battle_id=f"battle:{request.id}",
                context=_context(f"{request.id}:battle", logical_time, "battle"),
            )
            report = self._capture_report(
                request,
                challenger,
                defender,
                challenger_dimension,
                defender_dimension,
                challenger_roster,
                defender_roster,
                outcome,
                logical_time,
            )
        except Exception as exc:
            return SparringResult("failed", accepted, failure_message=f"切磋战斗失败：{exc}")
        return SparringResult(
            "accepted",
            accepted,
            report,
            challenger,
            defender,
            None if outcome.draw else (
                challenger.id if outcome.challenger_victory else defender.id
            ),
            outcome.draw,
            outcome.turns,
        )

    def _resolve(self, operation_id, request, status, defender, *, logical_time):
        scope_id = sparring_social_scope_id(defender.id)
        state = self.social.load(scope_id)
        if state is None:
            return None
        outcome = self.social.execute(
            scope_id,
            SocialCommand(
                operation_id,
                defender.id,
                state.revision,
                ResolveSocialRequest(request.id, status),
            ),
            context=_context(operation_id, logical_time, "resolve"),
        )
        if outcome.failure or outcome.value is None:
            return None
        return outcome.value.execution.state.requests[request.id]

    def _snapshot_bundle(self, character_id):
        with self.database.unit_of_work(write=False) as uow:
            inventory = self.snapshots.require(
                uow,
                self.storage.inventory,
                character_id,
                InventoryState,
            )
            loadout = self.snapshots.require(
                uow,
                self.storage.loadout,
                character_id,
                LoadoutState,
            )
            dimension = self.snapshots.require(
                uow,
                CHARACTER_WORLD_AGGREGATE,
                character_id,
                CharacterWorldState,
            )
            roster = self.snapshots.load(
                uow,
                self.storage.companion_roster,
                character_id,
                CompanionRosterState,
            ) or CompanionRosterState(character_id)
        return inventory, loadout, dimension, roster

    def _capture_report(
        self,
        request,
        challenger,
        defender,
        challenger_dimension,
        defender_dimension,
        challenger_roster,
        defender_roster,
        outcome,
        logical_time,
    ):
        skin = self.world_views.require(challenger_dimension.world_id)
        labels = {
            challenger.id: (challenger.name, "challenger"),
            defender.id: (defender.name, "defender"),
        }
        for roster, companion_id, role in (
            (challenger_roster, outcome.challenger_companion_id, "challenger_companion"),
            (defender_roster, outcome.defender_companion_id, "defender_companion"),
        ):
            if companion_id is None:
                continue
            companion = roster.instances[companion_id]
            labels[companion_id] = (
                self.content.companions.require_definition(companion.definition_id).name,
                role,
            )
        initial = outcome.trace.initial_frame.state
        final = outcome.trace.final_frame.state
        initial_participants = tuple(
            capture_battle_participant(
                initial.entities[entity_id],
                labels[entity_id][0],
                labels[entity_id][1],
                self.content.catalog.enemy_projector.attributes,
            )
            for entity_id in labels
        )
        final_participants = tuple(
            capture_battle_participant(
                final.entities[entity_id],
                labels[entity_id][0],
                labels[entity_id][1],
                self.content.catalog.enemy_projector.attributes,
            )
            for entity_id in labels
        )
        if outcome.draw:
            result_text = "切磋平局"
        else:
            winner = challenger.name if outcome.challenger_victory else defender.name
            result_text = f"{winner} 切磋获胜"
        draft = BattleReportDraft(
            report_id=self._report_id(request.id),
            mode_id="battle.mode.sparring",
            presentation_skin_id=str(skin.skin.id),
            presentation_skin_version=skin.skin.version,
            content_fingerprint=self.content.catalog.report.content_fingerprint,
            summary=BattleReportSummary(
                f"切磋·{challenger.name} vs {defender.name}",
                result_text,
                (
                    f"战斗行动: {outcome.turns}",
                    f"{challenger.name}余血: {outcome.challenger_health_after:.0f}",
                    f"{defender.name}余血: {outcome.defender_health_after:.0f}",
                ),
            ),
            segment=BattleReportSegmentDraft(
                segment_id=request.id,
                title=f"{challenger.name} vs {defender.name}",
                participants=initial_participants,
                events=outcome.trace.events,
                outcome=result_text,
                started_at=logical_time,
                finished_at=logical_time,
                final_participants=final_participants,
                transitions=capture_battle_transitions(
                    outcome.trace,
                    labels,
                    self.content.catalog.enemy_projector.attributes,
                ),
            ),
        )
        return self.battle_reports.capture(draft)

    @staticmethod
    def _report_id(request_id: str) -> str:
        return f"battle-report:sparring:{request_id}"


def _context(trace_id: str, logical_time: datetime, phase: str) -> RuleContext:
    return RuleContext(
        trace_id=trace_id,
        rule_version=SPARRING_RULE_VERSION,
        ruleset=Ruleset(f"ruleset.sparring.{phase}", TagSet.of("scene.sparring")),
        logical_time=logical_time,
        random=SeededRandomSource(trace_id),
    )


def sparring_social_scope_id(recipient_id: str) -> str:
    normalized = str(recipient_id or "").strip()
    if not normalized:
        raise ValueError("切磋社会请求缺少接收角色")
    return f"{SOCIAL_SCOPE_PREFIX}{normalized}"


__all__ = [
    "SparringFeature",
    "SparringRequestResult",
    "SparringResult",
    "SparringStorageKinds",
    "sparring_social_scope_id",
]
