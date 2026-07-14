"""角色组件的业务调用与协议中立回复。"""

from __future__ import annotations

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from game.content import (
    MORTAL_PHYSIQUE_FEATURE_ID,
    ORIGIN_HUMAN_FEATURE_ID,
    PRIMARY_CURRENCY_ID,
    SMALL_HEALTH_MEDICINE_ITEM_ID,
    SMALL_SPIRIT_MEDICINE_ITEM_ID,
    STARTER_WEAPON_ID,
    STARTING_CITY_ID,
)
from game.core.account import IdentityEvidence
from game.core.gameplay import HEALTH_CURRENT, HEALTH_MAXIMUM, SPIRIT_CURRENT, SPIRIT_MAXIMUM
from game.rules.character import CharacterCreationReceipt
from game.app import (
    CharacterCreationCommandResult,
    current_game_services,
    message_identity_evidence,
)
from launch import C, config, logger
from launch.adapter import current_message_context, manager
from message import Action, DocumentMessage, M


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
        client_id=context.client_id,
        evidence=evidence,
        requested_name=requested_name,
        sender_name=context.sender_name,
    )


async def _execute(
    *,
    client_id: str,
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
    await manager.send(_result_message(result), client_id)


def _result_message(result: CharacterCreationCommandResult) -> DocumentMessage:
    if result.status == "created" and result.receipt is not None:
        return _created_message(result.receipt)
    if result.status == "existing" and result.existing_character is not None:
        character = result.existing_character
        return (
            M.document()
            .header(character.name)
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
            .line("角色名不能为空，且不能超过 24 个字符。")
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
    progression = next(iter(character.progressions.values()))
    quantities = {
        stack.definition_id: stack.quantity
        for stack in receipt.inventory.stacks.values()
    }
    wallet = next(
        account
        for account in receipt.ledger.accounts.values()
        if account.owner_id == character.id and account.currency_id == PRIMARY_CURRENCY_ID
    )
    return (
        M.document()
        .header(character.name, f" Lv{progression.level}")
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
        .field("武器", projector.name(STARTER_WEAPON_ID))
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


def _now() -> datetime:
    return datetime.now(ZoneInfo(config.project.timezone))


__all__ = [
    "create_character",
]
