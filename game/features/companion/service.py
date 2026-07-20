"""伙伴秘境、捕获、配装绑定和放生的联合事务。"""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256

from game.content.catalog.item import (
    COMPANION_SANCTUARY_ITEM_COMPONENT_ID,
    CompanionSanctuaryItemComponent,
)
from game.core.gameplay import (
    ActionSlotKind,
    ActionState,
    CharacterState,
    ConsumeStack,
    HEALTH_CURRENT,
    InventoryState,
    InventoryTransaction,
    LoadoutState,
    RuleContext,
    Ruleset,
    SPIRIT_CURRENT,
    SeededRandomSource,
)
from game.rules.battle_report import (
    BattleReportDraft,
    BattleReportSegmentDraft,
    BattleReportSummary,
    capture_battle_participant,
    capture_battle_transitions,
)
from game.rules.character import CharacterDimensionState
from game.rules.companion import (
    COMPANION_RULESET_VERSION,
    CompanionEngine,
    CompanionRosterState,
    CompanionRuleError,
    CompanionSanctuaryState,
)
from game.rules.exploration import ExplorationState, ExplorationStatus

from .battle import CompanionSanctuaryBattleSimulator
from .models import (
    CompanionOperationReceipt,
    CompanionOperationResult,
    CompanionStorageKinds,
    CompanionView,
)


