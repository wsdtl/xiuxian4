"""队伍命令参数解析、邀请按钮和成员状态展示。"""

from __future__ import annotations

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from game.app import CurrentCharacterResult, current_game_services
from game.core.account import ExternalIdentity
from game.core.gameplay import Party, SocialRequest
from launch import C, config, logger
from launch.adapter import current_message_context
from launch.paths import public_url
from message import Action, DocumentMessage, M
from message.schema import FieldSeparator

from ..reply import send_game_reply


async def view(current: CurrentCharacterResult) -> None:
    character = _character(current)
    if character is None:
        await send_game_reply(_failure("当前没有可用角色"))
        return
    try:
        result = await asyncio.to_thread(
            current_game_services().party.view,
            character.id,
            logical_time=_now(),
        )
        await send_game_reply(
            _view_message(result.party, result.incoming_requests, character.id)
        )
    except Exception as exc:
        await _failed("队伍读取失败", character.id, exc)


async def create(current: CurrentCharacterResult) -> None:
    character = _character(current)
    if character is None:
        await send_game_reply(_failure("当前没有可用角色"))
        return
    try:
        result = await asyncio.to_thread(
            current_game_services().party.create,
            _operation_id("party-create"),
            character.id,
            logical_time=_now(),
        )
        if result.status == "created" and result.party is not None:
            reply = _success("队伍", "队伍已经创建，你现在是队长")
        elif result.status == "already_member":
            reply = _failure("你已经在一支队伍中")
        else:
            reply = _failure(result.failure_message or "队伍创建没有完成")
        await send_game_reply(reply)
    except Exception as exc:
        await _failed("创建队伍失败", character.id, exc)


async def invite(message: str, current: CurrentCharacterResult) -> None:
    character = _character(current)
    target_token = str(message or "").strip().split(maxsplit=1)
    if character is None:
        await send_game_reply(_failure("当前没有可用角色"))
        return
    if not target_token:
        await send_game_reply(_failure("发送：邀请组队 玩家"))
        return
    external_id = target_token[0]
    target = await asyncio.to_thread(_resolve_target, external_id)
    if target is None:
        await send_game_reply(_failure("对方尚未创建角色，无法邀请组队"))
        return
    try:
        result = await asyncio.to_thread(
            current_game_services().party.invite,
            _operation_id("party-invite"),
            character.id,
            target.id,
            logical_time=_now(),
        )
        if result.status in {"invited", "already_pending"}:
            text = "已经向对方发出队伍邀请" if result.status == "invited" else "双方已有一份待处理队伍邀请"
            reply = M.document().section("队伍邀请", icon="player").line(text).field("有效期", "10分钟").build()
        else:
            reply = _failure(result.failure_message or "队伍邀请没有发出")
        await send_game_reply(reply)
    except Exception as exc:
        await _failed("邀请组队失败", character.id, exc)


async def accept(message: str, current: CurrentCharacterResult) -> None:
    await _resolve_invitation(message, current, accepted=True)


async def reject(message: str, current: CurrentCharacterResult) -> None:
    await _resolve_invitation(message, current, accepted=False)


async def _resolve_invitation(message, current, *, accepted: bool) -> None:
    character = _character(current)
    request_id = str(message or "").strip()
    if character is None:
        await send_game_reply(_failure("当前没有可用角色"))
        return
    if not request_id:
        await send_game_reply(_failure("队伍请求编号不能为空"))
        return
    try:
        method = current_game_services().party.accept if accepted else current_game_services().party.reject
        result = await asyncio.to_thread(
            method,
            _operation_id("party-accept" if accepted else "party-reject"),
            character.id,
            request_id,
            logical_time=_now(),
        )
        if accepted and result.status == "accepted":
            reply = _success("组队", "已经加入队伍")
        elif not accepted and result.status == "rejected":
            reply = _success("组队", "已经拒绝这份队伍邀请")
        else:
            reply = _failure(result.failure_message or "队伍邀请没有处理")
        await send_game_reply(reply)
    except Exception as exc:
        await _failed("处理队伍邀请失败", character.id, exc)


async def leave(current: CurrentCharacterResult) -> None:
    await _simple_party_action(current, "party-leave", "leave", "已经退出队伍")


async def kick(message: str, current: CurrentCharacterResult) -> None:
    await _target_party_action(current, message, "kick", "请离队伍", "已将成员请离队伍")


async def transfer(message: str, current: CurrentCharacterResult) -> None:
    await _target_party_action(current, message, "transfer", "转让队长", "已经转让队长")


