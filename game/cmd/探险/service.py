"""探险命令的参数解析、应用服务调用与富文本展示。"""

from __future__ import annotations

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from game.app import CurrentCharacterResult, current_game_services
from game.content.catalog import PRIMARY_CURRENCY_ID
from game.features.exploration import (
    ExplorationMovementResult,
    ExplorationOperationResult,
    exploration_battle_report_id,
)
from game.core.gameplay import equipment_state_from_instance, weapon_state_from_instance
from game.rules.exploration import (
    ExplorationEncounterKind,
    ExplorationRewardKind,
    ExplorationStatus,
    ExplorationStopReason,
)
from launch import C, config, logger
from launch.paths import public_url
from message import Action, DocumentMessage, M

from ..reply import send_game_reply


async def view_exploration(current: CurrentCharacterResult) -> None:
    character = _character(current)
    if character is None:
        await send_game_reply(_unavailable())
        return
    try:
        services = current_game_services()
        state, overview = await asyncio.gather(
            asyncio.to_thread(
                services.exploration.load,
                character.id,
                logical_time=_now(),
            ),
            asyncio.to_thread(services.load_character_overview, character),
        )
        view = services.world_view(current.dimension)
        await send_game_reply(_exploration_message(state, overview.overview, view))
    except Exception as exc:
        await _failed("探险状态查询失败", character.id, exc)


async def move(message: str, current: CurrentCharacterResult) -> None:
    character = _character(current)
    if character is None:
        await send_game_reply(_unavailable())
        return
    services = current_game_services()
    view = services.world_view(current.dimension)
    requested = str(message or "").strip()
    if not requested:
        await view_exploration(current)
        return
    location_id = _resolve_location(requested, view)
    if location_id is None:
        await send_game_reply(
            M.document()
            .section("前往", icon="world")
            .line("没有找到这个地点")
            .note("发送: 探险 查看地点")
            .build()
        )
        return
    try:
        result = await asyncio.to_thread(
            services.exploration.move,
            character.id,
            location_id,
            logical_time=_now(),
        )
        await send_game_reply(_movement_message(result, view))
    except Exception as exc:
        await _failed("探险移动失败", character.id, exc)


async def start(current: CurrentCharacterResult) -> None:
    await _operate(current, "start", _start_message, "开始探险失败")


async def stop(current: CurrentCharacterResult) -> None:
    await _operate(current, "stop", _stop_message, "停止探险失败")


async def summary(current: CurrentCharacterResult) -> None:
    character = _character(current)
    if character is None:
        await send_game_reply(_unavailable())
        return
    try:
        services = current_game_services()
        result, overview_result = await asyncio.gather(
            asyncio.to_thread(
                services.exploration.load,
                character.id,
                logical_time=_now(),
            ),
            asyncio.to_thread(services.load_character_overview, character),
        )
        if overview_result.status != "ok" or overview_result.overview is None:
            await send_game_reply(_unavailable())
            return
        view = services.world_view(overview_result.overview.dimension)
        report = (
            services.battle_reports.reference(
                exploration_battle_report_id(result.state.session_id)
            )
            if result.state is not None
            else None
        )
        await send_game_reply(
            _summary_message(result, overview_result.overview, view, report)
        )
    except Exception as exc:
        await _failed("探险总结查询失败", character.id, exc)


async def _operate(current, method_name, presenter, log_message) -> None:
    character = _character(current)
    if character is None:
        await send_game_reply(_unavailable())
        return
    try:
        method = getattr(current_game_services().exploration, method_name)
        result = await asyncio.to_thread(
            method,
            character.id,
            logical_time=_now(),
        )
        view = current_game_services().world_view(current.dimension)
        await send_game_reply(presenter(result, view))
    except Exception as exc:
        await _failed(log_message, character.id, exc)


