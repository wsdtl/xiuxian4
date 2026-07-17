"""角色组件的业务调用与协议中立回复。"""

from __future__ import annotations

import asyncio
from datetime import datetime
from math import ceil
from zoneinfo import ZoneInfo

from game.content import (
    CHARACTER_LEVEL_PROGRESSION_ID,
    MORTAL_PHYSIQUE_FEATURE_ID,
    ORIGIN_HUMAN_FEATURE_ID,
    PRIMARY_CURRENCY_ID,
    SMALL_HEALTH_MEDICINE_ITEM_ID,
    SMALL_SPIRIT_MEDICINE_ITEM_ID,
    STARTING_CITY_ID,
)
from game.core.account import IdentityEvidence
from game.core.gameplay import (
    COMBAT_ATTACK,
    COMBAT_DEFENSE,
    COMBAT_SPEED,
    HEALTH_CURRENT,
    HEALTH_MAXIMUM,
    SPIRIT_CURRENT,
    SPIRIT_MAXIMUM,
    equipment_state_from_instance,
    weapon_state_from_instance,
)
from game.app import (
    CharacterCreationCommandResult,
    CharacterOverview,
    CharacterOverviewResult,
    CurrentCharacterResult,
    current_game_services,
    message_identity_evidence,
)
from game.rules.character import CharacterCreationReceipt, CharacterSettingsState
from launch import C, config, logger
from launch.adapter import current_message_context
from message import Action, DocumentMessage, M

from ..reply import send_game_reply
from ..presentation import (
    character_header_color,
    character_realm_name,
)


async def create_character(requested_name: str) -> None:
    """从公共消息上下文读取当前玩家并执行创建。"""

    context = current_message_context()
    if context is None:
        raise RuntimeError("创建角色缺少当前消息上下文")
    logical_time = _now()
    evidence = message_identity_evidence(
        context.identity,
        logical_time=logical_time,
    )
    await _execute(
        evidence=evidence,
        requested_name=requested_name,
        sender_name=context.sender_name,
    )


async def view_character(result: CharacterOverviewResult) -> None:
    """展示依赖层已经读取的当前角色状态。"""

    await send_game_reply(_overview_message(result))


async def mood(message: str, current: CurrentCharacterResult) -> None:
    """查看或修改当前角色的彩色人物头开关。"""

    if current.status != "ok" or current.character is None:
        await send_game_reply(_mood_unavailable_message())
        return
    services = current_game_services()
    try:
        settings = await asyncio.to_thread(
            services.load_character_settings,
            current.character.id,
        )
        requested = str(message or "").strip().casefold()
        if requested:
            on_words = {"开启", "打开", "启用", "开", "on", "1"}
            off_words = {"关闭", "关掉", "停用", "关", "off", "0"}
            if requested in on_words:
                enabled = True
            elif requested in off_words:
                enabled = False
            else:
                await send_game_reply(
                    _mood_message(settings, invalid=True)
                )
                return
            settings = await asyncio.to_thread(
                services.set_mood_header_enabled,
                current.character.id,
                enabled,
                logical_time=_now(),
            )
    except Exception as exc:
        logger.opt(colors=True, exception=exc).error(
            C.join(
                C.fail("心情设置执行失败"),
                C.kv("character", current.character.id),
            )
        )
        await send_game_reply(_mood_unavailable_message())
        return
    await send_game_reply(_mood_message(settings))


async def _execute(
    *,
    evidence: IdentityEvidence,
    requested_name: str,
    sender_name: str,
) -> None:
    services = current_game_services()
    try:
        result = await asyncio.to_thread(
            services.create_character,
            evidence,
            requested_name=requested_name,
            platform_name=sender_name,
        )
    except Exception as exc:
        logger.opt(colors=True, exception=exc).error(
            C.join(C.fail("创建角色命令执行失败"), C.kv("evidence", evidence.id))
        )
        result = CharacterCreationCommandResult("failed")
    await send_game_reply(_result_message(result))