async def preview_disband(current: CurrentCharacterResult) -> None:
    character = _character(current)
    if character is None:
        await send_game_reply(_failure("当前没有可用角色"))
        return
    try:
        result = await asyncio.to_thread(
            current_game_services().party.view,
            character.id,
            logical_time=_now(),
        )
        party = result.party
        if party is None:
            await send_game_reply(_failure("当前没有队伍"))
            return
        if party.leader_id != character.id:
            await send_game_reply(_failure("只有队长可以解散队伍"))
            return
        await send_game_reply(
            M.document()
            .section("确认解散队伍", icon="notice")
            .line(f"解散后，当前 {len(party.members)} 名成员的队伍关系会立即结束。")
            .actions((
                Action(
                    "party.disband.confirm",
                    "确认解散",
                    f"party_disband_confirm {result.state_revision}",
                    behavior="send",
                    style="secondary",
                ),
            ))
            .build()
        )
    except Exception as exc:
        await _failed("解散队伍预览失败", character.id, exc)


async def confirm_disband(message: str, current: CurrentCharacterResult) -> None:
    character = _character(current)
    if character is None:
        await send_game_reply(_failure("当前没有可用角色"))
        return
    try:
        revision = int(str(message or "").strip())
        result = await asyncio.to_thread(
            current_game_services().party.disband,
            _operation_id("party-disband"),
            character.id,
            expected_revision=revision,
            logical_time=_now(),
        )
        await send_game_reply(
            _success("组队", "队伍已经解散")
            if result.status == "disbanded"
            else _failure(result.failure_message or "队伍解散没有完成")
        )
    except ValueError:
        await send_game_reply(_failure("解散确认已经失效"))
    except Exception as exc:
        await _failed("解散队伍失败", character.id, exc)


async def set_ready(current: CurrentCharacterResult, ready: bool) -> None:
    character = _character(current)
    if character is None:
        await send_game_reply(_failure("当前没有可用角色"))
        return
    try:
        services = current_game_services()
        party_view = await asyncio.to_thread(
            services.party.view,
            character.id,
            logical_time=_now(),
        )
        if party_view.party is None:
            await send_game_reply(_failure("当前没有队伍"))
            return
        result = await asyncio.to_thread(
            services.party_battles.set_ready,
            _operation_id("party-battle-ready"),
            party_view.party.id,
            character.id,
            ready,
            logical_time=_now(),
        )
        text = "已标记为准备" if ready else "已取消准备"
        await send_game_reply(
            _success("组队", text)
            if result.status in {"ready", "unready", "replayed"}
            else _failure(result.failure_message or "准备状态没有更新")
        )
    except Exception as exc:
        await _failed("更新准备状态失败", character.id, exc)


async def party_battle_view(current: CurrentCharacterResult) -> None:
    character = _character(current)
    if character is None:
        await send_game_reply(_failure("当前没有可用角色"))
        return
    try:
        party_view = await asyncio.to_thread(
            current_game_services().party.view,
            character.id,
            logical_time=_now(),
        )
        if party_view.party is None:
            await send_game_reply(_failure("请先加入队伍"))
            return
        challenge = await asyncio.to_thread(
            current_game_services().party_battles.view,
            party_view.party.id,
        )
        await send_game_reply(_party_battle_message(party_view.party, challenge.challenge, character.id))
    except Exception as exc:
        await _failed("组队挑战读取失败", character.id, exc)


async def select_party_battle(message: str, current: CurrentCharacterResult) -> None:
    character = _character(current)
    if character is None:
        await send_game_reply(_failure("当前没有可用角色"))
        return
    try:
        level = int(str(message or "").strip())
    except ValueError:
        await send_game_reply(_failure("发送：选择组队挑战 等级"))
        return
    try:
        party_view = await asyncio.to_thread(
            current_game_services().party.view,
            character.id,
            logical_time=_now(),
        )
        if party_view.party is None:
            await send_game_reply(_failure("请先加入队伍"))
            return
        result = await asyncio.to_thread(
            current_game_services().party_battles.select,
            _operation_id("party-battle-select"),
            party_view.party.id,
            character.id,
            level,
            logical_time=_now(),
        )
        if result.status in {"selected", "replayed"}:
            reply = _success("组队挑战", _selection_text(result.challenge))
        else:
            reply = _failure(result.failure_message or "组队首领选择没有完成")
        await send_game_reply(reply)
    except Exception as exc:
        await _failed("选择组队首领失败", character.id, exc)


