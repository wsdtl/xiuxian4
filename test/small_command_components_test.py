"""自动用药、铭刻入口、原名偏好和装配命令的本地驱动测试。"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game.app import build_game_services, install_game_services, restore_game_services  # noqa: E402
from game.content import (  # noqa: E402
    CHARACTER_LEVEL_PROGRESSION_ID,
    CULTIVATION_SKIN_ID,
    INSCRIPTION_FEATHER_ITEM_ID,
    MAGIC_SKIN_ID,
    PRIMARY_CURRENCY_ID,
)
from game.content.catalog.character import REST_ACTION_ID  # noqa: E402
from game.core.gameplay import (  # noqa: E402
    INSCRIPTION_MEDIUM_DATA_KEY,
    GrantInstance,
    HEALTH_CURRENT,
    HEALTH_MAXIMUM,
    SPIRIT_CURRENT,
    SPIRIT_MAXIMUM,
    CharacterState,
    InscriptionMediumData,
    InventoryEngine,
    InventoryState,
    InventoryTransaction,
    SourceReceipt,
    WEAPON_SLOT_ID,
    equipment_state_data,
)
from game.core.persistence import CHARACTER_AGGREGATE, INVENTORY_AGGREGATE  # noqa: E402
from game.rules import (  # noqa: E402
    EquipmentGenerationRequest,
    EquipmentInstanceGenerator,
    game_operation_context,
)
from game.cmd import 角色 as character_component  # noqa: E402,F401
from game.cmd import 次元 as dimension_component  # noqa: E402,F401
from game.cmd import 休息 as rest_component  # noqa: E402,F401
from game.cmd import 提醒 as reminder_component  # noqa: E402,F401
from game.cmd import 铭刻 as inscription_component  # noqa: E402,F401
from game.cmd import 装配 as loadout_component  # noqa: E402,F401
from game.cmd import 物品 as item_component  # noqa: E402,F401
from launch.adapter.local import LocalEventHandler, dispatch  # noqa: E402
from launch.adapter.qq import QqEventHandler  # noqa: E402


def main() -> None:
    asyncio.run(_main())
    print("small command component tests passed")


async def _main() -> None:
    for command in (
        "自动用药",
        "铭刻",
        "铭刻能力",
        "铭刻原名",
        "inscription_confirm_asset",
        "inscription_confirm_ability",
        "装配",
        "装备",
        "卸下",
        "配装",
        "纳戒",
        "跃迁",
    ):
        assert len(LocalEventHandler.exact_rules[command]) == 1
        assert len(QqEventHandler.exact_rules[command]) == 1

    with TemporaryDirectory() as directory:
        services = build_game_services(
            database_path=Path(directory) / "small-command.db",
            identity_secret="small-command-test-secret",
        )
        services.database.initialize()
        previous = install_game_services(services)
        try:
            await LocalEventHandler.run()
            await dispatch(
                client_id="small-command-player",
                raw_message="创建角色 试剑客",
                sender_name="试剑客",
                event_id="small-command-create",
            )

            with services.database.unit_of_work(write=False) as uow:
                row = uow.connection.execute(
                    "SELECT aggregate_id FROM aggregate_snapshot "
                    "WHERE aggregate_kind = ?",
                    (CHARACTER_AGGREGATE,),
                ).fetchone()
            character = services.characters.load_character(str(row[0]))
            assert character is not None
            initial_overview = services.load_character_overview(character).overview
            assert initial_overview is not None
            initial_inventory = initial_overview.inventory
            initial_world = initial_overview.world
            target_skin_id = (
                MAGIC_SKIN_ID
                if initial_overview.dimension.skin_id == CULTIVATION_SKIN_ID
                else CULTIVATION_SKIN_ID
            )
            target_view = services.world_views.require(target_skin_id)
            worlds = await dispatch(
                client_id="small-command-player",
                raw_message="跃迁",
                sender_name="试剑客",
                event_id="small-command-worlds",
            )
            assert "太玄界" in worlds.replies[0].message.content
            assert "魔法世界" in worlds.replies[0].message.content
            target_action = next(
                action
                for action in worlds.replies[0].message.actions
                if action.label == target_view.skin.name
            )
            assert target_action.data == f"跃迁 {target_skin_id}"
            old_armory = await dispatch(
                client_id="small-command-player",
                raw_message="武库",
                sender_name="试剑客",
                event_id="small-command-old-armory",
            )
            old_weapon_button = old_armory.replies[0].message.actions[0]
            assert old_weapon_button.data == f"武库 {WEAPON_SLOT_ID}"
            shifted_world = await dispatch(
                client_id="small-command-player",
                raw_message=target_action.data,
                sender_name="试剑客",
                event_id="small-command-shift-world",
            )
            assert "次元跃迁" in shifted_world.replies[0].message.content
            assert target_view.skin.name in shifted_world.replies[0].message.content
            shifted_overview = services.load_character_overview(character).overview
            assert shifted_overview is not None
            assert shifted_overview.inventory == initial_inventory
            assert shifted_overview.world == initial_world
            assert shifted_overview.dimension.skin_id == target_skin_id
            old_button_after_shift = await dispatch(
                client_id="small-command-player",
                raw_message=old_weapon_button.data,
                sender_name="试剑客",
                event_id="small-command-old-button-after-shift",
            )
            assert (
                f"武库·{target_view.projector.name(WEAPON_SLOT_ID)}"
                in old_button_after_shift.replies[0].message.content
            )

            _injure_character(services, character.id)
            await dispatch(
                client_id="small-command-player",
                raw_message="rest_start",
                sender_name="试剑客",
                event_id="small-command-rest-start",
            )
            original_view = services.world_views.require(initial_overview.dimension.skin_id)
            blocked_shift = await dispatch(
                client_id="small-command-player",
                raw_message=f"跃迁 {original_view.skin.name}",
                sender_name="试剑客",
                event_id="small-command-shift-blocked",
            )
            assert "当前正在进行主要行动" in blocked_shift.replies[0].message.content, (
                blocked_shift.replies[0].message.content
            )
            await dispatch(
                client_id="small-command-player",
                raw_message="停止休息",
                sender_name="试剑客",
                event_id="small-command-rest-stop",
            )
            region = services.content.exploration_regions.definitions()[0]
            moved = services.exploration.move(
                character.id,
                region.location_id,
                logical_time=datetime.now(ZoneInfo("Asia/Shanghai")),
            )
            assert moved.status in {"moved", "already_there"}
            started = services.exploration.start(
                character.id,
                logical_time=datetime.now(ZoneInfo("Asia/Shanghai")),
            )
            assert started.status == "started"
            exploration_blocked = services.shift_character_dimension(
                character.id,
                original_view.skin.id,
                logical_time=datetime.now(ZoneInfo("Asia/Shanghai")),
            )
            assert exploration_blocked.status == "main_action_occupied"
            services.exploration.stop(
                character.id,
                logical_time=datetime.now(ZoneInfo("Asia/Shanghai")),
            )

            auto_medicine = await dispatch(
                client_id="small-command-player",
                raw_message="自动用药",
                sender_name="试剑客",
                event_id="small-command-auto-status",
            )
            assert "当前状态: _开启_" in auto_medicine.replies[0].message.content

            disabled = await dispatch(
                client_id="small-command-player",
                raw_message="自动用药 关闭",
                sender_name="试剑客",
                event_id="small-command-auto-disable",
            )
            assert "当前状态: _关闭_" in disabled.replies[0].message.content

            inscription = await dispatch(
                client_id="small-command-player",
                raw_message="铭刻",
                sender_name="试剑客",
                event_id="small-command-inscription",
            )
            assert (
                f"暂无{target_view.projector.name(INSCRIPTION_FEATHER_ITEM_ID)}"
                in inscription.replies[0].message.content
            )

            original = await dispatch(
                client_id="small-command-player",
                raw_message="铭刻原名 关闭",
                sender_name="试剑客",
                event_id="small-command-original-disable",
            )
            assert "当前状态: _关闭_" in original.replies[0].message.content

            loadout = await dispatch(
                client_id="small-command-player",
                raw_message="装配",
                sender_name="试剑客",
                event_id="small-command-loadout",
            )
            assert "当前装配" in loadout.replies[0].message.content
            assert target_view.projector.name(WEAPON_SLOT_ID) in loadout.replies[0].message.content

            preset_list = await dispatch(
                client_id="small-command-player",
                raw_message="配装",
                sender_name="试剑客",
                event_id="small-command-presets",
            )
            assert "配装 0" in preset_list.replies[0].message.content
            assert "配装 5" in preset_list.replies[0].message.content

            switched = await dispatch(
                client_id="small-command-player",
                raw_message="配装 1",
                sender_name="试剑客",
                event_id="small-command-switch",
            )
            assert "当前配装: _1_" in switched.replies[0].message.content

            equipment_ref, feather_ref, slot_name = _grant_test_assets(
                services,
                character.id,
            )

            nacre_after_grant = await dispatch(
                client_id="small-command-player",
                raw_message="纳戒",
                sender_name="试剑客",
                event_id="small-command-nacre-after-grant",
            )
            assert "旧桥挑灯客遗羽" not in nacre_after_grant.replies[0].message.content
            inscription_after_grant = await dispatch(
                client_id="small-command-player",
                raw_message="铭刻",
                sender_name="试剑客",
                event_id="small-command-inscription-after-grant",
            )
            assert "旧桥挑灯客遗羽" in inscription_after_grant.replies[0].message.content

            equipped = await dispatch(
                client_id="small-command-player",
                raw_message=f"装备 E{equipment_ref}",
                sender_name="试剑客",
                event_id="small-command-equip",
            )
            assert f"E{equipment_ref}" in equipped.replies[0].message.content

            unequipped = await dispatch(
                client_id="small-command-player",
                raw_message=f"卸下 {slot_name}",
                sender_name="试剑客",
                event_id="small-command-unequip",
            )
            assert "当前装配" in unequipped.replies[0].message.content

            preview = await dispatch(
                client_id="small-command-player",
                raw_message=f"铭刻 I{feather_ref} E{equipment_ref} 照夜",
                sender_name="试剑客",
                event_id="small-command-inscription-preview",
            )
            assert "铭刻预览" in preview.replies[0].message.content
            confirm_command = preview.replies[0].message.actions[0].data
            completed = await dispatch(
                client_id="small-command-player",
                raw_message=confirm_command,
                sender_name="试剑客",
                event_id="small-command-inscription-confirm",
            )
            assert "铭刻完成" in completed.replies[0].message.content
            assert "照夜" in completed.replies[0].message.content

            overview = services.load_character_overview(character).overview
            assert overview is not None
            assert overview.inventory.asset_id_for_reference(equipment_ref) == "equipment-command-1"
            assert all(
                value.definition_id != INSCRIPTION_FEATHER_ITEM_ID
                for value in overview.inventory.instances.values()
            )

            magic_view = services.world_views.require(MAGIC_SKIN_ID)
            await dispatch(
                client_id="small-command-player",
                raw_message=f"跃迁 {MAGIC_SKIN_ID}",
                sender_name="试剑客",
                event_id="small-command-final-magic-shift",
            )
            magic_profile = await dispatch(
                client_id="small-command-player",
                raw_message="我的角色",
                sender_name="试剑客",
                event_id="small-command-magic-profile",
            )
            profile_text = magic_profile.replies[0].message.content
            for definition_id in (
                CHARACTER_LEVEL_PROGRESSION_ID,
                HEALTH_CURRENT,
                SPIRIT_CURRENT,
                PRIMARY_CURRENCY_ID,
            ):
                expected = magic_view.projector.name(definition_id).removeprefix("当前")
                assert expected in profile_text
            magic_combat = await dispatch(
                client_id="small-command-player",
                raw_message="战斗面板",
                sender_name="试剑客",
                event_id="small-command-magic-combat",
            )
            combat_text = magic_combat.replies[0].message.content
            for definition_id in (HEALTH_MAXIMUM, SPIRIT_MAXIMUM):
                assert magic_view.projector.name(definition_id) in combat_text
            magic_overview = services.load_character_overview(character).overview
            assert magic_overview is not None
            presence = next(
                value
                for value in magic_overview.world.presences.values()
                if value.owner_id == character.id
            )
            assert presence.position.location_id is not None
            assert (
                magic_view.projector.name(presence.position.location_id)
                in profile_text
            )
            magic_armory = await dispatch(
                client_id="small-command-player",
                raw_message="武库",
                sender_name="试剑客",
                event_id="small-command-magic-armory",
            )
            assert magic_view.projector.name(WEAPON_SLOT_ID) in magic_armory.replies[0].message.content
            magic_rest = await dispatch(
                client_id="small-command-player",
                raw_message="休息",
                sender_name="试剑客",
                event_id="small-command-magic-rest",
            )
            assert magic_view.projector.name(REST_ACTION_ID) in magic_rest.replies[0].message.content
        finally:
            restore_game_services(previous)


def _grant_test_assets(services, character_id: str) -> tuple[int, int, str]:
    logical_time = datetime.now(ZoneInfo("Asia/Shanghai"))
    snapshots = services.character_creation.snapshots
    equipment_definition = next(iter(services.content.catalog.equipment.definitions))
    generated = EquipmentInstanceGenerator(
        services.content.catalog.equipment,
        services.content.catalog.itemization_engine,
        set_mark_chance=0,
    ).generate(
        EquipmentGenerationRequest(
            "small-command-equipment-generation",
            "equipment-command-1",
            equipment_definition.id,
            services.content.catalog.report.content_fingerprint,
        ),
        context=game_operation_context(
            "small-command-equipment-generation",
            logical_time=logical_time,
        ),
    )
    receipt = SourceReceipt(
        "small-command-assets-receipt",
        "source.test_setup",
        character_id,
        logical_time,
    )
    with services.database.unit_of_work() as uow:
        inventory = snapshots.require(
            uow,
            INVENTORY_AGGREGATE,
            character_id,
            InventoryState,
        )
        inscription = next(
            value.id
            for value in inventory.containers.values()
            if value.kind == "container.inscription"
        )
        armory = next(
            value.id
            for value in inventory.containers.values()
            if value.kind == "container.armory"
        )
        outcome = InventoryEngine(services.content.catalog.items).execute(
            InventoryTransaction(
                "small-command-grant-assets",
                character_id,
                "inventory.test_setup",
                (
                    GrantInstance(
                        "equipment-command-1",
                        equipment_definition.item_definition_id,
                        armory,
                        receipt,
                        equipment_state_data(generated.state),
                    ),
                    GrantInstance(
                        "feather-command-1",
                        INSCRIPTION_FEATHER_ITEM_ID,
                        inscription,
                        receipt,
                        {
                            INSCRIPTION_MEDIUM_DATA_KEY: InscriptionMediumData(
                                "旧桥挑灯客遗羽",
                                "灯穗落下一枚旧羽，微光随新名散去。",
                            )
                        },
                    ),
                ),
            ),
            state=inventory,
            context=game_operation_context(
                "small-command-grant-assets",
                logical_time=logical_time,
            ),
        ).unwrap()
        snapshots.update(
            uow,
            INVENTORY_AGGREGATE,
            character_id,
            inventory,
            outcome.state,
            logical_time,
        )
        uow.commit()
    equipment_ref = outcome.state.reference_number("equipment-command-1")
    feather_ref = outcome.state.reference_number("feather-command-1")
    character = services.characters.load_character(character_id)
    assert character is not None
    overview = services.load_character_overview(character).overview
    assert overview is not None
    slot_name = services.world_view(overview.dimension).projector.name(
        equipment_definition.slot_id
    )
    return equipment_ref, feather_ref, slot_name


def _injure_character(services, character_id: str) -> None:
    snapshots = services.character_creation.snapshots
    logical_time = datetime.now(ZoneInfo("Asia/Shanghai"))
    with services.database.unit_of_work() as uow:
        character = snapshots.require(
            uow,
            CHARACTER_AGGREGATE,
            character_id,
            CharacterState,
        )
        resources = dict(character.resources)
        resources[HEALTH_CURRENT] = max(1, resources[HEALTH_CURRENT] - 10)
        updated = replace(
            character,
            resources=resources,
            revision=character.revision + 1,
        )
        snapshots.update(
            uow,
            CHARACTER_AGGREGATE,
            character_id,
            character,
            updated,
            logical_time,
        )
        uow.commit()


if __name__ == "__main__":
    main()