def _exploration_message(result, overview, view) -> DocumentMessage:
    services = current_game_services()
    projector = view.projector
    location_id = None
    if overview is not None:
        presence = next(
            (
                value
                for value in overview.world.presences.values()
                if value.owner_id == overview.character.id
            ),
            None,
        )
        location_id = presence.position.location_id if presence else None
    builder = M.document().section("探险", icon="world")
    builder.row(
        ("位置", projector.name(location_id) if location_id else "未知"),
        ("状态", _status_text(result)),
    )
    if result.state is not None and result.state.status is ExplorationStatus.RUNNING:
        builder.field("下次结算", _time(result.state.next_batch_at))
    builder.section("常规区域", icon="combat")
    regular = [
        value
        for value in services.content.exploration_regions.definitions()
        if value.kind.value == "regular"
    ]
    for index, region in enumerate(regular, start=1):
        builder.item(
            index,
            f"{projector.name(region.location_id)} | {_levels(region.minimum_enemy_level, region.maximum_enemy_level)}",
        )
    builder.section("特殊区域", icon="notice")
    special = [
        value
        for value in services.content.exploration_regions.definitions()
        if value.kind.value != "regular"
    ]
    for index, region in enumerate(special, start=1):
        builder.item(
            index,
            f"{projector.name(region.location_id)} | {_focus(region.kind.value)} | {_levels(region.minimum_enemy_level, region.maximum_enemy_level)}",
        )
    actions = []
    if result.state is not None and result.state.status is ExplorationStatus.RUNNING:
        actions.append(Action("exploration.stop", "停止", "停止探险", behavior="send"))
    elif location_id is not None:
        try:
            services.content.exploration_regions.for_location(location_id)
        except KeyError:
            pass
        else:
            actions.append(Action("exploration.start", "开始", "开始探险", behavior="send"))
    actions.append(Action("exploration.move", "前往", "前往 ", behavior="fill", style="secondary"))
    return builder.actions(tuple(actions)).build()


def _movement_message(result: ExplorationMovementResult, view) -> DocumentMessage:
    projector = view.projector
    builder = M.document().section("前往", icon="world")
    if result.status == "moved":
        return builder.field("抵达", projector.name(result.location_id)).build()
    if result.status == "already_there":
        return builder.field("位置", projector.name(result.location_id)).line("已经在这里").build()
    if result.status == "exploring":
        return builder.line("探险进行中，停止后才能移动").build()
    return builder.line("本次移动没有完成").build()


def _start_message(result: ExplorationOperationResult, view) -> DocumentMessage:
    builder = M.document().section("开始探险", icon="combat")
    if result.status == "started" and result.state is not None:
        return (
            builder.field("区域", _name(result.state.location_id, view))
            .field("首次结算", _time(result.state.next_batch_at))
            .line("之后每 10 分钟自动结算，直到停止、战败或容量已满。")
            .actions((Action("exploration.stop", "停止", "停止探险", behavior="send"),))
            .build()
        )
    if result.status == "already_running":
        return builder.line("当前已经在探险").build()
    if result.status == "health_depleted":
        return builder.line("血气已经归零，恢复后才能开始探险").build()
    if result.status == "main_action_occupied":
        return builder.line("当前正在进行其他主要行动").build()
    if result.status == "not_in_region":
        return builder.line("当前位置不是探险区域").note("发送: 探险 查看区域").build()
    return builder.line("本次探险没有开始").build()


def _stop_message(result: ExplorationOperationResult, view) -> DocumentMessage:
    builder = M.document().section("停止探险", icon="combat")
    if result.status == "stopped" and result.state is not None:
        return (
            builder.field("已结算", f"{result.state.completed_batches} 批")
            .line("已经停止")
            .build()
        )
    if result.status == "already_stopped":
        return builder.line("当前探险已经停止").build()
    if result.status == "not_started":
        return builder.line("当前没有探险记录").build()
    return builder.line("本次停止没有完成").build()