def _result_message(result: CharacterCreationCommandResult) -> DocumentMessage:
    if result.status == "created" and result.receipt is not None:
        return _created_message(result.receipt)
    if result.status == "existing" and result.existing_character is not None:
        return (
            M.document()
            .section("角色已存在", icon="notice")
            .field("状态", "已建立")
            .line("当前账号不能重复创建角色。")
            .build()
        )
    if result.status == "name_required":
        return (
            M.document()
            .header("创建角色")
            .section("需要角色名", icon="notice")
            .line("发送: 创建角色 名称")
            .actions(
                (
                    Action(
                        "character.create.fill_name",
                        "填写名称",
                        "创建角色 青衫客",
                        behavior="fill",
                        style="secondary",
                    ),
                )
            )
            .build()
        )
    if result.status == "name_invalid":
        return (
            M.document()
            .header("创建角色")
            .section("名称不可用", icon="notice")
            .line("角色名只能使用中文、英文字母或数字，显示宽度不能超过 12。")
            .line("发送: 创建角色 名称")
            .actions(
                (
                    Action(
                        "character.create.valid_name",
                        "填写名称",
                        "创建角色 ",
                        behavior="fill",
                        style="primary",
                    ),
                )
            )
            .build()
        )
    if result.status == "identity_conflict":
        return (
            M.document()
            .header("创建角色")
            .section("身份归属冲突", icon="notice")
            .line("当前平台身份对应多个账号，暂时不能创建角色。")
            .build()
        )
    return (
        M.document()
        .header("创建角色")
        .section("创建失败", icon="notice")
        .line("当前没有写入角色，请稍后重试。")
        .build()
    )


def _created_message(receipt: CharacterCreationReceipt) -> DocumentMessage:
    services = current_game_services()
    projector = services.content.projector
    character = receipt.character
    quantities = {
        stack.definition_id: stack.quantity
        for stack in receipt.inventory.stacks.values()
    }
    wallet = next(
        account
        for account in receipt.ledger.accounts.values()
        if account.owner_id == character.id and account.currency_id == PRIMARY_CURRENCY_ID
    )
    starter_instance = receipt.inventory.instances[receipt.starter_weapon.asset_id]
    starter_name = services.content.gear_projector.weapon(
        receipt.starter_weapon,
        starter_instance,
    ).name
    return (
        M.document()
        .section("角色创建", icon="profile")
        .row(
            ("种族", projector.name(ORIGIN_HUMAN_FEATURE_ID)),
            ("体质", projector.name(MORTAL_PHYSIQUE_FEATURE_ID)),
        )
        .row(
            (
                "血气",
                f"{int(character.resources[HEALTH_CURRENT])}/{int(character.core_attributes[HEALTH_MAXIMUM])}",
            ),
            (
                "灵力",
                f"{int(character.resources[SPIRIT_CURRENT])}/{int(character.core_attributes[SPIRIT_MAXIMUM])}",
            ),
        )
        .section("初始行囊", icon="inventory")
        .field("武器", starter_name)
        .row(
            (projector.name(PRIMARY_CURRENCY_ID), wallet.balance),
            (
                projector.name(SMALL_HEALTH_MEDICINE_ITEM_ID),
                f"x{quantities[SMALL_HEALTH_MEDICINE_ITEM_ID]}",
            ),
            (
                projector.name(SMALL_SPIRIT_MEDICINE_ITEM_ID),
                f"x{quantities[SMALL_SPIRIT_MEDICINE_ITEM_ID]}",
            ),
        )
        .section("落脚之地", icon="world")
        .field("城池", projector.name(STARTING_CITY_ID))
        .build()
    )


def _overview_message(result: CharacterOverviewResult) -> DocumentMessage:
    if result.status == "ok" and result.overview is not None:
        return _character_overview_message(result.overview)
    if result.status == "not_created":
        return (
            M.document()
            .header("我的角色")
            .section("建档状态", icon="notice")
            .line("尚未创建角色")
            .note("发送: 创建角色 名称")
            .actions(
                (
                    Action(
                        "character.create",
                        "创建角色",
                        "创建角色 ",
                        behavior="fill",
                        style="primary",
                    ),
                )
            )
            .build()
        )
    if result.status == "identity_conflict":
        return (
            M.document()
            .header("我的角色")
            .section("身份归属冲突", icon="notice")
            .line("当前平台身份对应多个账号，暂时不能查看角色。")
            .build()
        )
    return (
        M.document()
        .header("我的角色")
        .section("读取失败", icon="notice")
        .line("当前没有读取到角色状态，请稍后重试。")
        .build()
    )


def _mood_message(
    settings: CharacterSettingsState,
    *,
    invalid: bool = False,
) -> DocumentMessage:
    now_value = _now()
    color = character_header_color(settings, now_value)
    builder = (
        M.document()
        .section("心情", icon="mood")
        .row(
            ("当前状态", "开启" if settings.mood_header_enabled else "关闭"),
            ("今日颜色", color or "默认"),
        )
    )
    if invalid:
        builder.line("心情只支持 开启 或 关闭。")
    else:
        builder.line("开启后，回复顶部的人物头会按星期轮换颜色。")
    return (
        builder.actions(
            (
                Action(
                    "character.mood.enable",
                    "开启",
                    "心情 开启",
                    behavior="send",
                ),
                Action(
                    "character.mood.disable",
                    "关闭",
                    "心情 关闭",
                    behavior="send",
                    style="secondary",
                ),
            )
        )
        .build()
    )


