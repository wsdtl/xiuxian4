"""探险消耗、异步结算与休息恢复的跨领域编排。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import ceil
from typing import Mapping

from xiuxian_core.gameplay import (
    AbilityUse,
    ActionRecord,
    ActionResult,
    ActionSlotKind,
    ActionSnapshot,
    ActionState,
    ActionStatus,
    ActionTransaction,
    ClaimAction,
    CompleteAction,
    RuleContext,
    RuleEntity,
    Ruleset,
    SeededRandomSource,
    StartAction,
)
from xiuxian_core.gameplay.character import (
    COMBAT_ATTACK,
    COMBAT_DEFENSE,
    COMBAT_SPEED,
    HEALTH_CURRENT,
    HEALTH_MAXIMUM,
    SPIRIT_CURRENT,
    SPIRIT_MAXIMUM,
    ChangeCharacterResource,
    CharacterEngine,
    CharacterState,
    CharacterTransaction,
)
from xiuxian_core.gameplay.content import ContentRuntime
from xiuxian_core.gameplay.economy import LedgerState
from xiuxian_core.gameplay.inventory import InventoryState
from xiuxian_core.gameplay.loadout import LoadoutState
from xiuxian_core.gameplay.rewards import (
    CharacterExperienceReward,
    CurrencyReward,
    RewardClaimState,
    RewardExpectations,
    RewardSettlement,
    StackItemReward,
)
from xiuxian_core.persistence import (
    ACTION_AGGREGATE,
    CHARACTER_AGGREGATE,
    INVENTORY_AGGREGATE,
    LEDGER_AGGREGATE,
    REWARD_CLAIM_AGGREGATE,
    PersistedRewardSettlementService,
    RewardSettlementStorageKeys,
    SnapshotRepository,
    SqliteDatabase,
)

from ..aggregates import LOADOUT_AGGREGATE, PLAYER_PROFILE_AGGREGATE
from ..models import PlayerProfileState
from ..storage_keys import inventory_container_id, issuer_id, wallet_id
from ..world import (
    EXPLORATION_ACTION_ID,
    EXPLORATION_OUTCOME_ID,
    HERB_ITEM_ID,
    PROGRESSION_ID,
    RECOVERY_ACTION_ID,
    RECOVERY_OUTCOME_ID,
    TRIAL_ABILITY_ID,
)
from .models import (
    ActivityView,
    ExplorationClaimView,
    ExplorationStartView,
    RecoveryClaimView,
    RecoveryStartView,
)


class AdventureViolation(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class ExplorationRules:
    spirit_cost: int
    enemy_id: str
    enemy_health: int
    stone_reward: int
    experience_reward: int
    herb_reward: int


class AdventureService:
    """不依赖命令和消息协议的探险与恢复应用服务。"""

    def __init__(
        self,
        database: SqliteDatabase,
        runtime: ContentRuntime,
        snapshots: SnapshotRepository,
        character_engine: CharacterEngine,
        rewards: PersistedRewardSettlementService,
    ) -> None:
        self.database = database
        self.runtime = runtime
        self.snapshots = snapshots
        self.character_engine = character_engine
        self.rewards = rewards
        self.exploration_rules = _exploration_rules(
            runtime.actions.require(EXPLORATION_ACTION_ID).metadata
        )
        recovery = runtime.actions.require(RECOVERY_ACTION_ID)
        if recovery.metadata.get("system") != "recovery":
            raise ValueError("恢复行动缺少 recovery 内容声明")

    def activities(self, account_id: str, *, logical_time: datetime) -> tuple[ActivityView, ...]:
        with self.database.unit_of_work(write=False) as uow:
            self._profile(uow, account_id)
            actions = self.snapshots.require(uow, ACTION_AGGREGATE, account_id, ActionState)
        return tuple(
            _activity_view(record, logical_time)
            for record in sorted(actions.records.values(), key=lambda value: value.sequence)
        )

    def start_exploration(
        self,
        account_id: str,
        *,
        context: RuleContext,
    ) -> ExplorationStartView:
        with self.database.unit_of_work() as uow:
            profile = self._profile(uow, account_id)
            actions = self.snapshots.require(uow, ACTION_AGGREGATE, account_id, ActionState)
            if existing := _action_for(actions, EXPLORATION_ACTION_ID):
                character = self.snapshots.require(
                    uow, CHARACTER_AGGREGATE, profile.character_id, CharacterState
                )
                return ExplorationStartView(
                    _activity_view(existing, context.logical_time),
                    int(character.resources[SPIRIT_CURRENT]),
                    int(character.core_attributes[SPIRIT_MAXIMUM]),
                    True,
                )
            self._require_free_main_slot(actions)
            character = self.snapshots.require(
                uow, CHARACTER_AGGREGATE, profile.character_id, CharacterState
            )
            loadout = self.snapshots.require(
                uow, LOADOUT_AGGREGATE, profile.loadout_id, LoadoutState
            )
            sequence = actions.next_sequence
            action_id = f"exploration:{account_id}:{sequence}"
            character_outcome = self.character_engine.execute(
                CharacterTransaction(
                    f"cost:{action_id}",
                    profile.character_id,
                    character.revision,
                    "character.exploration_cost",
                    (
                        ChangeCharacterResource(
                            SPIRIT_CURRENT,
                            -self.exploration_rules.spirit_cost,
                            "source.exploration",
                            action_id,
                        ),
                    ),
                ),
                state=character,
                context=context,
            )
            if character_outcome.failure:
                raise AdventureViolation(
                    "adventure.spirit_insufficient",
                    "精神不足，先休息恢复后再探险",
                )
            assert character_outcome.value is not None
            snapshot = ActionSnapshot(
                context.logical_time,
                str(context.rule_version),
                self.runtime.report.content_fingerprint,
                str(getattr(context.random, "seed", context.trace_id)),
                character.revision,
                loadout.revision,
                {
                    "core_attributes": dict(character.core_attributes),
                    "resources": dict(character.resources),
                },
            )
            action_outcome = self.runtime.action_engine.execute(
                ActionTransaction(
                    f"start:{action_id}",
                    account_id,
                    actions.revision,
                    (StartAction(action_id, EXPLORATION_ACTION_ID, snapshot),),
                ),
                state=actions,
                context=context,
            )
            if action_outcome.failure:
                raise AdventureViolation(action_outcome.failure.code, action_outcome.failure.message)
            assert action_outcome.value is not None
            self.snapshots.update(
                uow,
                CHARACTER_AGGREGATE,
                profile.character_id,
                character,
                character_outcome.value.state,
                context.logical_time,
            )
            self.snapshots.update(
                uow,
                ACTION_AGGREGATE,
                account_id,
                actions,
                action_outcome.value.state,
                context.logical_time,
            )
            uow.commit()
        record = action_outcome.value.state.records[action_id]
        current_spirit = int(character_outcome.value.state.resources[SPIRIT_CURRENT])
        return ExplorationStartView(
            _activity_view(record, context.logical_time),
            current_spirit,
            int(character.core_attributes[SPIRIT_MAXIMUM]),
        )

    def claim_exploration(
        self,
        account_id: str,
        *,
        context: RuleContext,
    ) -> ExplorationClaimView:
        record = self._complete_exploration_if_due(account_id, context)
        assert record.result is not None and record.result.settlement_id is not None
        with self.database.unit_of_work(write=False) as uow:
            profile = self._profile(uow, account_id)
            inventory = self.snapshots.require(
                uow, INVENTORY_AGGREGATE, profile.inventory_id, InventoryState
            )
            ledger = self.snapshots.require(uow, LEDGER_AGGREGATE, profile.ledger_id, LedgerState)
            character = self.snapshots.require(
                uow, CHARACTER_AGGREGATE, profile.character_id, CharacterState
            )
            claims = self.snapshots.require(
                uow, REWARD_CLAIM_AGGREGATE, profile.claim_scope_id, RewardClaimState
            )
        issuer_account_id = issuer_id()
        wallet_account_id = wallet_id(account_id)
        rules = self.exploration_rules
        settlement = RewardSettlement(
            record.result.settlement_id,
            account_id,
            profile.claim_scope_id,
            "source.exploration",
            record.id,
            (
                CurrencyReward(issuer_account_id, wallet_account_id, rules.stone_reward),
                CharacterExperienceReward(
                    profile.character_id,
                    PROGRESSION_ID,
                    rules.experience_reward,
                ),
                StackItemReward(
                    f"herb:{record.id}",
                    HERB_ITEM_ID,
                    inventory_container_id(profile.character_id),
                    rules.herb_reward,
                ),
            ),
            RewardExpectations(
                claims.revision,
                inventory_revision=inventory.revision,
                ledger_account_revisions={
                    issuer_account_id: ledger.accounts[issuer_account_id].revision,
                    wallet_account_id: ledger.accounts[wallet_account_id].revision,
                },
                character_revisions={profile.character_id: character.revision},
            ),
        )
        reward_outcome = self.rewards.settle(
            settlement,
            RewardSettlementStorageKeys(
                profile.inventory_id,
                profile.ledger_id,
                character_ids=(profile.character_id,),
            ),
            context=context,
        )
        if reward_outcome.failure:
            raise AdventureViolation(reward_outcome.failure.code, reward_outcome.failure.message)
        assert reward_outcome.value is not None
        self._claim_action(account_id, record.id, context)
        facts = record.result.facts
        return ExplorationClaimView(
            settlement.id,
            int(facts["damage"]),
            rules.stone_reward,
            rules.herb_reward,
            rules.experience_reward,
            reward_outcome.value.replayed,
        )

    def start_recovery(
        self,
        account_id: str,
        *,
        context: RuleContext,
    ) -> RecoveryStartView:
        with self.database.unit_of_work() as uow:
            profile = self._profile(uow, account_id)
            actions = self.snapshots.require(uow, ACTION_AGGREGATE, account_id, ActionState)
            if existing := _action_for(actions, RECOVERY_ACTION_ID):
                missing_health = int(existing.snapshot.values["missing_health"])
                missing_spirit = int(existing.snapshot.values["missing_spirit"])
                return RecoveryStartView(
                    _activity_view(existing, context.logical_time),
                    missing_health,
                    missing_spirit,
                    True,
                )
            self._require_free_main_slot(actions)
            character = self.snapshots.require(
                uow, CHARACTER_AGGREGATE, profile.character_id, CharacterState
            )
            loadout = self.snapshots.require(
                uow, LOADOUT_AGGREGATE, profile.loadout_id, LoadoutState
            )
            missing_health = max(
                0,
                int(character.core_attributes[HEALTH_MAXIMUM])
                - int(character.resources[HEALTH_CURRENT]),
            )
            missing_spirit = max(
                0,
                int(character.core_attributes[SPIRIT_MAXIMUM])
                - int(character.resources[SPIRIT_CURRENT]),
            )
            if missing_health == 0 and missing_spirit == 0:
                raise AdventureViolation("adventure.recovery_not_needed", "当前血气与精神无需恢复")
            action_id = f"recovery:{account_id}:{actions.next_sequence}"
            snapshot = ActionSnapshot(
                context.logical_time,
                str(context.rule_version),
                self.runtime.report.content_fingerprint,
                str(getattr(context.random, "seed", context.trace_id)),
                character.revision,
                loadout.revision,
                {"missing_health": missing_health, "missing_spirit": missing_spirit},
            )
            outcome = self.runtime.action_engine.execute(
                ActionTransaction(
                    f"start:{action_id}",
                    account_id,
                    actions.revision,
                    (StartAction(action_id, RECOVERY_ACTION_ID, snapshot),),
                ),
                state=actions,
                context=context,
            )
            if outcome.failure:
                raise AdventureViolation(outcome.failure.code, outcome.failure.message)
            assert outcome.value is not None
            self.snapshots.update(
                uow,
                ACTION_AGGREGATE,
                account_id,
                actions,
                outcome.value.state,
                context.logical_time,
            )
            uow.commit()
        record = outcome.value.state.records[action_id]
        return RecoveryStartView(
            _activity_view(record, context.logical_time),
            missing_health,
            missing_spirit,
        )

    def claim_recovery(
        self,
        account_id: str,
        *,
        context: RuleContext,
    ) -> RecoveryClaimView:
        with self.database.unit_of_work() as uow:
            profile = self._profile(uow, account_id)
            actions = self.snapshots.require(uow, ACTION_AGGREGATE, account_id, ActionState)
            record = _action_for(actions, RECOVERY_ACTION_ID)
            if record is None:
                raise AdventureViolation("adventure.recovery_missing", "当前没有正在进行的休息")
            if context.logical_time < record.completes_at:
                raise AdventureViolation("adventure.action_not_due", "休息尚未结束")
            character = self.snapshots.require(
                uow, CHARACTER_AGGREGATE, profile.character_id, CharacterState
            )
            restore_health = min(
                int(record.snapshot.values["missing_health"]),
                max(
                    0,
                    int(character.core_attributes[HEALTH_MAXIMUM])
                    - int(character.resources[HEALTH_CURRENT]),
                ),
            )
            restore_spirit = min(
                int(record.snapshot.values["missing_spirit"]),
                max(
                    0,
                    int(character.core_attributes[SPIRIT_MAXIMUM])
                    - int(character.resources[SPIRIT_CURRENT]),
                ),
            )
            result = ActionResult(
                RECOVERY_OUTCOME_ID,
                context.logical_time,
                facts={
                    "restored_health": restore_health,
                    "restored_spirit": restore_spirit,
                },
            )
            action_outcome = self.runtime.action_engine.execute(
                ActionTransaction(
                    f"finish:{record.id}",
                    account_id,
                    actions.revision,
                    (CompleteAction(record.id, result), ClaimAction(record.id)),
                ),
                state=actions,
                context=context,
            )
            if action_outcome.failure:
                raise AdventureViolation(action_outcome.failure.code, action_outcome.failure.message)
            assert action_outcome.value is not None
            next_character = character
            operations = tuple(
                operation
                for operation in (
                    ChangeCharacterResource(
                        HEALTH_CURRENT,
                        restore_health,
                        "source.recovery",
                        record.id,
                    )
                    if restore_health
                    else None,
                    ChangeCharacterResource(
                        SPIRIT_CURRENT,
                        restore_spirit,
                        "source.recovery",
                        record.id,
                    )
                    if restore_spirit
                    else None,
                )
                if operation is not None
            )
            if operations:
                character_outcome = self.character_engine.execute(
                    CharacterTransaction(
                        f"recover:{record.id}",
                        profile.character_id,
                        character.revision,
                        "character.recovery",
                        operations,
                    ),
                    state=character,
                    context=context,
                )
                if character_outcome.failure:
                    raise AdventureViolation(
                        character_outcome.failure.code,
                        character_outcome.failure.message,
                    )
                assert character_outcome.value is not None
                next_character = character_outcome.value.state
                self.snapshots.update(
                    uow,
                    CHARACTER_AGGREGATE,
                    profile.character_id,
                    character,
                    next_character,
                    context.logical_time,
                )
            self.snapshots.update(
                uow,
                ACTION_AGGREGATE,
                account_id,
                actions,
                action_outcome.value.state,
                context.logical_time,
            )
            uow.commit()
        return RecoveryClaimView(
            restore_health,
            restore_spirit,
            int(next_character.resources[HEALTH_CURRENT]),
            int(next_character.core_attributes[HEALTH_MAXIMUM]),
            int(next_character.resources[SPIRIT_CURRENT]),
            int(next_character.core_attributes[SPIRIT_MAXIMUM]),
        )

    def _complete_exploration_if_due(
        self,
        account_id: str,
        context: RuleContext,
    ) -> ActionRecord:
        with self.database.unit_of_work() as uow:
            self._profile(uow, account_id)
            actions = self.snapshots.require(uow, ACTION_AGGREGATE, account_id, ActionState)
            record = _action_for(actions, EXPLORATION_ACTION_ID)
            if record is None:
                raise AdventureViolation("adventure.exploration_missing", "当前没有可结束的探险")
            if record.status is ActionStatus.COMPLETED:
                return record
            if context.logical_time < record.completes_at:
                remaining = ceil((record.completes_at - context.logical_time).total_seconds())
                raise AdventureViolation(
                    "adventure.action_not_due",
                    f"探险尚未结束，还需 {remaining} 秒",
                )
            result = self._resolve_exploration(record, context)
            outcome = self.runtime.action_engine.execute(
                ActionTransaction(
                    f"complete:{record.id}",
                    account_id,
                    actions.revision,
                    (CompleteAction(record.id, result),),
                ),
                state=actions,
                context=context,
            )
            if outcome.failure:
                raise AdventureViolation(outcome.failure.code, outcome.failure.message)
            assert outcome.value is not None
            self.snapshots.update(
                uow,
                ACTION_AGGREGATE,
                account_id,
                actions,
                outcome.value.state,
                context.logical_time,
            )
            uow.commit()
        return outcome.value.state.records[record.id]

    def _resolve_exploration(self, record: ActionRecord, context: RuleContext) -> ActionResult:
        rules = self.exploration_rules
        attributes = _number_mapping(record.snapshot.values["core_attributes"])
        resources = _number_mapping(record.snapshot.values["resources"])
        actor = RuleEntity(
            record.snapshot.values.get("character_id", record.id),
            base_attributes=attributes,
            resources=resources,
            base_abilities=frozenset({TRIAL_ABILITY_ID}),
        )
        enemy = RuleEntity(
            rules.enemy_id,
            base_attributes={
                HEALTH_MAXIMUM: rules.enemy_health,
                SPIRIT_MAXIMUM: 0,
                COMBAT_ATTACK: 2,
                COMBAT_DEFENSE: 1,
                COMBAT_SPEED: 4,
            },
            resources={HEALTH_CURRENT: rules.enemy_health, SPIRIT_CURRENT: 0},
        )
        replay_context = RuleContext(
            f"resolve:{record.id}",
            record.snapshot.ruleset_version,
            Ruleset("ruleset.exploration"),
            context.logical_time,
            SeededRandomSource(record.snapshot.random_seed),
        )
        ability = self.runtime.ability_engine.execute(
            AbilityUse(f"strike:{record.id}", TRIAL_ABILITY_ID),
            actor=actor,
            target=enemy,
            context=replay_context,
        )
        remaining = int(ability.target.resources[HEALTH_CURRENT])
        damage = rules.enemy_health - remaining
        if remaining > 0:
            raise AdventureViolation("adventure.exploration_failed", "雾竹林妖影未被击破")
        return ActionResult(
            EXPLORATION_OUTCOME_ID,
            context.logical_time,
            f"reward:{record.id}",
            {"enemy_id": rules.enemy_id, "damage": damage, "enemy_health": rules.enemy_health},
        )

    def _claim_action(self, account_id: str, action_id: str, context: RuleContext) -> None:
        with self.database.unit_of_work() as uow:
            actions = self.snapshots.require(uow, ACTION_AGGREGATE, account_id, ActionState)
            if action_id not in actions.records:
                return
            outcome = self.runtime.action_engine.execute(
                ActionTransaction(
                    f"claim:{action_id}",
                    account_id,
                    actions.revision,
                    (ClaimAction(action_id),),
                ),
                state=actions,
                context=context,
            )
            if outcome.failure:
                raise AdventureViolation(outcome.failure.code, outcome.failure.message)
            assert outcome.value is not None
            self.snapshots.update(
                uow,
                ACTION_AGGREGATE,
                account_id,
                actions,
                outcome.value.state,
                context.logical_time,
            )
            uow.commit()

    def _require_free_main_slot(self, actions: ActionState) -> None:
        if actions.running(ActionSlotKind.MAIN):
            raise AdventureViolation("adventure.main_action_busy", "当前已有主行动正在进行")
        if actions.completed():
            raise AdventureViolation("adventure.result_pending", "当前还有行动结果尚未领取")

    def _profile(self, uow, account_id: str) -> PlayerProfileState:
        profile = self.snapshots.load(
            uow, PLAYER_PROFILE_AGGREGATE, account_id, PlayerProfileState
        )
        if profile is None:
            raise AdventureViolation("adventure.player_not_created", "尚未开始修仙")
        return profile


def _exploration_rules(metadata: Mapping[str, object]) -> ExplorationRules:
    try:
        if metadata["system"] != "exploration":
            raise ValueError
        result = ExplorationRules(
            int(metadata["spirit_cost"]),
            str(metadata["enemy_id"]),
            int(metadata["enemy_health"]),
            int(metadata["stone_reward"]),
            int(metadata["experience_reward"]),
            int(metadata["herb_reward"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("探险行动 metadata 不完整") from exc
    if min(
        result.spirit_cost,
        result.enemy_health,
        result.stone_reward,
        result.experience_reward,
        result.herb_reward,
    ) < 1 or not result.enemy_id.strip():
        raise ValueError("探险行动 metadata 数值边界无效")
    return result


def _action_for(actions: ActionState, definition_id: str) -> ActionRecord | None:
    matches = [
        record
        for record in actions.records.values()
        if record.definition_id == definition_id
    ]
    if len(matches) > 1:
        raise AdventureViolation("adventure.action_state_invalid", "同类行动记录重复")
    return matches[0] if matches else None


def _activity_view(record: ActionRecord, logical_time: datetime) -> ActivityView:
    remaining = max(0, ceil((record.completes_at - logical_time).total_seconds()))
    phase = "completed" if record.status is ActionStatus.COMPLETED or remaining == 0 else "running"
    return ActivityView(
        record.id,
        str(record.definition_id),
        phase,
        record.started_at,
        record.completes_at,
        remaining,
    )


def _number_mapping(value: object) -> dict[str, float]:
    if not isinstance(value, Mapping):
        raise AdventureViolation("adventure.snapshot_invalid", "探险冻结数值无效")
    try:
        return {str(key): float(item) for key, item in value.items()}
    except (TypeError, ValueError) as exc:
        raise AdventureViolation("adventure.snapshot_invalid", "探险冻结数值无效") from exc


__all__ = ["AdventureService", "AdventureViolation", "ExplorationRules"]
