"""伙伴命令解析、确认和协议中立展示。"""

from __future__ import annotations

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from game.app import CharacterOverview, CharacterOverviewResult, current_game_services
from game.content import LOADOUT_PRESET_IDS
from game.rules.companion import CompanionSanctuaryStatus
from launch import C, config, logger
from launch.adapter import current_message_context
from launch.paths import public_url
from message import Action, DocumentMessage, M
from message.schema import FieldSeparator

from ..reply import send_game_reply


_APTITUDE_NAMES = {
    "companion.aptitude.vitality": "体魄",
    "companion.aptitude.offense": "威势",
    "companion.aptitude.agility": "灵动",
    "companion.aptitude.focus": "灵性",
}
_ROLE_NAMES = {
    "assault": "强攻",
    "swift": "迅捷",
    "guardian": "守护",
    "control": "控制",
    "sustain": "续航",
}


async def view_companions(message: str, result: CharacterOverviewResult) -> None:
    overview = _overview(result)
    if overview is None:
        await send_game_reply(_unavailable())
        return
    try:
        view = await asyncio.to_thread(
            current_game_services().companions.view,
            overview.character.id,
            logical_time=_now(),
        )
        reference = str(message or "").strip()
        reply = (
            _companion_detail(view.roster, reference, overview)
            if reference
            else _companion_list(view.roster, overview)
        )
    except (KeyError, TypeError, ValueError) as exc:
        reply = _failure(str(exc))
    except Exception as exc:
        logger.opt(colors=True, exception=exc).error(
            C.join(C.fail("伙伴名册读取失败"), C.kv("character", overview.character.id))
        )
        reply = _failure("当前没有读取到伙伴名册")
    await send_game_reply(reply)


async def bind_companion(message: str, result: CharacterOverviewResult) -> None:
    overview = _overview(result)
    reference = str(message or "").strip().upper()
    if overview is None:
        await send_game_reply(_unavailable())
        return
    if not reference:
        await send_game_reply(_failure("发送：伙伴出战 C1"))
        return
    operation_id = _operation_id("companion-bind")
    try:
        outcome = await asyncio.to_thread(
            current_game_services().companions.bind,
            operation_id,
            overview.character.id,
            reference,
            allow_transfer=False,
            logical_time=_now(),
        )
        if outcome.status == "transfer_required" and outcome.roster is not None:
            await send_game_reply(_transfer_confirmation(outcome, overview))
            return
        await send_game_reply(_bind_result(outcome, overview))
    except Exception as exc:
        await _logged_failure("伙伴出战失败", overview.character.id, exc)


async def confirm_bind_transfer(message: str, result: CharacterOverviewResult) -> None:
    overview = _overview(result)
    if overview is None:
        await send_game_reply(_unavailable())
        return
    parts = str(message or "").split()
    if len(parts) != 2:
        await send_game_reply(_failure("出战确认已经失效"))
        return
    try:
        revision = int(parts[1])
        outcome = await asyncio.to_thread(
            current_game_services().companions.bind,
            _operation_id("companion-bind-transfer"),
            overview.character.id,
            parts[0],
            allow_transfer=True,
            expected_revision=revision,
            logical_time=_now(),
        )
        await send_game_reply(_bind_result(outcome, overview))
    except (TypeError, ValueError):
        await send_game_reply(_failure("出战确认已经失效"))
    except Exception as exc:
        await _logged_failure("伙伴转移失败", overview.character.id, exc)


async def unbind_companion(result: CharacterOverviewResult) -> None:
    overview = _overview(result)
    if overview is None:
        await send_game_reply(_unavailable())
        return
    try:
        outcome = await asyncio.to_thread(
            current_game_services().companions.unbind_current,
            _operation_id("companion-unbind"),
            overview.character.id,
            logical_time=_now(),
        )
        if outcome.status == "unbound":
            name = _species_name(outcome.companion) if outcome.companion else "伙伴"
            reply = M.document().section("伙伴休战", icon="player").line(f"{name} 已离开当前配装").build()
        elif outcome.status == "already_unbound":
            reply = _failure("当前配装没有出战伙伴")
        else:
            reply = _failure(outcome.failure_message or "伙伴休战没有完成")
        await send_game_reply(reply)
    except Exception as exc:
        await _logged_failure("伙伴休战失败", overview.character.id, exc)


