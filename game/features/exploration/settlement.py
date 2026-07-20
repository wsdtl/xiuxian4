"""持续探险批次的跨领域原子结算。"""

from dataclasses import replace
from datetime import datetime

from game.content.catalog import CHARACTER_LEVEL_PROGRESSION_ID
from game.core.gameplay import (
    HEALTH_CURRENT,
    HEALTH_MAXIMUM,
    SPIRIT_CURRENT,
    SPIRIT_MAXIMUM,
    CharacterState,
    InventoryState,
    LoadoutState,
    LootRollCommand,
    LootState,
    RewardClaimState,
    RewardExpectations,
    RewardSettlement,
    RuleContext,
    Ruleset,
    SeededRandomSource,
    WeaponState,
)
from game.rules.character import (
    CHARACTER_SETTINGS_AGGREGATE,
    CharacterSettingsState,
    PRIMARY_LEDGER_ID,
)
from game.rules.companion import CompanionRosterState
from game.rules.encounter import EnemyEncounterGenerator
from game.rules.equipment import (
    EQUIPMENT_SET_GUARANTEE_AGGREGATE,
    EquipmentSetGuaranteeState,
    consume_equipment_set_guarantee,
)
from game.rules.exploration import (
    EXPLORATION_AGGREGATE,
    EXPLORATION_RULESET_VERSION,
    ExplorationBatchPlanner,
    ExplorationBatchResult,
    ExplorationBattleSimulator,
    ExplorationState,
    ExplorationStatus,
    ExplorationStopReason,
    record_batch,
    stop_exploration,
)
from game.rules.battle_report import (
    BattleReportDraft,
    BattleReportSegmentDraft,
    BattleReportSummary,
    capture_battle_participant,
    capture_battle_round_states,
    capture_battle_turn_states,
    capture_battle_transitions,
)

from .medicine import ExplorationMedicineService
from .models import (
    MAX_CATCH_UP_BATCHES,
    MAX_DISCOVERABLE_EXPLORATIONS,
    ExplorationOperationResult,
    ExplorationStorageKinds,
    exploration_battle_report_id,
)
from .rewards import ExplorationRewardFactory, available_backpack_space