def _mood_unavailable_message() -> DocumentMessage:
    return (
        M.document()
        .header("心情")
        .section("读取失败", icon="notice")
        .line("当前没有读取到角色设置，请稍后重试。")
        .build()
    )


def _character_overview_message(overview: CharacterOverview) -> DocumentMessage:
    services = current_game_services()
    projector = services.content.projector
    character = overview.character
    progression = character.progressions[CHARACTER_LEVEL_PROGRESSION_ID]
    progression_definition = services.content.catalog.characters.progressions.require(
        progression.definition_id
    )
    required = progression_definition.required_for_next_level(progression.level)
    experience = "已满级" if required is None else f"{progression.experience}/{required}"
    wallet = next(
        (
            account
            for account in overview.ledger.accounts.values()
            if account.owner_id == character.id
            and account.currency_id == PRIMARY_CURRENCY_ID
        ),
        None,
    )
    presence = next(
        (
            value
            for value in overview.world.presences.values()
            if value.owner_id == character.id
        ),
        None,
    )
    location = "未知"
    if presence is not None:
        position = presence.position
        location = (
            _projected_name(position.location_id)
            if position.location_id is not None
            else f"({position.x}, {position.y})"
        )
    weapon_text = "未装备"
    weapon_asset_id = overview.loadout.weapon_asset_id
    if weapon_asset_id is not None:
        instance = overview.inventory.instances.get(weapon_asset_id)
        if instance is not None:
            weapon = weapon_state_from_instance(instance)
            weapon_text = " | ".join(
                (
                    services.content.gear_projector.weapon(
                        weapon,
                        instance,
                        inscription_preference=overview.inscription_preference,
                    ).name,
                    f"Lv{weapon.level}",
                )
            )
    equipment_names = []
    for asset_id in overview.loadout.equipment_asset_ids:
        instance = overview.inventory.instances.get(asset_id)
        if instance is None:
            continue
        equipment = equipment_state_from_instance(instance)
        equipment_names.append(
            services.content.gear_projector.equipment(
                equipment,
                instance,
                inscription_preference=overview.inscription_preference,
            ).name
        )
    equipment_names = tuple(equipment_names)
    equipment_text = "无" if not equipment_names else ", ".join(equipment_names)
    return (
        M.document()
        .section("修行状态", icon="profile")
        .row(("境界", character_realm_name(character, projector)), ("经验", experience))
        .row(
            (
                "血气",
                f"{_number(character.resources[HEALTH_CURRENT])}/{_number(character.core_attributes[HEALTH_MAXIMUM])}",
            ),
            (
                "灵力",
                f"{_number(character.resources[SPIRIT_CURRENT])}/{_number(character.core_attributes[SPIRIT_MAXIMUM])}",
            ),
        )
        .section("基础属性", icon="combat")
        .row(
            ("最大血气", _number(character.core_attributes[HEALTH_MAXIMUM])),
            ("最大灵力", _number(character.core_attributes[SPIRIT_MAXIMUM])),
        )
        .row(
            ("攻击", _number(character.core_attributes[COMBAT_ATTACK])),
            ("防御", _number(character.core_attributes[COMBAT_DEFENSE])),
        )
        .field("速度", _number(character.core_attributes[COMBAT_SPEED]))
        .section("当前装配", icon="inventory")
        .field("武器", weapon_text)
        .field("装备", f"{len(equipment_names)}/6 | {equipment_text}")
        .section("当前状态", icon="world")
        .row(("位置", location), (projector.name(PRIMARY_CURRENCY_ID), wallet.balance if wallet else 0))
        .field("行动", _action_text(overview))
        .build()
    )


def _projected_name(definition_id: str) -> str:
    try:
        return current_game_services().content.projector.name(definition_id)
    except KeyError:
        return definition_id


def _action_text(overview: CharacterOverview) -> str:
    if overview.action is None:
        return "空闲"
    running = overview.action.running()
    if running:
        record = running[0]
        remaining_seconds = max(0, int((record.completes_at - _now()).total_seconds()))
        remaining_minutes = ceil(remaining_seconds / 60)
        return f"{_projected_name(record.definition_id)} | 剩余 {remaining_minutes} 分钟"
    completed = overview.action.completed()
    if completed:
        return f"{len(completed)} 项待领取"
    return "空闲"


def _number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def _now() -> datetime:
    return datetime.now(ZoneInfo(config.project.timezone))


__all__ = [
    "create_character",
    "mood",
    "view_character",
]