def _summary_message(
    result: ExplorationOperationResult,
    overview,
    view,
    battle_report=None,
) -> DocumentMessage:
    if result.state is None:
        return (
            M.document()
            .section("探险总结", icon="combat")
            .line("还没有探险记录")
            .build()
        )
    state = result.state
    builder = (
        M.document()
        .section("探险总结", icon="combat")
        .row(("区域", _name(state.location_id, view)), ("状态", _status_text(result)))
        .row(("批次", state.completed_batches), ("胜负", f"{state.victories}胜 {state.defeats}负"))
        .row(("经验", f"+{state.character_experience}"), ("武器经验", f"+{state.weapon_experience}"))
        .row(("武器", state.weapon_drops), ("装备", state.equipment_drops))
        .row(("战利品", state.trophy_drops), ("药物", state.medicine_drops))
        .field("抽奖签", state.draw_ticket_drops)
        .field("战利品估价", f"{state.trophy_value} {_name(PRIMARY_CURRENCY_ID, view)}")
    )
    if battle_report is not None:
        builder.field(
            "战报",
            M.link(
                "查看完整战报",
                public_url("battle", battle_report.share_id),
            ),
        )
    last = state.last_result
    if last is not None:
        builder.section("最近一批", icon="inventory")
        if last.plan.encounter_kind is ExplorationEncounterKind.EMPTY:
            builder.line("没有遭遇")
        else:
            enemies = (
                tuple(last.plan.encounter.enemies)
                if last.plan.encounter is not None
                else ()
            )
            builder.field(
                "遭遇",
                ", ".join(view.enemy_projector.enemy(enemy).name for enemy in enemies)
                or "未知敌人",
            )
            builder.field("结果", "胜利" if last.victory else "平局" if last.draw else "战败")
            if last.rewards:
                builder.field(
                    "获得",
                    ", ".join(
                        _reward_name(reference, overview, view)
                        for reference in last.rewards
                    ),
                )
            if last.medicines_used:
                builder.field(
                    "自动用药",
                    ", ".join(
                        _reward_name(reference, overview, view)
                        for reference in last.medicines_used
                    ),
                )
    return builder.actions(
        (Action("exploration.recycle_trophies", "回收", "回收战利品", behavior="send"),)
    ).build()


def _status_text(result: ExplorationOperationResult) -> str:
    state = result.state
    if state is None:
        return "未开始"
    if state.status is ExplorationStatus.RUNNING:
        return "进行中"
    return {
        ExplorationStopReason.MANUAL: "已停止",
        ExplorationStopReason.DEFEATED: "战败停止",
        ExplorationStopReason.CAPACITY_FULL: "容量已满",
        ExplorationStopReason.INVALID_LOCATION: "位置失效",
    }.get(state.stop_reason, "已停止")


def _resolve_location(value: str, view) -> str | None:
    services = current_game_services()
    locations = services.content.catalog.world.locations
    if value in locations:
        return value
    normalized = value.casefold()
    for definition_id in locations.ids():
        if view.projector.name(definition_id).casefold() == normalized:
            return definition_id
    return None


def _focus(kind: str) -> str:
    return {
        "weapon_focus": "武器偏向",
        "equipment_focus": "装备偏向",
        "boss_focus": "强敌偏向",
    }[kind]


def _levels(low: int, high: int) -> str:
    return f"Lv{low}" if low == high else f"Lv{low}-{high}"


def _name(definition_id: str, view) -> str:
    return view.projector.name(definition_id)


def _reward_name(reference, overview, view) -> str:
    if reference.kind is ExplorationRewardKind.ITEM:
        return f"{view.projector.name(reference.definition_id)} x{reference.quantity}"
    instance = overview.inventory.instances.get(reference.asset_id)
    if instance is None:
        return view.projector.name(reference.definition_id)
    if reference.kind is ExplorationRewardKind.WEAPON:
        return view.gear_projector.weapon(
            weapon_state_from_instance(instance),
            instance,
            inscription_preference=overview.inscription_preference,
        ).name
    return view.gear_projector.equipment(
        equipment_state_from_instance(instance),
        instance,
        inscription_preference=overview.inscription_preference,
    ).name


def _time(value: datetime) -> str:
    return value.astimezone(ZoneInfo(config.project.timezone)).strftime("%m-%d %H:%M")


def _character(current: CurrentCharacterResult):
    return current.character if current.status == "ok" else None


def _now() -> datetime:
    return datetime.now(ZoneInfo(config.project.timezone))


async def _failed(message: str, character_id: str, exc: Exception) -> None:
    logger.opt(colors=True, exception=exc).error(
        C.join(C.fail(message), C.kv("character", character_id))
    )
    await send_game_reply(
        M.document().section("探险", icon="world").line("当前操作没有完成，请稍后重试").build()
    )


def _unavailable() -> DocumentMessage:
    return M.document().section("探险", icon="world").line("当前没有可用角色").build()


__all__ = [
    "move",
    "start",
    "stop",
    "summary",
    "view_exploration",
]