async def view_sanctuary(result: CharacterOverviewResult) -> None:
    overview = _overview(result)
    if overview is None:
        await send_game_reply(_unavailable())
        return
    try:
        view = await asyncio.to_thread(
            current_game_services().companions.view,
            overview.character.id,
            logical_time=_now(),
        )
        await send_game_reply(_sanctuary_message(view.sanctuary, overview))
    except Exception as exc:
        await _logged_failure("伙伴秘境读取失败", overview.character.id, exc)


async def hunt_companion(message: str, result: CharacterOverviewResult) -> None:
    overview = _overview(result)
    if overview is None:
        await send_game_reply(_unavailable())
        return
    try:
        trace_index = int(str(message or "").strip())
        outcome = await asyncio.to_thread(
            current_game_services().companions.hunt,
            _operation_id("companion-hunt"),
            overview.character.id,
            trace_index,
            logical_time=_now(),
        )
        await send_game_reply(_hunt_result(outcome, overview))
    except ValueError:
        await send_game_reply(_failure("发送：秘境追踪 1"))
    except Exception as exc:
        await _logged_failure("伙伴追踪失败", overview.character.id, exc)


async def preview_release(message: str, result: CharacterOverviewResult) -> None:
    overview = _overview(result)
    reference = str(message or "").strip().upper()
    if overview is None:
        await send_game_reply(_unavailable())
        return
    try:
        view = await asyncio.to_thread(
            current_game_services().companions.view,
            overview.character.id,
            logical_time=_now(),
        )
        companion = view.roster.by_reference(reference)
        if companion is None:
            raise ValueError("找不到要放生的伙伴")
        action_name = _projector(overview).name("term.companion_release")
        reply = (
            M.document()
            .section(f"确认{action_name}", icon="notice")
            .line(f"{companion.reference} {_species_name(companion)} 将永久离开名册。")
            .note("不会返还万灵引或获得任何收益，已捕获图鉴会保留。")
            .actions((
                Action(
                    "companion.release.confirm",
                    f"确认{action_name}",
                    f"companion_release_confirm {companion.reference} {view.roster.revision}",
                    behavior="send",
                    style="secondary",
                ),
            ))
            .build()
        )
    except (KeyError, ValueError) as exc:
        reply = _failure(str(exc))
    except Exception as exc:
        await _logged_failure("伙伴放生预览失败", overview.character.id, exc)
        return
    await send_game_reply(reply)


async def confirm_release(message: str, result: CharacterOverviewResult) -> None:
    overview = _overview(result)
    if overview is None:
        await send_game_reply(_unavailable())
        return
    parts = str(message or "").split()
    if len(parts) != 2:
        await send_game_reply(_failure("放生确认已经失效"))
        return
    try:
        outcome = await asyncio.to_thread(
            current_game_services().companions.release,
            _operation_id("companion-release"),
            overview.character.id,
            parts[0],
            int(parts[1]),
            logical_time=_now(),
        )
        action_name = _projector(overview).name("term.companion_release")
        reply = (
            M.document()
            .section(action_name, icon="player")
            .line(f"{_species_name(outcome.companion)} 已离开名册")
            .build()
            if outcome.status == "released" and outcome.companion is not None
            else _failure(outcome.failure_message or "放生没有完成")
        )
        await send_game_reply(reply)
    except (TypeError, ValueError):
        await send_game_reply(_failure("放生确认已经失效"))
    except Exception as exc:
        await _logged_failure("伙伴放生失败", overview.character.id, exc)


async def preview_abandon(result: CharacterOverviewResult) -> None:
    overview = _overview(result)
    if overview is None:
        await send_game_reply(_unavailable())
        return
    try:
        view = await asyncio.to_thread(
            current_game_services().companions.view,
            overview.character.id,
            logical_time=_now(),
        )
        sanctuary = view.sanctuary
        if sanctuary is None or not sanctuary.active:
            raise ValueError("当前没有可以放弃的伙伴秘境")
        reply = (
            M.document()
            .section("确认放弃秘境", icon="notice")
            .line("当前踪迹和已锁定目标都会永久消失。")
            .note("开启秘境消耗的万灵引不会返还。")
            .actions((
                Action(
                    "companion.abandon.confirm",
                    "确认放弃",
                    f"companion_abandon_confirm {sanctuary.revision}",
                    behavior="send",
                    style="secondary",
                ),
            ))
            .build()
        )
    except ValueError as exc:
        reply = _failure(str(exc))
    except Exception as exc:
        await _logged_failure("伙伴秘境放弃预览失败", overview.character.id, exc)
        return
    await send_game_reply(reply)


