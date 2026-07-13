"""首个世界的玩家入世、山门试炼、奖励领取与装备业务。"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from hashlib import sha256

from xiuxian_core.account import (
    AccountDirectoryState,
    AccountEngine,
    AccountState,
    AccountStatus,
    EvidenceRecord,
    ExternalIdentity,
    IdentityBinding,
    IdentityConflict,
    IdentityEvidence,
)
from xiuxian_core.gameplay import (
    AbilityUse,
    ActionResult,
    ActionSnapshot,
    ActionState,
    ActionTransaction,
    ClaimAction,
    CompleteAction,
    AttributeResolver,
    GameplayExecutor,
    RuleContext,
    RuleEntity,
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
    CharacterEngine,
    CharacterProjector,
    CharacterState,
)
from xiuxian_core.gameplay.content import ContentRuntime
from xiuxian_core.gameplay.economy import (
    LedgerAccount,
    LedgerAccountKind,
    LedgerEngine,
    LedgerState,
)
from xiuxian_core.gameplay.inscription import InscriptionPreference
from xiuxian_core.gameplay.inventory import (
    ITEM_ABILITY_COMPONENT_ID,
    CharacterItemUse,
    CharacterItemUseEngine,
    InventoryAbilityExecutor,
    InventoryEngine,
    InventoryState,
    ItemAbilityComponent,
    ItemContainer,
    ItemInstance,
    ItemStack,
    ItemUseReceipt,
    SourceReceipt,
)
from xiuxian_core.gameplay.loadout import (
    WEAPON_SLOT_ID,
    EquipAsset,
    LoadoutEngine,
    LoadoutState,
    LoadoutTransaction,
    standard_loadout_slot_catalog,
)
from xiuxian_core.gameplay.rewards import (
    CharacterExperienceReward,
    CurrencyReward,
    RewardClaimState,
    RewardExpectations,
    RewardSettlement,
    RewardSettlementEngine,
    StackItemReward,
)
from xiuxian_core.gameplay.weapon import WeaponEngine, WeaponState
from xiuxian_core.persistence import (
    ACTION_AGGREGATE,
    CHARACTER_AGGREGATE,
    INSCRIPTION_PREFERENCE_AGGREGATE,
    INVENTORY_AGGREGATE,
    LEDGER_AGGREGATE,
    REWARD_CLAIM_AGGREGATE,
    WEAPON_AGGREGATE,
    ConcurrencyConflict,
    ContentActivationStore,
    PersistedItemUseService,
    PersistedRewardSettlementService,
    RewardSettlementStorageKeys,
    SnapshotRepository,
    SqliteDatabase,
    gameplay_snapshot_codec,
)

from .models import (
    ClaimResultView,
    EntryResult,
    EquipResultView,
    ItemUseResultView,
    PendingTrial,
    PlayerProfileState,
    PlayerStatusView,
    TrialResultView,
    UsableItemView,
)
from .aggregates import (
    ACCOUNT_DIRECTORY_AGGREGATE,
    LOADOUT_AGGREGATE,
    PLAYER_PROFILE_AGGREGATE,
)
from .storage_keys import (
    equipped_container_id,
    inventory_container_id,
    issuer_id,
    wallet_id,
)
from .adventure import AdventureService
from .world import (
    CHARACTER_TEMPLATE_ID,
    CURRENCY_ID,
    HERB_ITEM_ID,
    PROGRESSION_ID,
    QUALITY_ID,
    STARTER_WEAPON_ID,
    STARTER_WEAPON_ITEM_ID,
    TRIAL_ABILITY_ID,
    TRIAL_ACTION_ID,
    TRIAL_ENEMY_ID,
    TRIAL_EXPERIENCE_REWARD,
    TRIAL_HERB_REWARD,
    TRIAL_OUTCOME_ID,
    TRIAL_STONE_REWARD,
)


class GameViolation(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def game_snapshot_repository() -> SnapshotRepository:
    registrations = (
        ("account.status", AccountStatus),
        ("account.external_identity", ExternalIdentity),
        ("account.binding", IdentityBinding),
        ("account.state", AccountState),
        ("account.conflict", IdentityConflict),
        ("account.evidence_record", EvidenceRecord),
        ("account.directory", AccountDirectoryState),
        ("loadout.state", LoadoutState),
        ("game.player_profile", PlayerProfileState),
    )
    return SnapshotRepository(gameplay_snapshot_codec(registrations))


class GameApplication:
    """不依赖命令和消息协议的首个世界业务组合根。"""

    def __init__(self, database: SqliteDatabase, runtime: ContentRuntime) -> None:
        self.database = database
        self.runtime = runtime
        self.snapshots = game_snapshot_repository()
        self.inventory_engine = InventoryEngine(runtime.items)
        self.ledger_engine = LedgerEngine(runtime.currencies)
        self.character_engine = CharacterEngine(runtime.characters)
        self.weapon_engine = WeaponEngine(runtime.weapons)
        self.reward_engine = RewardSettlementEngine(
            inventory=self.inventory_engine,
            ledger=self.ledger_engine,
            character=self.character_engine,
            weapon=self.weapon_engine,
        )
        self.rewards = PersistedRewardSettlementService(
            database,
            self.reward_engine,
            self.snapshots,
        )
        self.loadout_engine = LoadoutEngine(
            standard_loadout_slot_catalog(),
            runtime.items,
            self.inventory_engine,
        )
        self.character_projector = CharacterProjector(
            runtime.characters,
            AttributeResolver(runtime.attributes),
            runtime.resources,
            ability_ids=frozenset(runtime.abilities.ids()),
            trigger_ids=frozenset(runtime.triggers.ids()),
            interceptor_ids=frozenset(runtime.interceptors.ids()),
            target_constraint_ids=frozenset(runtime.target_constraints.ids()),
        )
        self.item_use_engine = CharacterItemUseEngine(
            InventoryAbilityExecutor(
                runtime.items,
                self.inventory_engine,
                GameplayExecutor(runtime.ability_engine, runtime.trigger_engine),
            ),
            self.character_engine,
            self.character_projector,
        )
        self.item_uses = PersistedItemUseService(
            database,
            self.item_use_engine,
            self.snapshots,
        )
        self.adventure = AdventureService(
            database,
            runtime,
            self.snapshots,
            self.character_engine,
            self.rewards,
        )

    def initialize(self, *, logical_time: datetime) -> None:
        _aware(logical_time)
        self.database.initialize()
        ContentActivationStore(self.database).verify_or_initialize(
            self.runtime.report,
            slot_id="content.first_world",
            logical_time=logical_time,
        )

    def enter_world(
        self,
        evidence: IdentityEvidence,
        *,
        logical_time: datetime,
        create_player: bool = True,
    ) -> EntryResult:
        _aware(logical_time)
        with self.database.unit_of_work() as uow:
            previous_directory = self.snapshots.load(
                uow,
                ACCOUNT_DIRECTORY_AGGREGATE,
                "main",
                AccountDirectoryState,
            )
            directory = previous_directory or AccountDirectoryState()
            account, next_directory = self._resolve_account(evidence, directory)
            profile = self.snapshots.load(
                uow,
                PLAYER_PROFILE_AGGREGATE,
                account.id,
                PlayerProfileState,
            )
            created = profile is None and create_player
            if previous_directory is None:
                self.snapshots.insert(
                    uow,
                    ACCOUNT_DIRECTORY_AGGREGATE,
                    "main",
                    next_directory,
                    logical_time,
                )
            elif next_directory != previous_directory:
                self.snapshots.update(
                    uow,
                    ACCOUNT_DIRECTORY_AGGREGATE,
                    "main",
                    previous_directory,
                    next_directory,
                    logical_time,
                )
            if profile is None and create_player:
                self._initialize_player(uow, account.id, logical_time)
            uow.commit()
        return EntryResult(account.id, created)

    def status(self, account_id: str) -> PlayerStatusView:
        with self.database.unit_of_work(write=False) as uow:
            profile = self._profile(uow, account_id)
            character = self.snapshots.require(
                uow, CHARACTER_AGGREGATE, profile.character_id, CharacterState
            )
            inventory = self.snapshots.require(
                uow, INVENTORY_AGGREGATE, profile.inventory_id, InventoryState
            )
            ledger = self.snapshots.require(
                uow, LEDGER_AGGREGATE, profile.ledger_id, LedgerState
            )
            loadout = self.snapshots.require(
                uow, LOADOUT_AGGREGATE, profile.loadout_id, LoadoutState
            )
            actions = self.snapshots.require(
                uow, ACTION_AGGREGATE, account_id, ActionState
            )
        progression = character.progressions[PROGRESSION_ID]
        wallet = ledger.accounts[wallet_id(account_id)]
        return PlayerStatusView(
            account_id,
            character.id,
            progression.level,
            progression.experience,
            int(character.resources[HEALTH_CURRENT]),
            int(character.core_attributes[HEALTH_MAXIMUM]),
            int(character.resources[SPIRIT_CURRENT]),
            int(character.core_attributes[SPIRIT_MAXIMUM]),
            wallet.balance,
            _stack_quantity(inventory, HERB_ITEM_ID),
            profile.starter_weapon_asset_id,
            loadout.weapon_asset_id,
            _pending_trial(actions),
        )

    def usable_items(
        self,
        account_id: str,
        *,
        logical_time: datetime,
    ) -> tuple[UsableItemView, ...]:
        _aware(logical_time)
        with self.database.unit_of_work(write=False) as uow:
            profile = self._profile(uow, account_id)
            inventory = self.snapshots.require(
                uow,
                INVENTORY_AGGREGATE,
                profile.inventory_id,
                InventoryState,
            )
        return _usable_item_views(
            inventory,
            owner_id=profile.character_id,
            runtime=self.runtime,
            logical_time=logical_time,
        )

    def use_item(
        self,
        account_id: str,
        item_definition_id: str,
        *,
        context: RuleContext,
        target_account_id: str | None = None,
    ) -> ItemUseResultView:
        if target_account_id is not None and target_account_id != account_id:
            raise GameViolation(
                "game.item_target_forbidden",
                "当前物品使用入口只允许以自己为目标",
            )
        try:
            definition = self.runtime.items.require(item_definition_id)
            component = definition.component(
                ITEM_ABILITY_COMPONENT_ID,
                ItemAbilityComponent,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise GameViolation("game.item_not_usable", "该物品当前不能主动使用") from exc

        with self.database.unit_of_work(write=False) as uow:
            profile = self._profile(uow, account_id)
        transaction_id = f"item-use:{context.trace_id}"
        committed = self.item_uses.committed_receipt(
            transaction_id,
            actor_id=profile.character_id,
        )
        if committed is not None:
            if (
                committed.item_definition_id != definition.id
                or committed.ability_id != component.ability_id
                or committed.target_id != profile.character_id
            ):
                raise GameViolation(
                    "game.item_request_mismatch",
                    "同一请求 ID 对应了不同的物品使用内容",
                )
            return _item_use_result(committed)

        with self.database.unit_of_work(write=False) as uow:
            inventory = self.snapshots.require(
                uow,
                INVENTORY_AGGREGATE,
                profile.inventory_id,
                InventoryState,
            )
        asset_id = _select_usable_asset(
            inventory,
            owner_id=profile.character_id,
            definition_id=str(definition.id),
            consume_quantity=component.consume_quantity,
            logical_time=context.logical_time,
        )
        if asset_id is None:
            raise GameViolation("game.item_unavailable", "纳戒中没有可用的该物品")
        outcome = self.item_uses.use(
            CharacterItemUse(
                transaction_id,
                profile.character_id,
                profile.character_id,
                asset_id,
                AbilityUse(f"{transaction_id}:ability", component.ability_id),
            ),
            inventory_id=profile.inventory_id,
            context=context,
        )
        if outcome.failure:
            raise GameViolation(outcome.failure.code, outcome.failure.message)
        assert outcome.value is not None
        return _item_use_result(outcome.value)

    def begin_trial(
        self,
        account_id: str,
        *,
        context: RuleContext,
    ) -> TrialResultView:
        with self.database.unit_of_work() as uow:
            profile = self._profile(uow, account_id)
            actions = self.snapshots.require(
                uow, ACTION_AGGREGATE, account_id, ActionState
            )
            if pending := _pending_trial(actions):
                return TrialResultView(pending, replayed=True)
            character = self.snapshots.require(
                uow, CHARACTER_AGGREGATE, profile.character_id, CharacterState
            )
            loadout = self.snapshots.require(
                uow, LOADOUT_AGGREGATE, profile.loadout_id, LoadoutState
            )
            sequence = actions.next_sequence
            trial_id = f"trial:{account_id}:{sequence}"
            actor = RuleEntity(
                character.id,
                base_attributes=character.core_attributes,
                resources=character.resources,
                base_abilities=frozenset({TRIAL_ABILITY_ID}),
            )
            enemy_health = 12
            enemy = RuleEntity(
                TRIAL_ENEMY_ID,
                base_attributes={
                    HEALTH_MAXIMUM: enemy_health,
                    SPIRIT_MAXIMUM: 0,
                    COMBAT_ATTACK: 2,
                    COMBAT_DEFENSE: 1,
                    COMBAT_SPEED: 4,
                },
                resources={HEALTH_CURRENT: enemy_health, SPIRIT_CURRENT: 0},
            )
            ability_result = self.runtime.ability_engine.execute(
                AbilityUse(f"{trial_id}:strike", TRIAL_ABILITY_ID),
                actor=actor,
                target=enemy,
                context=context,
            )
            remaining = int(ability_result.target.resources[HEALTH_CURRENT])
            damage = enemy_health - remaining
            if remaining > 0:
                raise GameViolation("game.trial_not_defeated", "山门木傀仍未被击破")
            settlement_id = f"reward:{trial_id}"
            snapshot = ActionSnapshot(
                context.logical_time,
                str(context.rule_version),
                self.runtime.report.content_fingerprint,
                str(getattr(context.random, "seed", context.trace_id)),
                character.revision,
                loadout.revision,
                {"enemy_id": TRIAL_ENEMY_ID, "enemy_health": enemy_health},
            )
            result = ActionResult(
                TRIAL_OUTCOME_ID,
                context.logical_time,
                settlement_id,
                {
                    "enemy_id": TRIAL_ENEMY_ID,
                    "damage": damage,
                    "enemy_health": enemy_health,
                },
            )
            outcome = self.runtime.action_engine.execute(
                ActionTransaction(
                    f"action:start:{trial_id}",
                    account_id,
                    actions.revision,
                    (
                        StartAction(trial_id, TRIAL_ACTION_ID, snapshot),
                        CompleteAction(trial_id, result),
                    ),
                ),
                state=actions,
                context=context,
            )
            if outcome.failure:
                raise GameViolation(outcome.failure.code, outcome.failure.message)
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
        pending = _pending_trial(outcome.value.state)
        assert pending is not None
        return TrialResultView(pending)

    def claim_trial(
        self,
        account_id: str,
        *,
        context: RuleContext,
    ) -> ClaimResultView:
        with self.database.unit_of_work(write=False) as uow:
            profile = self._profile(uow, account_id)
            actions = self.snapshots.require(uow, ACTION_AGGREGATE, account_id, ActionState)
            pending = _pending_trial(actions)
            if pending is None:
                raise GameViolation("game.trial_nothing_to_claim", "当前没有待领取的试炼结果")
            inventory = self.snapshots.require(
                uow, INVENTORY_AGGREGATE, profile.inventory_id, InventoryState
            )
            ledger = self.snapshots.require(
                uow, LEDGER_AGGREGATE, profile.ledger_id, LedgerState
            )
            character = self.snapshots.require(
                uow, CHARACTER_AGGREGATE, profile.character_id, CharacterState
            )
            claims = self.snapshots.require(
                uow,
                REWARD_CLAIM_AGGREGATE,
                profile.claim_scope_id,
                RewardClaimState,
            )
        issuer_account_id = issuer_id()
        wallet_account_id = wallet_id(account_id)
        settlement = RewardSettlement(
            pending.reward_settlement_id,
            account_id,
            profile.claim_scope_id,
            "source.mountain_gate_trial",
            pending.id,
            (
                CurrencyReward(issuer_account_id, wallet_account_id, TRIAL_STONE_REWARD),
                CharacterExperienceReward(
                    profile.character_id,
                    PROGRESSION_ID,
                    TRIAL_EXPERIENCE_REWARD,
                ),
                StackItemReward(
                    f"herb:{pending.id}",
                    HERB_ITEM_ID,
                    inventory_container_id(profile.character_id),
                    TRIAL_HERB_REWARD,
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
        outcome = self.rewards.settle(
            settlement,
            RewardSettlementStorageKeys(
                profile.inventory_id,
                profile.ledger_id,
                character_ids=(profile.character_id,),
            ),
            context=context,
        )
        if outcome.failure:
            raise GameViolation(outcome.failure.code, outcome.failure.message)
        assert outcome.value is not None
        self._mark_trial_claimed(account_id, pending, context)
        status = self.status(account_id)
        return ClaimResultView(
            pending.reward_settlement_id,
            status.stones,
            status.herb_quantity,
            status.experience,
            replayed=outcome.value.replayed,
        )

    def equip_starter_weapon(
        self,
        account_id: str,
        *,
        context: RuleContext,
    ) -> EquipResultView:
        with self.database.unit_of_work() as uow:
            profile = self._profile(uow, account_id)
            loadout = self.snapshots.require(
                uow, LOADOUT_AGGREGATE, profile.loadout_id, LoadoutState
            )
            if loadout.weapon_asset_id == profile.starter_weapon_asset_id:
                return EquipResultView(profile.starter_weapon_asset_id, replayed=True)
            inventory = self.snapshots.require(
                uow, INVENTORY_AGGREGATE, profile.inventory_id, InventoryState
            )
            outcome = self.loadout_engine.execute(
                LoadoutTransaction(
                    f"equip:{account_id}:{profile.starter_weapon_asset_id}:{loadout.revision}",
                    profile.character_id,
                    loadout.revision,
                    inventory_container_id(profile.character_id),
                    equipped_container_id(profile.character_id),
                    (EquipAsset(WEAPON_SLOT_ID, profile.starter_weapon_asset_id),),
                ),
                loadout=loadout,
                inventory_state=inventory,
                context=context,
            )
            if outcome.failure:
                raise GameViolation(outcome.failure.code, outcome.failure.message)
            assert outcome.value is not None
            self.snapshots.update(
                uow,
                LOADOUT_AGGREGATE,
                profile.loadout_id,
                loadout,
                outcome.value.loadout,
                context.logical_time,
            )
            self.snapshots.update(
                uow,
                INVENTORY_AGGREGATE,
                profile.inventory_id,
                inventory,
                outcome.value.inventory,
                context.logical_time,
            )
            uow.commit()
        return EquipResultView(profile.starter_weapon_asset_id)

    def _resolve_account(
        self,
        evidence: IdentityEvidence,
        directory: AccountDirectoryState,
    ) -> tuple[AccountState, AccountDirectoryState]:
        bound = {
            binding.account_id
            for identity in evidence.identities
            if (binding := directory.bindings.get(identity.key)) is not None
        }
        all_bound = all(identity.key in directory.bindings for identity in evidence.identities)
        if len(bound) == 1 and all_bound:
            account = directory.accounts[next(iter(bound))]
            if account.status is not AccountStatus.ACTIVE:
                raise GameViolation("game.account_not_active", "当前账号不可进入世界")
            return account, directory
        account_id = _account_id(evidence.primary)
        resolution = AccountEngine(lambda: account_id).resolve_identity(
            evidence,
            state=directory,
        )
        if not resolution.resolved or resolution.account is None:
            raise GameViolation("game.identity_conflict", "当前平台身份存在归属冲突")
        if resolution.account.status is not AccountStatus.ACTIVE:
            raise GameViolation("game.account_not_active", "当前账号不可进入世界")
        return resolution.account, resolution.directory

    def _initialize_player(self, uow, account_id: str, logical_time: datetime) -> None:
        character_id = f"character:{account_id}"
        profile = PlayerProfileState(
            account_id,
            character_id,
            f"inventory:{account_id}",
            f"ledger:{account_id}",
            character_id,
            f"claim:{account_id}",
            f"weapon:{account_id}:starter",
        )
        character = self.runtime.characters.create_character(
            character_id=character_id,
            account_id=account_id,
            template_id=CHARACTER_TEMPLATE_ID,
            created_at=logical_time,
        )
        inventory_container = ItemContainer(
            inventory_container_id(character_id),
            "container.inventory",
            character_id,
            maximum_assets=80,
        )
        equipped_container = ItemContainer(
            equipped_container_id(character_id),
            "container.equipped",
            character_id,
            maximum_assets=7,
        )
        receipt = SourceReceipt(
            f"entry:{account_id}:starter_weapon",
            "source.player_entry",
            account_id,
            logical_time,
        )
        weapon_instance = ItemInstance(
            profile.starter_weapon_asset_id,
            STARTER_WEAPON_ITEM_ID,
            inventory_container.id,
            receipt,
        )
        inventory = InventoryState(
            {inventory_container.id: inventory_container, equipped_container.id: equipped_container},
            {},
            {weapon_instance.id: weapon_instance},
        )
        weapon = self.runtime.weapons.create_state(
            asset_id=weapon_instance.id,
            definition_id=STARTER_WEAPON_ID,
            quality_id=QUALITY_ID,
        )
        issuer = LedgerAccount(
            issuer_id(),
            "owner.system",
            "system.first_world",
            CURRENCY_ID,
            LedgerAccountKind.ISSUER,
        )
        wallet = LedgerAccount(
            wallet_id(account_id),
            "owner.account",
            account_id,
            CURRENCY_ID,
        )
        values = (
            (PLAYER_PROFILE_AGGREGATE, account_id, profile),
            (CHARACTER_AGGREGATE, character.id, character),
            (INVENTORY_AGGREGATE, profile.inventory_id, inventory),
            (LEDGER_AGGREGATE, profile.ledger_id, LedgerState({issuer.id: issuer, wallet.id: wallet})),
            (WEAPON_AGGREGATE, weapon.asset_id, weapon),
            (LOADOUT_AGGREGATE, profile.loadout_id, LoadoutState(character.id)),
            (REWARD_CLAIM_AGGREGATE, profile.claim_scope_id, RewardClaimState(profile.claim_scope_id)),
            (ACTION_AGGREGATE, account_id, ActionState(account_id)),
            (INSCRIPTION_PREFERENCE_AGGREGATE, account_id, InscriptionPreference(account_id)),
        )
        for aggregate_kind, aggregate_id, value in values:
            self.snapshots.insert(
                uow,
                aggregate_kind,
                aggregate_id,
                value,
                logical_time,
            )

    def _mark_trial_claimed(
        self,
        account_id: str,
        pending: PendingTrial,
        context: RuleContext,
    ) -> None:
        try:
            with self.database.unit_of_work() as uow:
                actions = self.snapshots.require(uow, ACTION_AGGREGATE, account_id, ActionState)
                current_pending = _pending_trial(actions)
                if current_pending is None:
                    return
                if current_pending.id != pending.id:
                    raise GameViolation("game.trial_changed", "待领取试炼已经变化")
                outcome = self.runtime.action_engine.execute(
                    ActionTransaction(
                        f"action:claim:{pending.id}",
                        account_id,
                        actions.revision,
                        (ClaimAction(pending.id),),
                    ),
                    state=actions,
                    context=context,
                )
                if outcome.failure:
                    raise GameViolation(outcome.failure.code, outcome.failure.message)
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
        except ConcurrencyConflict:
            with self.database.unit_of_work(write=False) as uow:
                latest = self.snapshots.require(uow, ACTION_AGGREGATE, account_id, ActionState)
            if _pending_trial(latest) is not None:
                raise

    def _profile(self, uow, account_id: str) -> PlayerProfileState:
        profile = self.snapshots.load(
            uow,
            PLAYER_PROFILE_AGGREGATE,
            account_id,
            PlayerProfileState,
        )
        if profile is None:
            raise GameViolation("game.player_not_created", "尚未开始修仙")
        return profile


def _account_id(identity: ExternalIdentity) -> str:
    raw = "|".join(identity.key).encode("utf-8")
    return f"account-{sha256(raw).hexdigest()[:24]}"


def _stack_quantity(inventory: InventoryState, definition_id: str) -> int:
    return sum(
        stack.quantity
        for stack in inventory.stacks.values()
        if stack.definition_id == definition_id
    )


def _usable_item_views(
    inventory: InventoryState,
    *,
    owner_id: str,
    runtime: ContentRuntime,
    logical_time: datetime,
) -> tuple[UsableItemView, ...]:
    grouped: dict[str, dict[str, int | str]] = {}
    for asset in (*inventory.stacks.values(), *inventory.instances.values()):
        if inventory.owner_of(asset.id) != owner_id:
            continue
        definition = runtime.items.require(asset.definition_id)
        component = definition.components.get(ITEM_ABILITY_COMPONENT_ID)
        if not isinstance(component, ItemAbilityComponent):
            continue
        quantity = asset.quantity if isinstance(asset, ItemStack) else 1
        reserved = _active_reserved_quantity(inventory, asset.id, logical_time)
        available = quantity - reserved
        if component.consume_quantity == 0 and reserved:
            available = 0
        key = str(definition.id)
        current = grouped.setdefault(
            key,
            {
                "ability_id": str(component.ability_id),
                "quantity": 0,
                "available_quantity": 0,
                "asset_count": 0,
            },
        )
        current["quantity"] = int(current["quantity"]) + quantity
        current["available_quantity"] = int(current["available_quantity"]) + available
        current["asset_count"] = int(current["asset_count"]) + 1
    return tuple(
        UsableItemView(
            definition_id,
            str(values["ability_id"]),
            int(values["quantity"]),
            int(values["available_quantity"]),
            int(values["asset_count"]),
        )
        for definition_id, values in sorted(grouped.items())
    )


def _select_usable_asset(
    inventory: InventoryState,
    *,
    owner_id: str,
    definition_id: str,
    consume_quantity: int,
    logical_time: datetime,
) -> str | None:
    candidates = []
    for asset in (*inventory.stacks.values(), *inventory.instances.values()):
        if asset.definition_id != definition_id or inventory.owner_of(asset.id) != owner_id:
            continue
        quantity = asset.quantity if isinstance(asset, ItemStack) else 1
        reserved = _active_reserved_quantity(inventory, asset.id, logical_time)
        available = quantity - reserved
        if consume_quantity == 0:
            allowed = reserved == 0
        else:
            allowed = available >= consume_quantity
        if allowed:
            candidates.append(asset)
    if not candidates:
        return None
    candidates.sort(key=_asset_source_key)
    return candidates[0].id


def _active_reserved_quantity(
    inventory: InventoryState,
    asset_id: str,
    logical_time: datetime,
) -> int:
    return sum(
        reservation.quantity
        for reservation in inventory.reservations_for(asset_id)
        if not reservation.expired_at(logical_time)
    )


def _asset_source_key(asset: ItemStack | ItemInstance) -> tuple[datetime, str]:
    logical_time = (
        asset.lots[0].receipt.logical_time
        if isinstance(asset, ItemStack)
        else asset.receipt.logical_time
    )
    return logical_time, asset.id


def _item_use_result(receipt: ItemUseReceipt) -> ItemUseResultView:
    return ItemUseResultView(
        receipt.transaction_id,
        str(receipt.item_definition_id),
        str(receipt.ability_id),
        receipt.actor_id,
        receipt.target_id,
        receipt.consumed_quantity,
        receipt.resource_changes,
        receipt.replayed,
    )


def _pending_trial(actions: ActionState) -> PendingTrial | None:
    completed = actions.completed(TRIAL_ACTION_ID)
    if not completed:
        return None
    record = completed[0]
    assert record.result is not None
    if record.result.outcome_id != TRIAL_OUTCOME_ID:
        raise GameViolation("game.trial_outcome_invalid", "山门试炼结果类型无效")
    if record.result.settlement_id is None:
        raise GameViolation("game.trial_settlement_missing", "山门试炼缺少奖励结算 ID")
    facts = record.result.facts
    try:
        return PendingTrial(
            record.id,
            record.sequence,
            str(facts["enemy_id"]),
            int(facts["damage"]),
            int(facts["enemy_health"]),
            record.result.settlement_id,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise GameViolation("game.trial_facts_invalid", "山门试炼结果数据无效") from exc


def _aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("游戏业务逻辑时间必须包含时区")


__all__ = [
    "ACCOUNT_DIRECTORY_AGGREGATE",
    "GameApplication",
    "GameViolation",
    "LOADOUT_AGGREGATE",
    "PLAYER_PROFILE_AGGREGATE",
    "game_snapshot_repository",
]
