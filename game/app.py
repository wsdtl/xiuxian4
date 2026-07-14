"""游戏数据库、内容和服务的启动装配入口。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from game.content import DEFAULT_SKIN_ID, OfficialContent, build_official_content
from game.core.account import AccountEngine, ExternalIdentity, IdentityEvidence
from game.core.gameplay import CharacterState
from game.core.persistence import (
    ConcurrencyConflict,
    PersistenceError,
    PersistedAccountService,
    PersistedCharacterCreationService,
    PersistedCharacterService,
    SqliteDatabase,
)
from game.rules.character import (
    CharacterCreationPlanner,
    CharacterCreationReceipt,
    CharacterCreationRequest,
    CharacterCreationWorkflow,
    CharacterIdentityViolation,
    character_creation_context,
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
class GameServices:
    """命令层可以使用的完整游戏服务集合。"""

    database: SqliteDatabase
    accounts: PersistedAccountService
    characters: PersistedCharacterService
    character_creation: PersistedCharacterCreationService
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
            return CharacterCreationCommandResult(
                status,
                existing_character=self.characters.load_for_account(account_id),
            )
        except ConcurrencyConflict:
            return CharacterCreationCommandResult(
                "existing",
                existing_character=self.characters.load_for_account(account_id),
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
    current_game_services().database.initialize()


__all__ = [
    "CharacterCreationCommandResult",
    "GameServices",
    "build_game_services",
    "current_game_services",
    "initialize_game_services",
    "install_game_services",
    "message_identity_evidence",
    "restore_game_services",
]