class ExplorationSettlementService:
    """每个到期批次在一个工作单元内全部成功或回滚。"""

    def __init__(
        self,
        database,
        content,
        snapshots,
        rewards,
        inventory_engine,
        player_lineup,
        battle_reports,
        storage: ExplorationStorageKinds,
        reward_keys_factory,
    ) -> None:
        self.database = database
        self.content = content
        self.snapshots = snapshots
        self.rewards = rewards
        self.battle_reports = battle_reports
        self.storage = storage
        self.reward_keys_factory = reward_keys_factory
        catalog = content.catalog
        encounters = EnemyEncounterGenerator(
            catalog.enemies,
            content_version=catalog.report.content_fingerprint,
        )
        self.planner = ExplorationBatchPlanner(content.exploration_regions, encounters)
        self.battles = ExplorationBattleSimulator(catalog, player_lineup)
        self.reward_factory = ExplorationRewardFactory(content)
        self.medicine = ExplorationMedicineService(
            content,
            snapshots,
            inventory_engine,
            storage,
        )

    def settle_due(
        self,
        character_id: str,
        *,
        logical_time: datetime,
        limit: int = MAX_CATCH_UP_BATCHES,
    ) -> ExplorationOperationResult:
        completed: list[ExplorationBatchResult] = []
        for _ in range(limit):
            result = self._settle_next(character_id, logical_time=logical_time)
            if result is None:
                break
            completed.append(result)
        return ExplorationOperationResult(
            "settled",
            self.load_state(character_id),
            tuple(completed),
        )

    def settle_all_due(
        self,
        *,
        logical_time: datetime,
        limit: int = MAX_DISCOVERABLE_EXPLORATIONS,
    ) -> int:
        with self.database.unit_of_work(write=False) as uow:
            states = self.snapshots.list(
                uow,
                EXPLORATION_AGGREGATE,
                ExplorationState,
                limit=limit,
            )
        settled = 0
        for state in states:
            if state.status is not ExplorationStatus.RUNNING or state.next_batch_at > logical_time:
                continue
            result = self.settle_due(
                state.character_id,
                logical_time=logical_time,
                limit=MAX_CATCH_UP_BATCHES,
            )
            settled += len(result.batches)
        return settled

    def load_state(self, character_id: str) -> ExplorationState | None:
        with self.database.unit_of_work(write=False) as uow:
            return self.snapshots.load(
                uow,
                EXPLORATION_AGGREGATE,
                character_id,
                ExplorationState,
            )

    def _settle_next(
        self,
        character_id: str,
        *,
        logical_time: datetime,
    ) -> ExplorationBatchResult | None:
        with self.database.unit_of_work() as uow:
            state = self.snapshots.load(
                uow, EXPLORATION_AGGREGATE, character_id, ExplorationState
            )
            if (
                state is None
                or state.status is not ExplorationStatus.RUNNING
                or state.next_batch_at > logical_time
            ):
                return None
            resolved_at = state.next_batch_at
            batch_index = state.batch_index + 1
            context = _context(
                f"{state.session_id}:batch:{batch_index}",
                resolved_at,
            )
            character = self.snapshots.require(
                uow, self.storage.character, character_id, CharacterState
            )
            inventory = self.snapshots.require(
                uow, self.storage.inventory, character_id, InventoryState
            )
            loadout = self.snapshots.require(
                uow, self.storage.loadout, character_id, LoadoutState
            )
            roster = self.snapshots.load(
                uow,
                self.storage.companion_roster,
                character_id,
                CompanionRosterState,
            ) or CompanionRosterState(character_id)
            settings = self.snapshots.require(
                uow,
                CHARACTER_SETTINGS_AGGREGATE,
                character_id,
                CharacterSettingsState,
            )
            level = character.progressions[CHARACTER_LEVEL_PROGRESSION_ID].level
            plan = self.planner.plan(
                session_id=state.session_id,
                batch_index=batch_index,
                region_id=state.region_id,
                character_level=level,
                random=context.random,
            )
            victory = False
            draw = False
            battle = None
            health_after = character.resources[HEALTH_CURRENT]
            spirit_after = character.resources[SPIRIT_CURRENT]
            health_maximum = float(character.core_attributes[HEALTH_MAXIMUM])
            spirit_maximum = float(character.core_attributes[SPIRIT_MAXIMUM])
            if plan.encounter is not None:
                battle = self.battles.simulate(
                    plan,
                    character=character,
                    inventory=inventory,
                    loadout=loadout,
                    roster=roster,
                    context=context,
                )
                victory = battle.victory
                draw = battle.draw
                health_after = battle.health_after
                spirit_after = battle.spirit_after
                health_maximum = battle.health_maximum
                spirit_maximum = battle.spirit_maximum

            character_experience = 0
            weapon_experience = 0
            weapon_drops = 0
            equipment_drops = 0
            trophy_drops = 0
            medicine_drops = 0
            draw_ticket_drops = 0
            trophy_value = 0
            reward_references = []
            medicines_used = []
            if victory and plan.encounter is not None:
                quotes = tuple(
                    self.content.catalog.enemy_threat.reward_quote(enemy)
                    for enemy in plan.encounter.enemies
                )
                character_experience = sum(value.character_experience for value in quotes)
                weapon_experience = sum(value.weapon_experience for value in quotes)
                rolls = sum(value.loot_rolls for value in quotes)
                loot_state = self.snapshots.require(
                    uow, self.storage.loot, character_id, LootState
                )
                region = self.content.exploration_regions.require(state.region_id)
                loot_outcome = self.content.catalog.loot_engine.roll(
                    LootRollCommand(
                        f"{context.trace_id}:loot",
                        character_id,
                        region.loot_table_id(plan.encounter_kind.value),
                        loot_state.revision,
                        rolls,
                        plan.loot_modifiers,
                    ),
                    state=loot_state,
                    context=context,
                )
                if loot_outcome.failure or loot_outcome.value is None:
                    raise RuntimeError(
                        loot_outcome.failure.message if loot_outcome.failure else "探险掉落失败"
                    )
                equipment_set_guarantee = self.snapshots.load(
                    uow,
                    EQUIPMENT_SET_GUARANTEE_AGGREGATE,
                    character_id,
                    EquipmentSetGuaranteeState,
                )
                reward_build = self.reward_factory.build(
                    loot_outcome.value.receipt.awards,
                    plan=plan,
                    character=character,
                    inventory=inventory,
                    loadout=loadout,
                    character_experience=character_experience,
                    weapon_experience=weapon_experience,
                    equipment_set_guarantee_charges=(
                        equipment_set_guarantee.charges
                        if equipment_set_guarantee is not None
                        else 0
                    ),
                    context=context,
                )
                remaining_space = available_backpack_space(
                    inventory,
                    self.content.catalog.items,
                )
                if (
                    remaining_space is not None
                    and reward_build.backpack_space > remaining_space
                ):
                    stopped = stop_exploration(
                        state,
                        ExplorationStopReason.CAPACITY_FULL,
                        logical_time=resolved_at,
                    )
                    self.snapshots.update(
                        uow,
                        EXPLORATION_AGGREGATE,
                        character_id,
                        state,
                        stopped,
                        resolved_at,
                    )
                    uow.commit()
                    return None
                weapon_drops = reward_build.weapon_drops
                equipment_drops = reward_build.equipment_drops
                trophy_drops = reward_build.trophy_drops
                medicine_drops = reward_build.medicine_drops
                draw_ticket_drops = reward_build.draw_ticket_drops
                trophy_value = reward_build.trophy_value
                reward_references = list(reward_build.references)
                self.snapshots.update(
                    uow,
                    self.storage.loot,
                    character_id,
                    loot_state,
                    loot_outcome.value.state,
                    resolved_at,
                )
                weapon_revisions = (
                    self._weapon_revisions(uow, loadout)
                    if weapon_experience > 0
                    else {}
                )
                settlement = RewardSettlement(
                    f"{context.trace_id}:reward",
                    character_id,
                    character_id,
                    "source.exploration",
                    f"{state.session_id}:{batch_index}",
                    reward_build.rewards,
                    RewardExpectations(
                        claim_revision=self._claim_revision(uow, character_id),
                        inventory_revision=(
                            inventory.revision
                            if (
                                weapon_drops
                                or equipment_drops
                                or trophy_drops
                                or medicine_drops
                                or draw_ticket_drops
                            )
                            else None
                        ),
                        character_revisions={character_id: character.revision},
                        weapon_revisions=weapon_revisions,
                    ),
                )
                keys = self.reward_keys_factory(
                    character_id,
                    PRIMARY_LEDGER_ID,
                    (character_id,),
                    tuple(weapon_revisions),
                )
                reward_outcome = self.rewards.settle_in_uow(
                    uow,
                    settlement,
                    keys,
                    context=context,
                )
                if reward_outcome.failure:
                    raise RuntimeError(reward_outcome.failure.message)
                if reward_build.equipment_set_guarantees_consumed:
                    if equipment_set_guarantee is None:
                        raise RuntimeError("装备套装保证状态缺失")
                    next_guarantee = consume_equipment_set_guarantee(
                        equipment_set_guarantee,
                        reward_build.equipment_set_guarantees_consumed,
                    )
                    self.snapshots.update(
                        uow,
                        EQUIPMENT_SET_GUARANTEE_AGGREGATE,
                        character_id,
                        equipment_set_guarantee,
                        next_guarantee,
                        resolved_at,
                    )

            current_character = self.snapshots.require(
                uow, self.storage.character, character_id, CharacterState
            )
            resources = dict(current_character.resources)
            resources[HEALTH_CURRENT] = health_after
            resources[SPIRIT_CURRENT] = spirit_after
            after_battle = current_character
            if resources != dict(current_character.resources):
                after_battle = replace(
                    current_character,
                    resources=resources,
                    revision=current_character.revision + 1,
                )
                self.snapshots.update(
                    uow,
                    self.storage.character,
                    character_id,
                    current_character,
                    after_battle,
                    resolved_at,
                )
            if victory and settings.auto_use_medicine:
                after_battle, medicines_used = self.medicine.apply(
                    uow,
                    after_battle,
                    health_maximum,
                    spirit_maximum,
                    context,
                )

            result = ExplorationBatchResult(
                plan=plan,
                resolved_at=resolved_at,
                victory=victory,
                draw=draw,
                health_after=after_battle.resources[HEALTH_CURRENT],
                spirit_after=after_battle.resources[SPIRIT_CURRENT],
                character_experience=character_experience if victory else 0,
                weapon_experience=weapon_experience if victory else 0,
                weapon_drops=weapon_drops,
                equipment_drops=equipment_drops,
                trophy_drops=trophy_drops,
                medicine_drops=medicine_drops,
                draw_ticket_drops=draw_ticket_drops,
                trophy_value=trophy_value,
                rewards=tuple(reward_references),
                medicines_used=tuple(medicines_used),
            )
            reason = None
            if plan.encounter is not None and not victory:
                reason = ExplorationStopReason.DEFEATED
            next_state = record_batch(state, result, stop_reason=reason)
            self.snapshots.update(
                uow,
                EXPLORATION_AGGREGATE,
                character_id,
                state,
                next_state,
                resolved_at,
            )
            if battle is not None:
                self.battle_reports.capture_in_uow(
                    uow,
                    self._battle_report_draft(
                        state,
                        next_state,
                        character,
                        roster,
                        battle,
                        context.trace_id,
                    ),
                )
            uow.commit()
            return result

    def _battle_report_draft(
        self,
        state: ExplorationState,
        next_state: ExplorationState,
        character: CharacterState,
        roster: CompanionRosterState,
        battle,
        segment_id: str,
    ) -> BattleReportDraft:
        plan = next_state.last_result.plan
        assert plan.encounter is not None
        enemies = tuple(plan.encounter.enemies)
        participants = [
            capture_battle_participant(
                battle.trace.initial_frame.state.entities[character.id],
                character.name,
                "player",
                self.content.catalog.enemy_projector.attributes,
            )
        ]
        labels = {character.id: (character.name, "player")}
        if battle.player_companion_id is not None:
            companion = roster.instances[battle.player_companion_id]
            companion_name = self.content.companions.species.require(
                companion.definition_id
            ).name
            participants.append(
                capture_battle_participant(
                    battle.trace.initial_frame.state.entities[companion.id],
                    companion_name,
                    "companion",
                    self.content.catalog.enemy_projector.attributes,
                )
            )
            labels[companion.id] = (companion_name, "companion")
        enemy_names = []
        for enemy in enemies:
            display = self.content.enemy_projector.enemy(enemy)
            participants.append(
                capture_battle_participant(
                    battle.trace.initial_frame.state.entities[enemy.id],
                    display.name,
                    "enemy",
                    self.content.catalog.enemy_projector.attributes,
                )
            )
            enemy_names.append(display.name)
        outcome = "探险胜利" if battle.victory else "战斗平局" if battle.draw else "探险战败"
        final_participants = [
            capture_battle_participant(
                battle.trace.final_frame.state.entities[character.id],
                character.name,
                "player",
                self.content.catalog.enemy_projector.attributes,
            )
        ]
        if battle.player_companion_id is not None:
            companion = roster.instances[battle.player_companion_id]
            companion_name = self.content.companions.species.require(
                companion.definition_id
            ).name
            final_participants.append(
                capture_battle_participant(
                    battle.trace.final_frame.state.entities[companion.id],
                    companion_name,
                    "companion",
                    self.content.catalog.enemy_projector.attributes,
                )
            )
        final_participants.extend(
            capture_battle_participant(
                battle.trace.final_frame.state.entities[enemy.id],
                self.content.enemy_projector.enemy(enemy).name,
                "enemy",
                self.content.catalog.enemy_projector.attributes,
            )
            for enemy in enemies
        )
        return BattleReportDraft(
            report_id=exploration_battle_report_id(state.session_id),
            mode_id="battle.mode.exploration",
            presentation_skin_id=str(self.content.skin.id),
            presentation_skin_version=self.content.skin.version,
            content_fingerprint=self.content.catalog.report.content_fingerprint,
            summary=BattleReportSummary(
                f"探险战报·{self.content.projector.name(state.location_id)}",
                f"{next_state.victories}胜 {next_state.defeats}负",
                (
                    f"完成批次: {next_state.completed_batches}",
                    f"累计经验: +{next_state.character_experience}",
                    f"累计掉落: 武器 {next_state.weapon_drops}, 装备 {next_state.equipment_drops}",
                ),
            ),
            segment=BattleReportSegmentDraft(
                segment_id=segment_id,
                title=f"第 {plan.batch_index} 批·{', '.join(enemy_names)}",
                participants=tuple(participants),
                events=battle.trace.events,
                outcome=outcome,
                started_at=next_state.last_result.resolved_at,
                finished_at=next_state.last_result.resolved_at,
                final_participants=tuple(final_participants),
                round_states=capture_battle_round_states(
                    battle.trace,
                    {
                        **labels,
                        **{
                            enemy.id: (
                                self.content.enemy_projector.enemy(enemy).name,
                                "enemy",
                            )
                            for enemy in enemies
                        },
                    },
                    self.content.catalog.enemy_projector.attributes,
                ),
                turn_states=capture_battle_turn_states(
                    battle.trace,
                    {
                        **labels,
                        **{
                            enemy.id: (
                                self.content.enemy_projector.enemy(enemy).name,
                                "enemy",
                            )
                            for enemy in enemies
                        },
                    },
                    self.content.catalog.enemy_projector.attributes,
                ),
                transitions=capture_battle_transitions(
                    battle.trace,
                    {
                        **labels,
                        **{
                            enemy.id: (
                                self.content.enemy_projector.enemy(enemy).name,
                                "enemy",
                            )
                            for enemy in enemies
                        },
                    },
                    self.content.catalog.enemy_projector.attributes,
                ),
            ),
        )

    def _weapon_revisions(self, uow, loadout: LoadoutState) -> dict[str, int]:
        if loadout.weapon_asset_id is None:
            return {}
        weapon = self.snapshots.require(
            uow,
            self.storage.weapon,
            loadout.weapon_asset_id,
            WeaponState,
        )
        return {weapon.asset_id: weapon.revision}

    def _claim_revision(self, uow, character_id: str) -> int:
        return self.snapshots.require(
            uow,
            self.storage.reward_claim,
            character_id,
            RewardClaimState,
        ).revision


def _context(trace_id: str, logical_time: datetime) -> RuleContext:
    return RuleContext(
        trace_id,
        EXPLORATION_RULESET_VERSION,
        Ruleset("ruleset.standard"),
        logical_time,
        SeededRandomSource(trace_id),
    )


__all__ = ["ExplorationSettlementService"]