class CompanionFeature:
    """伙伴领域唯一写入口；命令组件不能直接操作快照。"""

    def __init__(
        self,
        database,
        content,
        world_views,
        snapshots,
        inventory_engine,
        battle_reports,
        engine: CompanionEngine,
        battle: CompanionSanctuaryBattleSimulator,
        storage: CompanionStorageKinds,
    ) -> None:
        self.database = database
        self.content = content
        self.world_views = world_views
        self.snapshots = snapshots
        self.inventory_engine = inventory_engine
        self.battle_reports = battle_reports
        self.engine = engine
        self.battle = battle
        self.storage = storage

    def view(self, character_id: str, *, logical_time) -> CompanionView:
        with self.database.unit_of_work() as uow:
            roster = self._load_roster(uow, character_id)
            sanctuary = self.snapshots.load(
                uow,
                self.storage.sanctuary,
                character_id,
                CompanionSanctuaryState,
            )
            if sanctuary is not None:
                current = self.engine.expire(sanctuary, logical_time=logical_time)
                if current is not sanctuary:
                    self.snapshots.update(
                        uow,
                        self.storage.sanctuary,
                        character_id,
                        sanctuary,
                        current,
                        logical_time,
                    )
                    sanctuary = current
                    uow.commit()
            return CompanionView(roster, sanctuary)

    def open_sanctuary(
        self,
        operation_id: str,
        character: CharacterState,
        dimension: CharacterDimensionState,
        item_asset_id: str,
        *,
        logical_time,
    ) -> CompanionOperationResult:
        fingerprint = _fingerprint(
            "open",
            character.id,
            dimension.skin_id,
            item_asset_id,
        )
        context = _context(operation_id, logical_time, "open")
        with self.database.unit_of_work() as uow:
            replay = self._replay(uow, operation_id, fingerprint, character.id)
            if replay is not None:
                return self._replayed_result(uow, replay)
            roster, roster_exists = self._load_roster_entry(uow, character.id)
            previous = self.snapshots.load(
                uow,
                self.storage.sanctuary,
                character.id,
                CompanionSanctuaryState,
            )
            inventory = self.snapshots.require(
                uow,
                self.storage.inventory,
                character.id,
                InventoryState,
            )
            try:
                item_asset = inventory.asset(item_asset_id)
            except KeyError:
                return CompanionOperationResult(
                    "item_unknown",
                    roster,
                    previous,
                    failure_message="找不到要使用的万灵引",
                )
            if inventory.owner_of(item_asset.id) != character.id:
                return CompanionOperationResult(
                    "item_forbidden",
                    roster,
                    previous,
                    failure_message="万灵引不属于当前角色",
                )
            definition = self.content.catalog.items.require(item_asset.definition_id)
            component = definition.components.get(COMPANION_SANCTUARY_ITEM_COMPONENT_ID)
            if not isinstance(component, CompanionSanctuaryItemComponent):
                return CompanionOperationResult(
                    "item_invalid",
                    roster,
                    previous,
                    failure_message="这件物品不能开启伙伴秘境",
                )
            if inventory.available_quantity(item_asset.id) < component.quantity:
                return CompanionOperationResult(
                    "item_unavailable",
                    roster,
                    previous,
                    failure_message="万灵引当前被其他流程占用",
                )
            try:
                sanctuary = self.engine.open_sanctuary(
                    roster,
                    previous,
                    session_id=f"companion-sanctuary:{operation_id}",
                    world_skin_id=dimension.skin_id,
                    character_level=_character_level(character),
                    logical_time=logical_time,
                    random=context.random,
                )
            except (CompanionRuleError, KeyError) as exc:
                return CompanionOperationResult(
                    getattr(exc, "code", "world_unavailable"),
                    roster,
                    previous,
                    failure_message=str(exc),
                )
            inventory_outcome = self.inventory_engine.execute(
                InventoryTransaction(
                    f"{operation_id}:inventory",
                    character.id,
                    "companion.sanctuary.open",
                    (ConsumeStack(item_asset.id, component.quantity),),
                ),
                state=inventory,
                context=context,
            )
            if inventory_outcome.failure or inventory_outcome.value is None:
                return CompanionOperationResult(
                    "item_consume_failed",
                    roster,
                    previous,
                    failure_message=(
                        inventory_outcome.failure.message
                        if inventory_outcome.failure
                        else "万灵引扣除失败"
                    ),
                )
            self.snapshots.update(
                uow,
                self.storage.inventory,
                character.id,
                inventory,
                inventory_outcome.value.state,
                logical_time,
            )
            if not roster_exists:
                self.snapshots.insert(
                    uow,
                    self.storage.roster,
                    character.id,
                    roster,
                    logical_time,
                )
            if previous is None:
                self.snapshots.insert(
                    uow,
                    self.storage.sanctuary,
                    character.id,
                    sanctuary,
                    logical_time,
                )
            else:
                self.snapshots.update(
                    uow,
                    self.storage.sanctuary,
                    character.id,
                    previous,
                    sanctuary,
                    logical_time,
                )
            receipt = CompanionOperationReceipt(
                operation_id,
                character.id,
                "open",
                sanctuary.session_id,
            )
            self._commit_receipt(uow, receipt, fingerprint, logical_time)
            uow.commit()
            return CompanionOperationResult("opened", roster, sanctuary)

    def hunt(
        self,
        operation_id: str,
        character_id: str,
        trace_index: int,
        *,
        logical_time,
    ) -> CompanionOperationResult:
        fingerprint = _fingerprint("hunt", character_id, trace_index)
        context = _context(operation_id, logical_time, "hunt")
        with self.database.unit_of_work() as uow:
            replay = self._replay(uow, operation_id, fingerprint, character_id)
            if replay is not None:
                return self._replayed_result(uow, replay)
            roster = self._load_roster(uow, character_id)
            sanctuary = self.snapshots.load(
                uow,
                self.storage.sanctuary,
                character_id,
                CompanionSanctuaryState,
            )
            if sanctuary is None:
                return CompanionOperationResult(
                    "sanctuary_missing",
                    roster,
                    failure_message="当前没有已经开启的伙伴秘境",
                )
            dimension = self.snapshots.require(
                uow,
                self.storage.dimension,
                character_id,
                CharacterDimensionState,
            )
            if dimension.skin_id != sanctuary.world_skin_id:
                return CompanionOperationResult(
                    "wrong_world",
                    roster,
                    sanctuary,
                    failure_message="必须返回开启秘境的世界才能继续追踪",
                )
            occupied = self._main_action_occupied(uow, character_id)
            if occupied:
                return CompanionOperationResult(
                    "main_action_occupied",
                    roster,
                    sanctuary,
                    failure_message="请先结束当前主要行动",
                )
            character = self.snapshots.require(
                uow,
                self.storage.character,
                character_id,
                CharacterState,
            )
            if character.resources[HEALTH_CURRENT] <= 0:
                return CompanionOperationResult(
                    "health_empty",
                    roster,
                    sanctuary,
                    failure_message="当前血气已经归零，恢复后才能追踪伙伴",
                )
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
            try:
                selected = self.engine.select_trace(
                    sanctuary,
                    trace_index,
                    logical_time=logical_time,
                )
            except CompanionRuleError as exc:
                return CompanionOperationResult(
                    exc.code,
                    roster,
                    sanctuary,
                    failure_message=str(exc),
                )
            target = selected.selected_trace()
            if target is None:
                raise RuntimeError("伙伴追猎缺少已锁定踪迹")
            battle = self.battle.simulate(
                selected.session_id,
                target,
                character=character,
                inventory=inventory,
                loadout=loadout,
                roster=roster,
                context=context,
            )
            resources = dict(character.resources)
            resources[HEALTH_CURRENT] = battle.player_health_after
            resources[SPIRIT_CURRENT] = battle.player_spirit_after
            next_character = character
            if resources != dict(character.resources):
                next_character = replace(
                    character,
                    resources=resources,
                    revision=character.revision + 1,
                )
                self.snapshots.update(
                    uow,
                    self.storage.character,
                    character_id,
                    character,
                    next_character,
                    logical_time,
                )
            companion = None
            if battle.victory:
                next_roster, next_sanctuary, companion = self.engine.capture(
                    roster,
                    selected,
                    logical_time=logical_time,
                )
                self.snapshots.update(
                    uow,
                    self.storage.roster,
                    character_id,
                    roster,
                    next_roster,
                    logical_time,
                )
            else:
                next_roster = roster
                next_sanctuary = self.engine.record_failed_attempt(
                    selected,
                    logical_time=logical_time,
                )
            next_sanctuary = replace(
                next_sanctuary,
                revision=sanctuary.revision + 1,
            )
            self.snapshots.update(
                uow,
                self.storage.sanctuary,
                character_id,
                sanctuary,
                next_sanctuary,
                logical_time,
            )
            report = self.battle_reports.capture_in_uow(
                uow,
                self._battle_report(
                    character,
                    roster,
                    loadout,
                    selected,
                    battle,
                    logical_time,
                ),
            )
            receipt = CompanionOperationReceipt(
                operation_id,
                character_id,
                "hunt",
                selected.session_id,
                companion.id if companion is not None else "",
                report.report_id,
            )
            self._commit_receipt(uow, receipt, fingerprint, logical_time)
            uow.commit()
            return CompanionOperationResult(
                "captured" if companion is not None else "defeated",
                next_roster,
                next_sanctuary,
                companion,
                report,
                battle,
            )

    def bind(
        self,
        operation_id: str,
        character_id: str,
        reference: str,
        *,
        allow_transfer: bool,
        expected_revision: int | None = None,
        logical_time,
    ) -> CompanionOperationResult:
        fingerprint = _fingerprint(
            "bind",
            character_id,
            reference,
            int(allow_transfer),
            expected_revision,
        )
        with self.database.unit_of_work() as uow:
            replay = self._replay(uow, operation_id, fingerprint, character_id)
            if replay is not None:
                return self._replayed_result(uow, replay)
            roster = self._load_roster(uow, character_id)
            if expected_revision is not None and roster.revision != expected_revision:
                return CompanionOperationResult(
                    "stale",
                    roster,
                    failure_message="伙伴名册已经变化，请重新选择出战伙伴",
                )
            companion = roster.by_reference(reference)
            if companion is None:
                return CompanionOperationResult(
                    "companion_unknown",
                    roster,
                    failure_message="找不到这名伙伴",
                )
            loadout = self.snapshots.require(
                uow,
                self.storage.loadout,
                character_id,
                LoadoutState,
            )
            if loadout.active_preset_id is None:
                return CompanionOperationResult(
                    "preset_missing",
                    roster,
                    companion=companion,
                    failure_message="当前没有激活配装",
                )
            previous_preset = roster.preset_for_companion(companion.id)
            if (
                previous_preset is not None
                and previous_preset != loadout.active_preset_id
                and not allow_transfer
            ):
                return CompanionOperationResult(
                    "transfer_required",
                    roster,
                    companion=companion,
                    previous_preset_id=str(previous_preset),
                )
            next_roster = self.engine.bind(
                roster,
                companion.id,
                loadout.active_preset_id,
                allow_transfer=allow_transfer,
            )
            if next_roster is roster:
                return CompanionOperationResult("already_bound", roster, companion=companion)
            self.snapshots.update(
                uow,
                self.storage.roster,
                character_id,
                roster,
                next_roster,
                logical_time,
            )
            receipt = CompanionOperationReceipt(
                operation_id,
                character_id,
                "bind",
                companion_id=companion.id,
            )
            self._commit_receipt(uow, receipt, fingerprint, logical_time)
            uow.commit()
            return CompanionOperationResult(
                "transferred" if previous_preset is not None else "bound",
                next_roster,
                companion=companion,
                previous_preset_id=(str(previous_preset) if previous_preset else None),
            )

    def unbind_current(
        self,
        operation_id: str,
        character_id: str,
        *,
        logical_time,
    ) -> CompanionOperationResult:
        fingerprint = _fingerprint("unbind", character_id)
        with self.database.unit_of_work() as uow:
            replay = self._replay(uow, operation_id, fingerprint, character_id)
            if replay is not None:
                return self._replayed_result(uow, replay)
            roster = self._load_roster(uow, character_id)
            loadout = self.snapshots.require(
                uow,
                self.storage.loadout,
                character_id,
                LoadoutState,
            )
            if loadout.active_preset_id is None:
                return CompanionOperationResult("preset_missing", roster)
            companion = roster.companion_for_preset(loadout.active_preset_id)
            next_roster = self.engine.unbind(roster, loadout.active_preset_id)
            if next_roster is roster:
                return CompanionOperationResult("already_unbound", roster)
            self.snapshots.update(
                uow,
                self.storage.roster,
                character_id,
                roster,
                next_roster,
                logical_time,
            )
            receipt = CompanionOperationReceipt(
                operation_id,
                character_id,
                "unbind",
                companion_id=companion.id if companion is not None else "",
            )
            self._commit_receipt(uow, receipt, fingerprint, logical_time)
            uow.commit()
            return CompanionOperationResult("unbound", next_roster, companion=companion)

    def release(
        self,
        operation_id: str,
        character_id: str,
        reference: str,
        expected_revision: int,
        *,
        logical_time,
    ) -> CompanionOperationResult:
        fingerprint = _fingerprint(
            "release",
            character_id,
            reference,
            expected_revision,
        )
        with self.database.unit_of_work() as uow:
            replay = self._replay(uow, operation_id, fingerprint, character_id)
            if replay is not None:
                return self._replayed_result(uow, replay)
            roster = self._load_roster(uow, character_id)
            if roster.revision != expected_revision:
                return CompanionOperationResult(
                    "stale",
                    roster,
                    failure_message="伙伴名册已经变化，请重新确认放生",
                )
            companion = roster.by_reference(reference)
            if companion is None:
                return CompanionOperationResult(
                    "companion_unknown",
                    roster,
                    failure_message="找不到要放生的伙伴",
                )
            next_roster = self.engine.release(roster, companion.id)
            self.snapshots.update(
                uow,
                self.storage.roster,
                character_id,
                roster,
                next_roster,
                logical_time,
            )
            receipt = CompanionOperationReceipt(
                operation_id,
                character_id,
                "release",
                companion_id=companion.id,
            )
            self._commit_receipt(uow, receipt, fingerprint, logical_time)
            uow.commit()
            return CompanionOperationResult("released", next_roster, companion=companion)

    def abandon(
        self,
        operation_id: str,
        character_id: str,
        expected_revision: int,
        *,
        logical_time,
    ) -> CompanionOperationResult:
        fingerprint = _fingerprint("abandon", character_id, expected_revision)
        with self.database.unit_of_work() as uow:
            replay = self._replay(uow, operation_id, fingerprint, character_id)
            if replay is not None:
                return self._replayed_result(uow, replay)
            roster = self._load_roster(uow, character_id)
            sanctuary = self.snapshots.load(
                uow,
                self.storage.sanctuary,
                character_id,
                CompanionSanctuaryState,
            )
            if sanctuary is None:
                return CompanionOperationResult("sanctuary_missing", roster)
            if sanctuary.revision != expected_revision:
                return CompanionOperationResult("stale", roster, sanctuary)
            next_sanctuary = self.engine.abandon(
                sanctuary,
                logical_time=logical_time,
            )
            if next_sanctuary is sanctuary:
                return CompanionOperationResult("sanctuary_inactive", roster, sanctuary)
            self.snapshots.update(
                uow,
                self.storage.sanctuary,
                character_id,
                sanctuary,
                next_sanctuary,
                logical_time,
            )
            receipt = CompanionOperationReceipt(
                operation_id,
                character_id,
                "abandon",
                sanctuary.session_id,
            )
            self._commit_receipt(uow, receipt, fingerprint, logical_time)
            uow.commit()
            return CompanionOperationResult("abandoned", roster, next_sanctuary)

    def _battle_report(
        self,
        character,
        roster,
        loadout,
        sanctuary,
        battle,
        logical_time,
    ) -> BattleReportDraft:
        target_trace = sanctuary.selected_trace()
        if target_trace is None:
            raise RuntimeError("伙伴战报缺少追踪目标")
        target_species = self.content.companions.species.require(
            target_trace.definition_id
        )
        labels = {character.id: (character.name, "player")}
        own_companion = roster.companion_for_preset(loadout.active_preset_id)
        if own_companion is not None:
            own_species = self.content.companions.species.require(
                own_companion.definition_id
            )
            labels[own_companion.id] = (own_species.name, "companion")
        labels[battle.target_id] = (f"野生·{target_species.name}", "target")
        initial = battle.trace.initial_frame.state
        final = battle.trace.final_frame.state
        participant_ids = tuple(initial.participants)
        attributes = self.content.catalog.enemy_projector.attributes
        initial_participants = tuple(
            capture_battle_participant(
                initial.entities[entity_id],
                labels[entity_id][0],
                labels[entity_id][1],
                attributes,
            )
            for entity_id in participant_ids
        )
        final_participants = tuple(
            capture_battle_participant(
                final.entities[entity_id],
                labels[entity_id][0],
                labels[entity_id][1],
                attributes,
            )
            for entity_id in participant_ids
        )
        view = self.world_views.require(sanctuary.world_skin_id)
        outcome = "追猎成功" if battle.victory else "追猎失败"
        report_id = (
            f"battle-report:companion:{sanctuary.session_id}:"
            f"attempt:{sanctuary.attempt_count + 1}"
        )
        return BattleReportDraft(
            report_id=report_id,
            mode_id="battle.mode.companion_sanctuary",
            presentation_skin_id=str(view.skin.id),
            presentation_skin_version=view.skin.version,
            content_fingerprint=self.content.catalog.report.content_fingerprint,
            summary=BattleReportSummary(
                f"{view.projector.name('term.companion_sanctuary')}·{target_species.name}",
                outcome,
                (
                    f"战斗行动: {battle.turns}",
                    f"角色余血: {battle.player_health_after:.0f}",
                ),
            ),
            segment=BattleReportSegmentDraft(
                segment_id=f"{sanctuary.session_id}:{sanctuary.attempt_count + 1}",
                title=f"追踪 {target_species.name}",
                participants=initial_participants,
                events=battle.trace.events,
                outcome=outcome,
                started_at=logical_time,
                finished_at=logical_time,
                final_participants=final_participants,
                transitions=capture_battle_transitions(
                    battle.trace,
                    labels,
                    attributes,
                ),
            ),
        )

    def _main_action_occupied(self, uow, character_id: str) -> bool:
        action = self.snapshots.load(
            uow,
            self.storage.action,
            character_id,
            ActionState,
        )
        exploration = self.snapshots.load(
            uow,
            self.storage.exploration,
            character_id,
            ExplorationState,
        )
        return bool(
            (action is not None and action.running(ActionSlotKind.MAIN))
            or (
                exploration is not None
                and exploration.status is ExplorationStatus.RUNNING
            )
        )

    def _replay(self, uow, transaction_id, fingerprint, actor_id):
        committed = uow.load_transaction(transaction_id)
        if committed is None:
            return None
        if committed.fingerprint != fingerprint or committed.scope_id != actor_id:
            raise ValueError(f"同一伙伴事务 ID 对应不同内容: {transaction_id}")
        return self.snapshots.codec.loads(
            committed.receipt_payload,
            CompanionOperationReceipt,
        )

    def _replayed_result(self, uow, receipt):
        roster = self._load_roster(uow, receipt.actor_id)
        sanctuary = self.snapshots.load(
            uow,
            self.storage.sanctuary,
            receipt.actor_id,
            CompanionSanctuaryState,
        )
        companion = roster.instances.get(receipt.companion_id)
        report = (
            self.battle_reports.reference(receipt.battle_report_id)
            if receipt.battle_report_id
            else None
        )
        status = {
            "open": "opened",
            "hunt": "captured" if companion is not None else "defeated",
            "bind": "bound",
            "unbind": "unbound",
            "release": "released",
            "abandon": "abandoned",
        }[receipt.operation]
        return CompanionOperationResult(
            status,
            roster,
            sanctuary,
            companion,
            report,
            replayed=True,
        )

    def _commit_receipt(self, uow, receipt, fingerprint, logical_time):
        uow.insert_transaction(
            receipt.transaction_id,
            fingerprint,
            receipt.actor_id,
            self.snapshots.codec.dumps(receipt),
            logical_time.isoformat(),
        )

    def _load_roster(self, uow, character_id: str) -> CompanionRosterState:
        return self._load_roster_entry(uow, character_id)[0]

    def _load_roster_entry(self, uow, character_id: str):
        roster = self.snapshots.load(
            uow,
            self.storage.roster,
            character_id,
            CompanionRosterState,
        )
        return (roster or CompanionRosterState(character_id), roster is not None)


def _character_level(character: CharacterState) -> int:
    return next(iter(character.progressions.values())).level


def _context(trace_id: str, logical_time, phase: str) -> RuleContext:
    return RuleContext(
        trace_id,
        COMPANION_RULESET_VERSION,
        Ruleset(
            f"ruleset.companion.{phase}",
        ),
        logical_time,
        SeededRandomSource(trace_id),
    )


def _fingerprint(*values: object) -> str:
    payload = "\0".join(str(value) for value in values)
    return sha256(payload.encode("utf-8")).hexdigest()


__all__ = ["CompanionFeature"]
