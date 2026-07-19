"""游戏数据库、内容和服务的启动装配入口。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from game.content import (
    DIMENSIONAL_DISASTER_BATTLE_ROUNDS,
    DEFAULT_SKIN_ID,
    OfficialContent,
    PLAYABLE_WORLD_SKIN_IDS,
    WorldViewCatalog,
    assemble_official_catalog,
    build_dimensional_disaster_catalog,
)
from game.core.account import AccountEngine, ExternalIdentity, IdentityEvidence
from game.core.gameplay import (
    AttributeResolver,
    ActionSlotKind,
    ActionRecord,
    ActionState,
    CharacterEngine,
    CharacterItemUseEngine,
    CharacterProjector,
    CharacterState,
    InventoryEngine,
    InventoryAbilityExecutor,
    InventoryState,
    InscriptionEngine,
    InscriptionPreference,
    LedgerState,
    LedgerEngine,
    LoadoutState,
    LoadoutEngine,
    NotificationEntry,
    NotificationStatus,
    RewardSettlementEngine,
    GameplayExecutor,
    WeaponEngine,
    WorldState,
)
from game.core.persistence import (
    ACTIVITY_AGGREGATE,
    ACTION_AGGREGATE,
    CHARACTER_AGGREGATE,
    ConcurrencyConflict,
    INVENTORY_AGGREGATE,
    INSCRIPTION_PREFERENCE_AGGREGATE,
    LEDGER_AGGREGATE,
    LOADOUT_AGGREGATE,
    LOOT_AGGREGATE,
    PersistenceError,
    NotificationInboxService,
    PersistedActivityService,
    PersistedActionService,
    PersistedAccountService,
    PersistedCharacterCreationService,
    PersistedCharacterService,
    PersistedInscriptionService,
    PersistedItemUseService,
    PersistedLoadoutService,
    PersistedRewardSettlementService,
    REWARD_CLAIM_AGGREGATE,
    RewardSettlementStorageKeys,
    SnapshotRepository,
    SqliteDatabase,
    WORLD_AGGREGATE,
    WEAPON_AGGREGATE,
    gameplay_snapshot_codec,
)
from game.rules.character import (
    CHARACTER_DIMENSION_AGGREGATE,
    CHARACTER_SETTINGS_AGGREGATE,
    CharacterDimensionState,
    CharacterCreationPlanner,
    CharacterCreationReceipt,
    CharacterCreationRequest,
    CharacterCreationWorkflow,
    CharacterIdentityViolation,
    CharacterSettingsState,
    DimensionShiftResult,
    PRIMARY_LEDGER_ID,
    PRIMARY_WORLD_ID,
    character_creation_context,
    shift_dimension,
)
from game.rules.activity import (
    GLOBAL_ACTIVITY_SCOPE_ID,
    GlobalActivityCatalog,
    GlobalActivityView,
    global_activity_catalog,
)
from game.rules.combat import PlayerCombatProjector
from game.features.exploration import (
    ExplorationFeature,
    ExplorationStorageKinds,
    exploration_codec_registrations,
)
from game.features.dimensional_disaster import (
    DimensionalDisasterFeature,
    DimensionalDisasterStorageKinds,
    dimensional_disaster_codec_registrations,
)
from game.features.item_sale import ItemSaleFeature, ItemSaleStorageKinds
from game.features.battle_report import BattleReportService
from game.features.rest import RestFeature, RestStorageKinds, rest_codec_registrations
from game.rules.exploration import (
    EXPLORATION_AGGREGATE,
    ExplorationState,
    ExplorationStatus,
)
from launch import C, OnEvent, Scheduler, config, logger
from launch.adapter import MessageIdentity


@dataclass(frozen=True)
class CharacterCreationCommandResult:
    """命令层可以稳定展示的角色创建结果。"""

    status: str
    receipt: CharacterCreationReceipt | None = None
    existing_character: CharacterState | None = None


@dataclass(frozen=True)
class CharacterOverview:
    """角色状态页需要的一致数据库快照。"""

    character: CharacterState
    inventory: InventoryState
    loadout: LoadoutState
    ledger: LedgerState
    world: WorldState
    dimension: CharacterDimensionState
    inscription_preference: InscriptionPreference | None = None
    action: ActionState | None = None


@dataclass(frozen=True)
class CharacterOverviewResult:
    """角色状态查询的稳定结果。"""

    status: str
    overview: CharacterOverview | None = None


@dataclass(frozen=True)
class CurrentCharacterResult:
    """当前身份解析到角色后的稳定结果。"""

    status: str
    character: CharacterState | None = None
    dimension: CharacterDimensionState | None = None


@dataclass(frozen=True)
class PlayerReplyState:
    """统一人物头和全局通栏需要的只读状态。"""

    character: CharacterState
    settings: CharacterSettingsState
    dimension: CharacterDimensionState
    activity_spotlights: tuple[GlobalActivityView, ...] = ()
    additional_activity_count: int = 0
    unread_notification_count: int = 0
    pending_action_count: int = 0

    def __post_init__(self) -> None:
        if (
            self.additional_activity_count < 0
            or self.unread_notification_count < 0
            or self.pending_action_count < 0
        ):
            raise ValueError("玩家回复摘要数量不能小于 0")


@dataclass(frozen=True)
class PlayerReplyStateResult:
    """当前消息身份对应的玩家回复装饰状态。"""

    status: str
    state: PlayerReplyState | None = None


@dataclass(frozen=True)
class PlayerReminderDetails:
    """通知与待领取汇总页使用的只读明细。"""

    notifications: tuple[NotificationEntry, ...] = ()
    pending_actions: tuple[ActionRecord, ...] = ()


@dataclass(frozen=True)
class PlayerReminderDetailsResult:
    """玩家提醒明细的稳定读取结果。"""

    status: str
    details: PlayerReminderDetails | None = None


@dataclass(frozen=True)
class GlobalActivityViewsResult:
    """当前开放全服活动的稳定读取结果。"""

    status: str
    activities: tuple[GlobalActivityView, ...] = ()


@dataclass(frozen=True)
class NotificationMarkResult:
    """通知已读操作的受控结果。"""

    status: str
    notification: NotificationEntry | None = None


@dataclass(frozen=True)
class GameServices:
    """命令层可以使用的完整游戏服务集合。"""

    database: SqliteDatabase
    accounts: PersistedAccountService
    characters: PersistedCharacterService
    character_creation: PersistedCharacterCreationService
    character_projector: CharacterProjector
    player_combat: PlayerCombatProjector
    inscriptions: PersistedInscriptionService
    item_use: PersistedItemUseService
    loadouts: PersistedLoadoutService
    notifications: NotificationInboxService
    activities: PersistedActivityService
    actions: PersistedActionService
    global_activities: GlobalActivityCatalog
    battle_reports: BattleReportService
    dimensional_disasters: DimensionalDisasterFeature
    exploration: ExplorationFeature
    rest: RestFeature
    item_sale: ItemSaleFeature
    world_views: WorldViewCatalog
    content: OfficialContent

    def world_view(
        self,
        dimension: CharacterDimensionState | str,
    ) -> OfficialContent:
        """读取角色当前界相对应的缓存展示投影。"""

        skin_id = (
            dimension.skin_id
            if isinstance(dimension, CharacterDimensionState)
            else dimension
        )
        return self.world_views.require(skin_id)

    def create_character(
        self,
        evidence: IdentityEvidence,
        *,
        requested_name: str = "",
        platform_name: str = "",
    ) -> CharacterCreationCommandResult:
        """解析账号并执行角色创世，不把持久化异常泄漏到命令组件。"""

        try:
            resolution = self.accounts.resolve_identity(evidence)
        except PersistenceError as exc:
            logger.opt(colors=True, exception=exc).error(
                C.join(
                    C.fail("账号身份解析失败"),
                    C.kv("evidence", evidence.id),
                )
            )
            return CharacterCreationCommandResult("failed")
        if resolution.account is None:
            return CharacterCreationCommandResult("identity_conflict")
        account_id = resolution.account.id
        request = CharacterCreationRequest(
            f"character:create:{evidence.id}",
            account_id,
            requested_name=requested_name,
            platform_name=platform_name,
        )
        try:
            receipt = self.character_creation.create(
                request,
                context=character_creation_context(
                    trace_id=request.transaction_id,
                    logical_time=evidence.logical_time,
                ),
            )
        except CharacterIdentityViolation as exc:
            status = {
                "character.name_required": "name_required",
                "character.name_invalid": "name_invalid",
                "character.account_already_has_character": "existing",
            }.get(exc.code, "rejected")
            existing_character = self.characters.load_for_account(account_id)
            return CharacterCreationCommandResult(
                status,
                existing_character=existing_character,
            )
        except ConcurrencyConflict:
            existing_character = self.characters.load_for_account(account_id)
            return CharacterCreationCommandResult(
                "existing",
                existing_character=existing_character,
            )
        except PersistenceError as exc:
            logger.opt(colors=True, exception=exc).error(
                C.join(
                    C.fail("角色创世持久化失败"),
                    C.kv("evidence", evidence.id),
                )
            )
            return CharacterCreationCommandResult("failed")
        if not isinstance(receipt, CharacterCreationReceipt):
            raise TypeError("角色创世服务返回了错误回执类型")
        return CharacterCreationCommandResult("created", receipt=receipt)

    def load_current_character(
        self,
        evidence: IdentityEvidence,
    ) -> CurrentCharacterResult:
        """把当前外部身份解析为游戏角色，不读取其他领域快照。"""

        try:
            resolution = self.accounts.resolve_identity(evidence)
            if resolution.account is None:
                return CurrentCharacterResult("identity_conflict")
            character = self.characters.load_for_account(resolution.account.id)
            if character is None:
                return CurrentCharacterResult("not_created")
            snapshots = self.character_creation.snapshots
            with self.database.unit_of_work(write=False) as uow:
                dimension = snapshots.require(
                    uow,
                    CHARACTER_DIMENSION_AGGREGATE,
                    character.id,
                    CharacterDimensionState,
                )
            return CurrentCharacterResult("ok", character, dimension)
        except PersistenceError as exc:
            logger.opt(colors=True, exception=exc).error(
                C.join(
                    C.fail("当前角色读取失败"),
                    C.kv("evidence", evidence.id),
                )
            )
            return CurrentCharacterResult("failed")

    def load_character_overview(
        self,
        character: CharacterState,
    ) -> CharacterOverviewResult:
        """按需读取角色状态页使用的跨领域快照。"""

        try:
            snapshots = self.character_creation.snapshots
            with self.database.unit_of_work(write=False) as uow:
                stored_character = snapshots.require(
                    uow,
                    CHARACTER_AGGREGATE,
                    character.id,
                    CharacterState,
                )
                if stored_character.account_id != character.account_id:
                    raise PersistenceError("角色详情账号归属不一致")
                inventory = snapshots.require(
                    uow,
                    INVENTORY_AGGREGATE,
                    character.id,
                    InventoryState,
                )
                loadout = snapshots.require(
                    uow,
                    LOADOUT_AGGREGATE,
                    character.id,
                    LoadoutState,
                )
                ledger = snapshots.require(
                    uow,
                    LEDGER_AGGREGATE,
                    PRIMARY_LEDGER_ID,
                    LedgerState,
                )
                world = snapshots.require(
                    uow,
                    WORLD_AGGREGATE,
                    PRIMARY_WORLD_ID,
                    WorldState,
                )
                dimension = snapshots.require(
                    uow,
                    CHARACTER_DIMENSION_AGGREGATE,
                    character.id,
                    CharacterDimensionState,
                )
                action = snapshots.load(
                    uow,
                    ACTION_AGGREGATE,
                    character.id,
                    ActionState,
                )
                inscription_preference = snapshots.load(
                    uow,
                    INSCRIPTION_PREFERENCE_AGGREGATE,
                    character.id,
                    InscriptionPreference,
                )
            return CharacterOverviewResult(
                "ok",
                CharacterOverview(
                    character=stored_character,
                    inventory=inventory,
                    loadout=loadout,
                    ledger=ledger,
                    world=world,
                    dimension=dimension,
                    inscription_preference=inscription_preference,
                    action=action,
                ),
            )
        except PersistenceError as exc:
            logger.opt(colors=True, exception=exc).error(
                C.join(
                    C.fail("角色状态读取失败"),
                    C.kv("character", character.id),
                )
            )
            return CharacterOverviewResult("failed")

    def load_character_settings(self, character_id: str) -> CharacterSettingsState:
        """读取角色个人展示和自动操作设置。"""

        snapshots = self.character_creation.snapshots
        with self.database.unit_of_work(write=False) as uow:
            return snapshots.require(
                uow,
                CHARACTER_SETTINGS_AGGREGATE,
                str(character_id or "").strip(),
                CharacterSettingsState,
            )

    def load_player_reply_state(
        self,
        evidence: IdentityEvidence,
    ) -> PlayerReplyStateResult:
        """只读加载当前人物头、通知摘要和待领取行动数量。"""

        current = self.load_current_character(evidence)
        if current.status != "ok" or current.character is None:
            return PlayerReplyStateResult(current.status)
        character = current.character
        try:
            snapshots = self.character_creation.snapshots
            with self.database.unit_of_work(write=False) as uow:
                settings = snapshots.require(
                    uow,
                    CHARACTER_SETTINGS_AGGREGATE,
                    character.id,
                    CharacterSettingsState,
                )
                dimension = snapshots.require(
                    uow,
                    CHARACTER_DIMENSION_AGGREGATE,
                    character.id,
                    CharacterDimensionState,
                )
                action = snapshots.load(
                    uow,
                    ACTION_AGGREGATE,
                    character.id,
                    ActionState,
                )
            unread_count = self.notifications.count_unread(
                character.account_id,
                logical_time=evidence.logical_time,
            )
            activity_state = self.activities.load(GLOBAL_ACTIVITY_SCOPE_ID)
            activity_selection = self.global_activities.spotlight(
                activity_state,
                logical_time=evidence.logical_time,
                limit=2,
            )
            return PlayerReplyStateResult(
                "ok",
                PlayerReplyState(
                    character,
                    settings,
                    dimension,
                    activity_spotlights=activity_selection.activities,
                    additional_activity_count=activity_selection.additional_count,
                    unread_notification_count=unread_count,
                    pending_action_count=(len(action.completed()) if action else 0),
                ),
            )
        except PersistenceError as exc:
            logger.opt(colors=True, exception=exc).error(
                C.join(
                    C.fail("玩家回复状态读取失败"),
                    C.kv("character", character.id),
                )
            )
            return PlayerReplyStateResult("failed")

    def shift_character_dimension(
        self,
        character_id: str,
        target_skin_id: str,
        *,
        logical_time: datetime,
    ) -> DimensionShiftResult:
        """角色空闲时原子切换界相，不修改位置、资产或规则状态。"""

        target = self.world_views.require(target_skin_id).skin.id
        snapshots = self.character_creation.snapshots
        normalized_id = str(character_id or "").strip()
        with self.database.unit_of_work() as uow:
            current = snapshots.require(
                uow,
                CHARACTER_DIMENSION_AGGREGATE,
                normalized_id,
                CharacterDimensionState,
            )
            if current.skin_id == target:
                return shift_dimension(
                    current,
                    target,
                    logical_time=logical_time,
                )
            action = snapshots.load(
                uow,
                ACTION_AGGREGATE,
                normalized_id,
                ActionState,
            )
            exploration = snapshots.load(
                uow,
                EXPLORATION_AGGREGATE,
                normalized_id,
                ExplorationState,
            )
            main_action_running = bool(
                action is not None and action.running(ActionSlotKind.MAIN)
            )
            exploration_running = bool(
                exploration is not None
                and exploration.status is ExplorationStatus.RUNNING
            )
            if main_action_running or exploration_running:
                return DimensionShiftResult("main_action_occupied", current)
            result = shift_dimension(
                current,
                target,
                logical_time=logical_time,
            )
            if result.status != "shifted" or result.current is None:
                return result
            snapshots.update(
                uow,
                CHARACTER_DIMENSION_AGGREGATE,
                normalized_id,
                current,
                result.current,
                logical_time,
            )
            uow.commit()
            return result

    def set_mood_header_enabled(
        self,
        character_id: str,
        enabled: bool,
        *,
        logical_time: datetime,
    ) -> CharacterSettingsState:
        """原子更新彩色人物头开关；重复设置相同值不增加版本。"""

        return self._set_character_setting(
            character_id,
            "mood_header_enabled",
            enabled,
            logical_time=logical_time,
        )

    def set_auto_use_medicine(
        self,
        character_id: str,
        enabled: bool,
        *,
        logical_time: datetime,
    ) -> CharacterSettingsState:
        """原子更新探险自动用药开关。"""

        return self._set_character_setting(
            character_id,
            "auto_use_medicine",
            enabled,
            logical_time=logical_time,
        )

    def set_inscription_show_original_name(
        self,
        character_id: str,
        show_original_name: bool,
        *,
        logical_time: datetime,
    ) -> InscriptionPreference:
        """初始化并更新当前角色的铭刻原名展示偏好。"""

        self.inscriptions.initialize_preference(character_id, logical_time=logical_time)
        return self.inscriptions.set_show_original_name(
            character_id,
            show_original_name,
            logical_time=logical_time,
        )

    def load_inscription_preference(
        self,
        character_id: str,
        *,
        logical_time: datetime,
    ) -> InscriptionPreference:
        """读取铭刻偏好；旧角色没有快照时按默认值补齐。"""

        return self.inscriptions.initialize_preference(
            character_id,
            logical_time=logical_time,
        )

    def mark_notification_read(
        self,
        character: CharacterState,
        notification_id: str,
        expected_revision: int,
        *,
        logical_time: datetime,
    ) -> NotificationMarkResult:
        """只允许当前角色标记自己账号的有效未读通知。"""

        notification_id = str(notification_id or "").strip()
        if not notification_id:
            return NotificationMarkResult("not_found")
        unread = self.notifications.list_unread(
            character.account_id,
            logical_time=logical_time,
            limit=100,
        )
        entry = next((value for value in unread if value.id == notification_id), None)
        if entry is None:
            return NotificationMarkResult("not_found")
        if entry.revision != expected_revision:
            return NotificationMarkResult("stale", entry)
        try:
            marked = self.notifications.mark(
                entry.id,
                NotificationStatus.READ,
                expected_revision=expected_revision,
                logical_time=logical_time,
            )
        except ConcurrencyConflict:
            return NotificationMarkResult("stale", entry)
        return NotificationMarkResult("read", marked)

    def _set_character_setting(
        self,
        character_id: str,
        field_name: str,
        enabled: bool,
        *,
        logical_time: datetime,
    ) -> CharacterSettingsState:
        if not isinstance(enabled, bool):
            raise TypeError("角色设置值必须是 bool")
        snapshots = self.character_creation.snapshots
        normalized_id = str(character_id or "").strip()
        with self.database.unit_of_work() as uow:
            current = snapshots.require(
                uow,
                CHARACTER_SETTINGS_AGGREGATE,
                normalized_id,
                CharacterSettingsState,
            )
            if getattr(current, field_name) is enabled:
                return current
            updated = replace(
                current,
                **{field_name: enabled, "revision": current.revision + 1},
            )
            snapshots.update(
                uow,
                CHARACTER_SETTINGS_AGGREGATE,
                normalized_id,
                current,
                updated,
                logical_time,
            )
            uow.commit()
            return updated

    def load_player_reminder_details(
        self,
        character: CharacterState,
        *,
        logical_time: datetime,
        notification_limit: int = 20,
    ) -> PlayerReminderDetailsResult:
        """只读加载未读通知和待领取行动，不改变任何状态。"""

        try:
            snapshots = self.character_creation.snapshots
            with self.database.unit_of_work(write=False) as uow:
                action = snapshots.load(
                    uow,
                    ACTION_AGGREGATE,
                    character.id,
                    ActionState,
                )
            notifications = self.notifications.list_unread(
                character.account_id,
                logical_time=logical_time,
                limit=notification_limit,
            )
            return PlayerReminderDetailsResult(
                "ok",
                PlayerReminderDetails(
                    notifications,
                    action.completed() if action else (),
                ),
            )
        except PersistenceError as exc:
            logger.opt(colors=True, exception=exc).error(
                C.join(
                    C.fail("玩家提醒明细读取失败"),
                    C.kv("character", character.id),
                )
            )
            return PlayerReminderDetailsResult("failed")

    def load_global_activity_views(
        self,
        *,
        logical_time: datetime,
    ) -> GlobalActivityViewsResult:
        """只读列出当前开放且已经注册的全部全服活动。"""

        try:
            state = self.activities.load(GLOBAL_ACTIVITY_SCOPE_ID)
            return GlobalActivityViewsResult(
                "ok",
                self.global_activities.active(state, logical_time=logical_time),
            )
        except PersistenceError as exc:
            logger.opt(colors=True, exception=exc).error(
                C.join(C.fail("全服活动读取失败"), C.kv("scope", GLOBAL_ACTIVITY_SCOPE_ID))
            )
            return GlobalActivityViewsResult("failed")


def message_identity_evidence(
    identity: MessageIdentity,
    *,
    logical_time: datetime,
) -> IdentityEvidence:
    """把驱动器公共身份事实转换成账号底座凭据。"""

    def convert(claim) -> ExternalIdentity:
        return ExternalIdentity(*claim.key)

    return IdentityEvidence(
        id=identity.evidence_id,
        primary=convert(identity.primary),
        aliases=tuple(convert(claim) for claim in identity.aliases),
        source_kind=identity.source_kind,
        logical_time=logical_time,
    )


_services: GameServices | None = None
_services_overridden = False


def build_game_services(
    *,
    database_path: Path | str | None = None,
    busy_timeout_ms: int | None = None,
    identity_secret: str | None = None,
    skin_id: str = DEFAULT_SKIN_ID,
) -> GameServices:
    """组装一次完整服务集合；数据库初始化由生命周期显式执行。"""

    secret = str(
        identity_secret
        if identity_secret is not None
        else config.get("ACCOUNT_IDENTITY_SECRET", "")
    ).strip()
    if len(secret.encode("utf-8")) < 16:
        raise ValueError("ACCOUNT_IDENTITY_SECRET 至少需要 16 字节")
    database = SqliteDatabase(
        database_path or config.database.path,
        busy_timeout_ms=(
            busy_timeout_ms
            if busy_timeout_ms is not None
            else config.database.busy_timeout_ms
        ),
    )
    catalog = assemble_official_catalog()
    world_views = WorldViewCatalog(catalog, PLAYABLE_WORLD_SKIN_IDS)
    content = world_views.require(skin_id)
    disaster_catalog = build_dimensional_disaster_catalog()
    disaster_catalog.validate(catalog, world_views.skin_ids())
    for warning in disaster_catalog.audit().warnings:
        logger.opt(colors=True).warning(C.warn(warning))
    registered_global_activities = GlobalActivityCatalog()
    for registration in global_activity_catalog.registrations():
        registered_global_activities.register(registration)
    for view in world_views.latest_views():
        registered_global_activities.validate(
            content.catalog.activities,
            view.projector,
        )
    workflow = CharacterCreationWorkflow(
        CharacterCreationPlanner(
            content.catalog,
            world_views.skin_ids(),
        )
    )
    snapshots = SnapshotRepository(
        gameplay_snapshot_codec(
            (
                *workflow.codec_registrations(),
                *dimensional_disaster_codec_registrations(),
                *exploration_codec_registrations(),
                *rest_codec_registrations(),
            )
        )
    )
    inventory_engine = InventoryEngine(content.catalog.items)
    character_projector = CharacterProjector(
        content.catalog.characters,
        AttributeResolver(content.catalog.attributes),
        content.catalog.resources,
        ability_ids=frozenset(content.catalog.abilities.ids()),
        trigger_ids=frozenset(content.catalog.triggers.ids()),
        interceptor_ids=frozenset(content.catalog.interceptors.ids()),
        target_constraint_ids=frozenset(content.catalog.target_constraints.ids()),
    )
    player_combat = PlayerCombatProjector(content.catalog, character_projector)
    item_use_service = PersistedItemUseService(
        database,
        CharacterItemUseEngine(
            InventoryAbilityExecutor(
                content.catalog.items,
                inventory_engine,
                GameplayExecutor(
                    content.catalog.ability_engine,
                    content.catalog.trigger_engine,
                ),
            ),
            CharacterEngine(content.catalog.characters),
            character_projector,
        ),
        snapshots,
    )
    action_service = PersistedActionService(
        database,
        content.catalog.action_engine,
        snapshots,
    )
    inscription_service = PersistedInscriptionService(
        database,
        InscriptionEngine(
            content.catalog.items,
            content.catalog.weapons,
            content.catalog.equipment,
        ),
        snapshots,
    )
    loadout_service = PersistedLoadoutService(
        database,
        LoadoutEngine(
            content.catalog.equipment.slots,
            content.catalog.items,
            inventory_engine,
        ),
        snapshots,
    )
    ledger_engine = LedgerEngine(content.catalog.currencies)
    reward_engine = RewardSettlementEngine(
        inventory=inventory_engine,
        ledger=ledger_engine,
        character=CharacterEngine(content.catalog.characters),
        weapon=WeaponEngine(content.catalog.weapons),
    )
    reward_settlement = PersistedRewardSettlementService(
        database,
        reward_engine,
        snapshots,
    )
    battle_reports = BattleReportService(database)
    exploration = ExplorationFeature(
        database,
        content,
        snapshots,
        reward_settlement,
        inventory_engine,
        player_combat,
        battle_reports,
        ExplorationStorageKinds(
            ACTION_AGGREGATE,
            CHARACTER_AGGREGATE,
            INVENTORY_AGGREGATE,
            LOADOUT_AGGREGATE,
            LOOT_AGGREGATE,
            REWARD_CLAIM_AGGREGATE,
            WEAPON_AGGREGATE,
            WORLD_AGGREGATE,
        ),
        RewardSettlementStorageKeys,
    )
    dimensional_disasters = DimensionalDisasterFeature(
        database,
        content,
        disaster_catalog,
        world_views.skin_ids(),
        snapshots,
        reward_settlement,
        player_combat,
        battle_reports,
        DimensionalDisasterStorageKinds(
            ACTION_AGGREGATE,
            ACTIVITY_AGGREGATE,
            CHARACTER_AGGREGATE,
            EXPLORATION_AGGREGATE,
            INVENTORY_AGGREGATE,
            LOADOUT_AGGREGATE,
            REWARD_CLAIM_AGGREGATE,
        ),
        RewardSettlementStorageKeys,
        maximum_battle_rounds=DIMENSIONAL_DISASTER_BATTLE_ROUNDS,
        timezone=config.project.timezone,
    )
    item_sale = ItemSaleFeature(
        database,
        snapshots,
        content.catalog.items,
        inventory_engine,
        ledger_engine,
        ItemSaleStorageKinds(INVENTORY_AGGREGATE, LEDGER_AGGREGATE),
    )
    rest = RestFeature(
        database,
        content.catalog,
        snapshots,
        action_service,
        CharacterEngine(content.catalog.characters),
        character_projector,
        RestStorageKinds(
            ACTION_AGGREGATE,
            CHARACTER_AGGREGATE,
            INVENTORY_AGGREGATE,
            LOADOUT_AGGREGATE,
            EXPLORATION_AGGREGATE,
        ),
    )
    return GameServices(
        database=database,
        accounts=PersistedAccountService(
            database,
            AccountEngine(lambda: f"account-{uuid4().hex}"),
            secret,
        ),
        characters=PersistedCharacterService(database),
        character_creation=PersistedCharacterCreationService(
            database,
            workflow,
            snapshots=snapshots,
        ),
        character_projector=character_projector,
        player_combat=player_combat,
        inscriptions=inscription_service,
        item_use=item_use_service,
        loadouts=loadout_service,
        notifications=NotificationInboxService(database),
        activities=PersistedActivityService(database, content.catalog.activity_engine),
        actions=action_service,
        global_activities=registered_global_activities,
        battle_reports=battle_reports,
        dimensional_disasters=dimensional_disasters,
        exploration=exploration,
        rest=rest,
        item_sale=item_sale,
        world_views=world_views,
        content=content,
    )


def current_game_services() -> GameServices:
    """返回当前服务集合；首次使用时按配置延迟组装。"""

    global _services
    if _services is None:
        _services = build_game_services()
    return _services


def install_game_services(services: GameServices) -> GameServices | None:
    """测试和受控工具临时替换服务集合，并返回旧值。"""

    global _services, _services_overridden
    previous = _services
    _services = services
    _services_overridden = True
    return previous


def restore_game_services(previous: GameServices | None) -> None:
    """恢复测试前的服务集合。"""

    global _services, _services_overridden
    _services = previous
    _services_overridden = False


@OnEvent.connect(priority=200)
def initialize_game_services() -> None:
    """在服务接收消息前校验并初始化当前 SQLite 数据库。"""

    global _services
    if (
        not _services_overridden
        and _services is not None
        and _services.database.path != config.database.path
    ):
        _services = None
    services = current_game_services()
    services.database.initialize()
    services.activities.initialize(
        GLOBAL_ACTIVITY_SCOPE_ID,
        logical_time=datetime.now(ZoneInfo(config.project.timezone)),
    )
    services.dimensional_disasters.maintain(
        logical_time=datetime.now(ZoneInfo(config.project.timezone))
    )


@Scheduler._sync(
    "interval",
    seconds=60,
    id="game_exploration_settlement",
    max_instances=1,
    coalesce=True,
)
def settle_running_explorations() -> None:
    """后台发现到期探险；单个批次仍由应用服务独立原子提交。"""

    services = current_game_services()
    try:
        services.exploration.settle_all_due(
            logical_time=datetime.now(ZoneInfo(config.project.timezone))
        )
    except Exception as exc:
        logger.opt(colors=True, exception=exc).error(C.fail("探险后台结算失败"))


@Scheduler._sync(
    "interval",
    seconds=60,
    id="game_dimensional_disaster_maintenance",
    max_instances=1,
    coalesce=True,
)
def maintain_dimensional_disasters() -> None:
    """开放当前灾厄窗口，并为到期事件封榜和发放唯一遗羽。"""

    services = current_game_services()
    try:
        services.dimensional_disasters.maintain(
            logical_time=datetime.now(ZoneInfo(config.project.timezone))
        )
    except Exception as exc:
        logger.opt(colors=True, exception=exc).error(C.fail("次元灾厄维护失败"))


@Scheduler._sync(
    "interval",
    seconds=60,
    id="game_rest_settlement",
    max_instances=1,
    coalesce=True,
)
def settle_completed_rest() -> None:
    """后台完成已经达到三十分钟的休息行动。"""

    services = current_game_services()
    try:
        services.rest.settle_all_due(
            logical_time=datetime.now(ZoneInfo(config.project.timezone))
        )
    except Exception as exc:
        logger.opt(colors=True, exception=exc).error(C.fail("休息后台结算失败"))


@Scheduler._sync(
    "interval",
    hours=24,
    id="game_battle_report_cleanup",
    max_instances=1,
    coalesce=True,
)
def cleanup_battle_reports() -> None:
    """每天清理过期战报：七天删除明细，三十天删除摘要。"""

    services = current_game_services()
    try:
        services.battle_reports.cleanup(
            logical_time=datetime.now(ZoneInfo(config.project.timezone))
        )
    except Exception as exc:
        logger.opt(colors=True, exception=exc).error(C.fail("战报保留期清理失败"))


__all__ = [
    "CharacterCreationCommandResult",
    "CharacterOverview",
    "CharacterOverviewResult",
    "CurrentCharacterResult",
    "GameServices",
    "GlobalActivityViewsResult",
    "PlayerReplyState",
    "PlayerReplyStateResult",
    "PlayerReminderDetails",
    "PlayerReminderDetailsResult",
    "build_game_services",
    "cleanup_battle_reports",
    "current_game_services",
    "initialize_game_services",
    "install_game_services",
    "message_identity_evidence",
    "restore_game_services",
    "settle_running_explorations",
    "settle_completed_rest",
]