async def confirm_abandon(message: str, result: CharacterOverviewResult) -> None:
    overview = _overview(result)
    if overview is None:
        await send_game_reply(_unavailable())
        return
    try:
        outcome = await asyncio.to_thread(
            current_game_services().companions.abandon,
            _operation_id("companion-abandon"),
            overview.character.id,
            int(str(message or "").strip()),
            logical_time=_now(),
        )
        reply = (
            M.document().section("伙伴秘境", icon="explore").line("秘境已经关闭").build()
            if outcome.status == "abandoned"
            else _failure(outcome.failure_message or "放弃秘境没有完成")
        )
        await send_game_reply(reply)
    except (TypeError, ValueError):
        await send_game_reply(_failure("放弃确认已经失效"))
    except Exception as exc:
        await _logged_failure("伙伴秘境放弃失败", overview.character.id, exc)


def _companion_list(roster, overview: CharacterOverview) -> DocumentMessage:
    term = _projector(overview).name("term.companion")
    builder = M.document().section(f"{term}名册", icon="player").field(
        "数量", f"{len(roster.instances)}/{current_game_services().content.companions.balance.roster_capacity}"
    )
    if not roster.instances:
        builder.line("当前还没有伙伴")
    for companion in sorted(roster.instances.values(), key=lambda value: int(value.reference[1:])):
        preset = roster.preset_for_companion(companion.id)
        status = f"配装 {_preset_index(preset)}" if preset is not None else "休战"
        builder.line(
            M.command(companion.reference, f"伙伴 {companion.reference}"),
            " ",
            _species_name(companion),
            FieldSeparator(),
            _projector(overview).name(companion.quality_id),
            FieldSeparator(),
            status,
        )
    builder.actions((Action("companion.sanctuary", "秘境", "伙伴秘境", behavior="send"),))
    return builder.build()


def _companion_detail(roster, reference: str, overview: CharacterOverview) -> DocumentMessage:
    companion = roster.by_reference(reference)
    if companion is None:
        raise ValueError("找不到这名伙伴")
    species = current_game_services().content.companions.species.require(companion.definition_id)
    origin = current_game_services().world_views.require(companion.origin_skin_id).skin.name
    preset = roster.preset_for_companion(companion.id)
    builder = (
        M.document()
        .section(f"{companion.reference} {species.name}", icon="player")
        .row(("品阶", _projector(overview).name(companion.quality_id)), ("等级", f"Lv{companion.level}"))
        .row(("来源", origin), ("定位", _ROLE_NAMES[species.role]))
        .field("状态", f"配装 {_preset_index(preset)}" if preset is not None else "休战")
        .line(species.description)
        .section("资质", icon="status")
    )
    builder.row(*((_APTITUDE_NAMES[str(key)], value) for key, value in companion.aptitudes.items()))
    builder.section("战斗特性", icon="combat").line(
        _projector(overview).name(species.core_behavior_id),
        FieldSeparator(),
        _projector(overview).name(companion.trait_behavior_id),
    )
    actions = []
    if preset == overview.loadout.active_preset_id:
        actions.append(Action("companion.unbind", "休战", "伙伴休战", behavior="send"))
    else:
        actions.append(Action("companion.bind", _projector(overview).name("term.companion_bind"), f"伙伴出战 {companion.reference}", behavior="send"))
    actions.append(Action("companion.release", _projector(overview).name("term.companion_release"), f"放生 {companion.reference}", behavior="send", style="secondary"))
    return builder.actions(actions).build()


def _sanctuary_message(sanctuary, overview: CharacterOverview) -> DocumentMessage:
    title = _projector(overview).name("term.companion_sanctuary")
    if sanctuary is None:
        return (
            M.document()
            .section(title, icon="explore")
            .line("当前没有已开启的伙伴秘境")
            .note("使用万灵引可在当前世界开启一次秘境。")
            .build()
        )
    status_names = {
        CompanionSanctuaryStatus.OPEN: "等待选择",
        CompanionSanctuaryStatus.TRACKING: "追踪中",
        CompanionSanctuaryStatus.CAPTURED: "已捕获",
        CompanionSanctuaryStatus.ABANDONED: "已放弃",
        CompanionSanctuaryStatus.EXPIRED: "已过期",
    }
    builder = M.document().section(title, icon="explore").row(
        ("状态", status_names[sanctuary.status]),
        ("有效期", sanctuary.expires_at.strftime("%m-%d %H:%M")),
    )
    actions = []
    if sanctuary.active:
        traces = sanctuary.traces
        if sanctuary.selected_trace_index is not None:
            traces = tuple(value for value in traces if value.index == sanctuary.selected_trace_index)
        for trace in traces:
            species = current_game_services().content.companions.species.require(trace.definition_id)
            builder.item(
                trace.index,
                species.name,
                FieldSeparator(),
                _ROLE_NAMES[species.role],
                FieldSeparator(),
                "危险相当",
            )
            actions.append(Action(f"companion.trace.{trace.index}", f"追踪 {trace.index}", f"秘境追踪 {trace.index}", behavior="send"))
        actions.append(Action("companion.abandon", "放弃", "放弃秘境", behavior="send", style="secondary"))
    return builder.actions(actions).build()


