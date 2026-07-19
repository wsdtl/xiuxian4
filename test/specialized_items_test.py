"""芥子神砂与合道玉契的持久化、边界和装备生成测试。"""

from datetime import datetime, timezone
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game.app import build_game_services  # noqa: E402
from game.content import (  # noqa: E402
    BACKPACK_CAPACITY_ITEM_ID,
    BACKPACK_CAPACITY_MAXIMUM,
    EQUIPMENT_SET_GUARANTEE_ITEM_ID,
)
from game.content.catalog.enemy import AWARD_RANDOM_EQUIPMENT_ID  # noqa: E402
from game.core.account import ExternalIdentity, IdentityEvidence  # noqa: E402
from game.core.gameplay import (  # noqa: E402
    GrantStack,
    InventoryState,
    InventoryTransaction,
    LootAward,
    RuleContext,
    Ruleset,
    SeededRandomSource,
    SourceReceipt,
)
from game.core.persistence import INVENTORY_AGGREGATE  # noqa: E402
from game.features.exploration.rewards import ExplorationRewardFactory  # noqa: E402
from game.features.special_items import SpecialItemUseCommand  # noqa: E402
from game.rules.equipment import (  # noqa: E402
    EQUIPMENT_SET_GUARANTEE_AGGREGATE,
    EquipmentSetGuaranteeState,
    consume_equipment_set_guarantee,
)


TIME = datetime(2026, 7, 19, 16, 0, tzinfo=timezone.utc)


def main() -> None:
    with TemporaryDirectory() as directory:
        services = build_game_services(
            database_path=Path(directory) / "specialized-items.db",
            identity_secret="specialized-items-secret",
        )
        services.database.initialize()
        character = _create_character(services)
        _grant_special_items(services, character.id)

        for index in range(20):
            outcome = services.special_item_use.use(
                SpecialItemUseCommand(
                    f"capacity-use:{index}",
                    character.id,
                    "stack:backpack-capacity",
                ),
                inventory_id=character.id,
                context=_context(f"capacity-use:{index}", index),
            )
            assert outcome.ok and outcome.value is not None, outcome.failure
        inventory = _inventory(services, character.id)
        backpack = next(
            value for value in inventory.containers.values() if value.kind == "container.backpack"
        )
        assert backpack.maximum_space == BACKPACK_CAPACITY_MAXIMUM == 140
        assert inventory.stacks["stack:backpack-capacity"].quantity == 1

        rejected = services.special_item_use.use(
            SpecialItemUseCommand(
                "capacity-use:rejected",
                character.id,
                "stack:backpack-capacity",
            ),
            inventory_id=character.id,
            context=_context("capacity-use:rejected", 100),
        )
        assert rejected.failure is not None
        assert rejected.failure.code == "inventory.container_space_maximum_reached"
        assert _inventory(services, character.id).stacks[
            "stack:backpack-capacity"
        ].quantity == 1

        activated = services.special_item_use.use(
            SpecialItemUseCommand(
                "set-guarantee:activate",
                character.id,
                "stack:set-guarantee",
            ),
            inventory_id=character.id,
            context=_context("set-guarantee:activate", 101),
        )
        assert activated.ok and activated.value is not None, activated.failure
        active_state = _guarantee(services, character.id)
        assert active_state.charges == 1
        assert _inventory(services, character.id).stacks["stack:set-guarantee"].quantity == 1

        duplicate = services.special_item_use.use(
            SpecialItemUseCommand(
                "set-guarantee:duplicate",
                character.id,
                "stack:set-guarantee",
            ),
            inventory_id=character.id,
            context=_context("set-guarantee:duplicate", 102),
        )
        assert duplicate.failure is not None
        assert duplicate.failure.code == "special_item.guarantee_already_active"
        assert _inventory(services, character.id).stacks["stack:set-guarantee"].quantity == 1

        overview = services.load_character_overview(character).overview
        assert overview is not None
        build = ExplorationRewardFactory(services.content).build(
            (
                LootAward(
                    0,
                    0,
                    "loot_group.test",
                    "loot_entry.test",
                    AWARD_RANDOM_EQUIPMENT_ID,
                    1,
                ),
            ),
            plan=SimpleNamespace(encounter=None),
            character=overview.character,
            inventory=overview.inventory,
            loadout=overview.loadout,
            character_experience=0,
            weapon_experience=0,
            equipment_set_guarantee_charges=active_state.charges,
            context=_context("set-guarantee:equipment-drop", 103),
        )
        assert build.equipment_drops == 1
        assert build.equipment_set_guarantees_consumed == 1
        generated = next(
            reward.state
            for reward in build.rewards
            if hasattr(reward, "state") and reward.state.asset_id.startswith("asset:")
        )
        assert generated.set_id is not None
        assert consume_equipment_set_guarantee(active_state, 1).charges == 0
    print("specialized item tests passed")


def _create_character(services):
    evidence = IdentityEvidence(
        "evidence:specialized-items",
        ExternalIdentity(
            "platform.local",
            "specialized-items",
            "identity.user",
            "private",
            "specialized-items-user",
        ),
        (),
        "message.local",
        TIME,
    )
    created = services.create_character(evidence, requested_name="试砂人")
    assert created.status == "created" and created.receipt is not None
    return created.receipt.character


def _grant_special_items(services, character_id: str) -> None:
    snapshots = services.special_item_use.snapshots
    with services.database.unit_of_work() as uow:
        inventory = snapshots.require(
            uow,
            INVENTORY_AGGREGATE,
            character_id,
            InventoryState,
        )
        special = next(
            value for value in inventory.containers.values() if value.kind == "container.special"
        )
        outcome = services.special_item_use.inventory_engine.execute(
            InventoryTransaction(
                "grant:specialized-items",
                character_id,
                "inventory.test_grant",
                (
                    GrantStack(
                        "stack:backpack-capacity",
                        BACKPACK_CAPACITY_ITEM_ID,
                        special.id,
                        21,
                        SourceReceipt(
                            "receipt:backpack-capacity",
                            "source.test",
                            "specialized-items",
                            TIME,
                        ),
                    ),
                    GrantStack(
                        "stack:set-guarantee",
                        EQUIPMENT_SET_GUARANTEE_ITEM_ID,
                        special.id,
                        2,
                        SourceReceipt(
                            "receipt:set-guarantee",
                            "source.test",
                            "specialized-items",
                            TIME,
                        ),
                    ),
                ),
            ),
            state=inventory,
            context=_context("grant:specialized-items", 0),
        )
        assert outcome.ok and outcome.value is not None, outcome.failure
        snapshots.update(
            uow,
            INVENTORY_AGGREGATE,
            character_id,
            inventory,
            outcome.value.state,
            TIME,
        )
        uow.commit()


def _inventory(services, character_id: str) -> InventoryState:
    with services.database.unit_of_work(write=False) as uow:
        return services.special_item_use.snapshots.require(
            uow,
            INVENTORY_AGGREGATE,
            character_id,
            InventoryState,
        )


def _guarantee(services, character_id: str) -> EquipmentSetGuaranteeState:
    with services.database.unit_of_work(write=False) as uow:
        return services.special_item_use.snapshots.require(
            uow,
            EQUIPMENT_SET_GUARANTEE_AGGREGATE,
            character_id,
            EquipmentSetGuaranteeState,
        )


def _context(trace_id: str, seed: int) -> RuleContext:
    return RuleContext(
        trace_id,
        "rules.specialized_items_test.v1",
        Ruleset("ruleset.specialized_items_test"),
        TIME,
        SeededRandomSource(seed),
    )


if __name__ == "__main__":
    main()