async def start_party_battle(current: CurrentCharacterResult) -> None:
    character = _character(current)
    if character is None:
        await send_game_reply(_failure("当前没有可用角色"))
        return
    try:
        party_view = await asyncio.to_thread(
            current_game_services().party.view,
            character.id,
            logical_time=_now(),
        )
        if party_view.party is None:
            await send_game_reply(_failure("请先加入队伍"))
            return
        result = await asyncio.to_thread(
            current_game_services().party_battles.challenge,
            _operation_id("party-battle-start"),
            party_view.party.id,
            character.id,
            logical_time=_now(),
        )
        if result.status in {"victory", "draw", "defeated", "replayed"}:
            builder = M.document().section("组队战报", icon="combat")
            if result.challenge is not None:
                builder.field("来源世界", _source_world_name(result.challenge.source_world_id))
            builder.row(
                ("首领", result.enemy_name),
                ("结果", "胜利" if result.victory else "平局" if result.draw else "战败"),
            )
            builder.field("战斗行动", result.turns)
            for character_id, lines in result.reward_summaries.items():
                builder.item(character_id, _character_name(character_id), "：", "；".join(lines))
            if result.share_id:
                builder.field(
                    "战报",
                    M.link("查看完整战报", public_url("battle", result.share_id)),
                )
            reply = builder.build()
        else:
            reply = _failure(result.failure_message or "组队挑战没有开始")
        await send_game_reply(reply)
    except Exception as exc:
        await _failed("组队挑战执行失败", character.id, exc)


async def _simple_party_action(current, prefix, method_name, success_text) -> None:
    character = _character(current)
    if character is None:
        await send_game_reply(_failure("当前没有可用角色"))
        return
    try:
        method = getattr(current_game_services().party, method_name)
        result = await asyncio.to_thread(method, _operation_id(prefix), character.id, logical_time=_now())
        await send_game_reply(_success("组队", success_text) if result.status in {"member.left", "disbanded"} else _failure(result.failure_message or "队伍操作没有完成"))
    except Exception as exc:
        await _failed("队伍操作失败", character.id, exc)


async def _target_party_action(current, message, method_name, title, success_text) -> None:
    character = _character(current)
    token = str(message or "").strip().split(maxsplit=1)
    if character is None:
        await send_game_reply(_failure("当前没有可用角色"))
        return
    if not token:
        await send_game_reply(_failure(f"发送：{title} 玩家"))
        return
    target = await asyncio.to_thread(_resolve_target, token[0])
    if target is None:
        await send_game_reply(_failure("对方尚未创建角色"))
        return
    try:
        method = getattr(current_game_services().party, method_name)
        result = await asyncio.to_thread(method, _operation_id(f"party-{method_name}"), character.id, target.id, logical_time=_now())
        success_status = "leadership.transferred" if method_name == "transfer" else "member.removed"
        await send_game_reply(_success("组队", success_text) if result.status == success_status else _failure(result.failure_message or "队伍操作没有完成"))
    except Exception as exc:
        await _failed(f"{title}失败", character.id, exc)


def _view_message(
    party: Party | None,
    requests: tuple[SocialRequest, ...],
    character_id: str,
) -> DocumentMessage:
    builder = M.document().section("组队", icon="player")
    actions = []
    if party is None:
        builder.line("当前没有加入队伍")
        actions.append(Action("party.create", "创建队伍", "创建队伍", behavior="send"))
    else:
        leader = _character_name(party.leader_id)
        capacity = current_game_services().content.catalog.parties.require(
            party.definition_id
        ).capacity
        builder.row(("队长", leader), ("人数", f"{len(party.members)}/{capacity}"))
        for member in sorted(party.members.values(), key=lambda value: value.slot):
            name = _character_name(member.subject_id)
            marker = "队长" if member.subject_id == party.leader_id else "成员"
            ready = "已准备" if member.ready else "未准备"
            builder.line(f"{member.slot + 1}. {name}", FieldSeparator(), marker, FieldSeparator(), ready)
        if party.leader_id == character_id:
            actions.extend(
                (
                    Action("party.leave", "退出", "退出队伍", behavior="send"),
                    Action("party.disband", "解散", "解散队伍", behavior="send", style="secondary"),
                )
            )
        else:
            actions.append(Action("party.leave", "退出", "退出队伍", behavior="send"))
        actions.extend(
            (
                Action("party.ready", "准备", "准备", behavior="send"),
                Action("party.unready", "取消准备", "取消准备", behavior="send", style="secondary"),
            )
        )
    if requests:
        builder.section("队伍邀请", icon="message")
        for request in requests:
            builder.item(request.id, _character_name(request.sender_id), " 邀请你加入队伍")
            actions.extend(
                (
                    Action(f"party.accept.{request.id}", "接受", f"接受组队 {request.id}", behavior="send"),
                    Action(f"party.reject.{request.id}", "拒绝", f"拒绝组队 {request.id}", behavior="send", style="secondary"),
                )
            )
    return builder.actions(actions).build()


