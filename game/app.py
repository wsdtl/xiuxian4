"""游戏数据库、内容和服务的启动装配入口。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from game.content import DEFAULT_SKIN_ID, OfficialContent, build_official_content
from game.core.account import AccountEngine, ExternalIdentity, IdentityEvidence
from game.core.gameplay import (
    ActionRecord,
    ActionState,
    CharacterState,
    InventoryState,
    LedgerState,
    LoadoutState,
    NotificationEntry,
    WorldState,
)
from game.core.persistence import (
    ACTION_AGGREGATE,
    ConcurrencyConflict,
    INVENTORY_AGGREGATE,
    LEDGER_AGGREGATE,
    LOADOUT_AGGREGATE,
    PersistenceError,
    NotificationInboxService,
    PersistedActivityService,
    PersistedAccountService,
    PersistedCharacterCreationService,
    PersistedCharacterService,
    SqliteDatabase,
    WORLD_AGGREGATE,
)
from game.rules.character import (
    CHARACTER_SETTINGS_AGGREGATE,
    CharacterCreationPlanner,
    CharacterCreationReceipt,
    CharacterCreationRequest,
    CharacterCreationWorkflow,
    CharacterIdentityViolation,
    CharacterSettingsState,
    PRIMARY_LEDGER_ID,
    PRIMARY_WORLD_ID,
    character_creation_context,
)
from game.rules.activity import (
    GLOBAL_ACTIVITY_SCOPE_ID,
    GlobalActivityCatalog,
    GlobalActivityView,
    global_activity_catalog,
)
from launch import C, OnEvent, config, logger
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


@dataclass(frozen=True)
class PlayerReplyState:
    """统一人物头和全局通栏需要的只读状态。"""

    character: CharacterState
    settings: CharacterSettingsState
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
class GameServices:
    """命令层可以使用的完整游戏服务集合。"""

    database: SqliteDatabase
    accounts: PersistedAccountService
    characters: PersistedCharacterService
    character_creation: PersistedCharacterCreationService
    notifications: NotificationInboxService
    activities: PersistedActivityService
    global_activities: GlobalActivityCatalog
    content: OfficialContent

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
            return CurrentCharacterResult("ok", character)
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
                action = snapshots.load(
                    uow,
                    ACTION_AGGREGATE,
                    character.id,
                    ActionState,
                )
            return CharacterOverviewResult(
                "ok",
                CharacterOverview(
                    character,
                    inventory,
                    loadout,
                    ledger,
                    world,
                    action,
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

    def set_mood_header_enabled(
        self,
        character_id: str,
        enabled: bool,
        *,
        logical_time: datetime,
    ) -> CharacterSettingsState:
        """原子更新彩色人物头开关；重复设置相同值不增加版本。"""

        snapshots = self.character_creation.snapshots
        normalized_id = str(character_id or "").strip()
        with self.database.unit_of_work() as uow:
            current = snapshots.require(
                uow,
                CHARACTER_SETTINGS_AGGREGATE,
                normalized_id,
                CharacterSettingsState,
            )
            if current.mood_header_enabled is enabled:
                return current
            updated = replace(
                current,
                mood_header_enabled=enabled,
                revision=current.revision + 1,
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
    content = build_official_content(skin_id)
    registered_global_activities = GlobalActivityCatalog()
    for registration in global_activity_catalog.registrations():
        registered_global_activities.register(registration)
    registered_global_activities.validate(
        content.catalog.activities,
        content.projector,
    )
    workflow = CharacterCreationWorkflow(
        CharacterCreationPlanner(content.catalog)
    )
    return GameServices(
        database=database,
        accounts=PersistedAccountService(
            database,
            AccountEngine(lambda: f"account-{uuid4().hex}"),
            secret,
        ),
        characters=PersistedCharacterService(database),
        character_creation=PersistedCharacterCreationService(database, workflow),
        notifications=NotificationInboxService(database),
        activities=PersistedActivityService(database, content.catalog.activity_engine),
        global_activities=registered_global_activities,
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
    "current_game_services",
    "initialize_game_services",
    "install_game_services",
    "message_identity_evidence",
    "restore_game_services",
]