def _hunt_result(outcome, overview: CharacterOverview) -> DocumentMessage:
    if outcome.status == "captured" and outcome.companion is not None:
        companion = outcome.companion
        builder = (
            M.document()
            .section("捕获成功", icon="reward")
            .field("伙伴", f"{companion.reference} {_species_name(companion)}")
            .row(("品阶", _projector(overview).name(companion.quality_id)), ("等级", f"Lv{companion.level}"))
        )
        if outcome.battle_report is not None:
            builder.field("战报", M.link("查看完整战报", public_url("battle", outcome.battle_report.share_id)))
        return builder.actions((Action("companion.bind", _projector(overview).name("term.companion_bind"), f"伙伴出战 {companion.reference}", behavior="send"),)).build()
    if outcome.status == "defeated":
        builder = M.document().section("追踪失败", icon="combat").line("目标仍停留在原踪迹，恢复后可以再次挑战。")
        if outcome.battle_report is not None:
            builder.field("战报", M.link("查看完整战报", public_url("battle", outcome.battle_report.share_id)))
        return builder.build()
    return _failure(outcome.failure_message or "伙伴追踪没有完成")


def _transfer_confirmation(outcome, overview: CharacterOverview) -> DocumentMessage:
    companion = outcome.companion
    assert companion is not None and outcome.roster is not None
    previous = _preset_index(outcome.previous_preset_id)
    current = _preset_index(overview.loadout.active_preset_id)
    return (
        M.document()
        .section("确认转移伙伴", icon="notice")
        .line(f"{_species_name(companion)} 当前属于配装 {previous}，将转移到配装 {current}。")
        .actions((Action("companion.bind.transfer", "确认转移", f"companion_bind_transfer_confirm {companion.reference} {outcome.roster.revision}", behavior="send"),))
        .build()
    )


def _bind_result(outcome, overview: CharacterOverview) -> DocumentMessage:
    if outcome.status in {"bound", "transferred", "already_bound"} and outcome.companion is not None:
        action = _projector(overview).name("term.companion_bind")
        text = "已经随当前配装出战" if outcome.status != "already_bound" else "本就属于当前配装"
        return M.document().section(f"伙伴{action}", icon="player").line(f"{_species_name(outcome.companion)} {text}").build()
    return _failure(outcome.failure_message or "伙伴出战没有完成")


def _species_name(companion) -> str:
    return current_game_services().content.companions.species.require(companion.definition_id).name


def _projector(overview: CharacterOverview):
    return current_game_services().world_view(overview.dimension).projector


def _preset_index(preset_id) -> int | None:
    if preset_id is None:
        return None
    try:
        return LOADOUT_PRESET_IDS.index(preset_id)
    except ValueError:
        return None


def _overview(result: CharacterOverviewResult) -> CharacterOverview | None:
    return result.overview if result.status == "ok" else None


def _operation_id(prefix: str) -> str:
    context = current_message_context()
    if context is None:
        raise RuntimeError("伙伴命令缺少消息上下文")
    return f"{prefix}:{context.identity.evidence_id}"


async def _logged_failure(title: str, character_id: str, exc: Exception) -> None:
    logger.opt(colors=True, exception=exc).error(
        C.join(C.fail(title), C.kv("character", character_id))
    )
    await send_game_reply(_failure("当前操作没有完成，请稍后重试"))


def _failure(message: str) -> DocumentMessage:
    return M.document().section("伙伴", icon="notice").line(message).build()


def _unavailable() -> DocumentMessage:
    return _failure("当前没有读取到角色状态，请稍后重试")


def _now() -> datetime:
    return datetime.now(ZoneInfo(config.project.timezone))


__all__ = [
    "bind_companion",
    "confirm_abandon",
    "confirm_bind_transfer",
    "confirm_release",
    "hunt_companion",
    "preview_abandon",
    "preview_release",
    "unbind_companion",
    "view_companions",
    "view_sanctuary",
]