def _party_battle_message(party: Party, challenge, character_id: str) -> DocumentMessage:
    builder = M.document().section("组队挑战", icon="combat")
    if challenge is None:
        builder.line("当前没有锁定的组队首领")
        if party.leader_id == character_id:
            builder.line("队长可发送：选择组队挑战 等级")
        return builder.build()
    view = current_game_services().world_views.require(challenge.source_world_id)
    enemy = view.enemy_projector.enemy(challenge.encounter.enemies[0])
    builder.field("来源世界", view.skin.name)
    builder.row(("首领", enemy.name), ("等级", str(challenge.level)))
    builder.line("状态", FieldSeparator(), "待挑战" if challenge.status == "selected" else "已完成")
    builder.line("挑战次数", FieldSeparator(), str(challenge.attempt_count))
    for member in sorted(party.members.values(), key=lambda value: value.slot):
        ready = "已准备" if member.subject_id in challenge.ready_fingerprints else "未准备"
        name = _character_name(member.subject_id)
        builder.line(f"{member.slot + 1}. {name}", FieldSeparator(), ready)
    if challenge.status == "selected":
        actions = [
            Action("party-battle.ready", "准备", "准备", behavior="send"),
            Action("party-battle.unready", "取消准备", "取消准备", behavior="send", style="secondary"),
        ]
        if party.leader_id == character_id:
            actions.append(Action("party-battle.start", "发起挑战", "开始组队挑战", behavior="send"))
        return builder.actions(actions).build()
    if challenge.report_id:
        report = current_game_services().battle_reports.reference(challenge.report_id)
        if report is not None:
            builder.field(
                "战报",
                M.link("查看完整战报", public_url("battle", report.share_id)),
            )
    return builder.build()


def _resolve_target(external_id: str):
    context = current_message_context()
    if context is None:
        raise RuntimeError("队伍命令缺少消息上下文")
    claim = context.identity.primary
    identity = ExternalIdentity(
        claim.provider_id,
        claim.tenant_id,
        claim.subject_kind,
        claim.scope_id,
        external_id,
    )
    services = current_game_services()
    account = services.accounts.find_existing_account(identity)
    return services.characters.load_for_account(account.id) if account is not None else None


def _character_name(character_id: str) -> str:
    character = current_game_services().characters.load_character(character_id)
    return character.name if character is not None else character_id


def _source_world_name(world_id: str) -> str:
    """把临时挑战的来源世界投影为玩家可读名称。"""

    return current_game_services().world_views.require(world_id).skin.name


def _selection_text(challenge) -> str:
    if challenge is None:
        return "已锁定组队首领，所有成员发送“准备”后由队长发起挑战"
    return (
        f"已锁定组队首领，来源世界：{_source_world_name(challenge.source_world_id)}。"
        "所有成员发送“准备”后由队长发起挑战"
    )


def _character(current: CurrentCharacterResult):
    return current.character if current.status == "ok" else None


def _operation_id(prefix: str) -> str:
    context = current_message_context()
    if context is None:
        raise RuntimeError("队伍命令缺少消息上下文")
    return f"{prefix}:{context.identity.evidence_id}"


def _now() -> datetime:
    return datetime.now(ZoneInfo(config.project.timezone))


async def _failed(title: str, character_id: str, exc: Exception) -> None:
    logger.opt(colors=True, exception=exc).error(C.join(C.fail(title), C.kv("character", character_id)))
    await send_game_reply(_failure("当前操作没有完成，请稍后重试"))


def _success(title: str, text: str) -> DocumentMessage:
    return M.document().section(title, icon="player").line(text).build()


def _failure(text: str) -> DocumentMessage:
    return M.document().section("组队", icon="notice").line(text).build()


__all__ = [
    "accept",
    "confirm_disband",
    "create",
    "invite",
    "kick",
    "leave",
    "preview_disband",
    "reject",
    "party_battle_view",
    "select_party_battle",
    "set_ready",
    "start_party_battle",
    "transfer",
    "view",
]
