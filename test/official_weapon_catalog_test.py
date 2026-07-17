"""七十二把正式武器的目录、真实执行和快速平衡巡检。"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game.content.catalog.foundation import QUALITY_IDS  # noqa: E402
from game.content.catalog import STARTER_WEAPON_ID  # noqa: E402
from game.content.catalog.weapon.balance import WeaponBalanceAuditor  # noqa: E402
from game.content.catalog.weapon.blueprints import WEAPON_BLUEPRINTS  # noqa: E402
from game.content.catalog.weapon.mechanics import (  # noqa: E402
    WEAPON_MARK_EFFECT_ID,
    WEAPON_MECHANIC_CONTENT,
)
from game.content.official import assemble_official_catalog  # noqa: E402
from game.core.gameplay import (  # noqa: E402
    AbilityUse,
    GameplayExecutor,
    ItemizationBalanceAuditor,
    RuleContext,
    RuleEntity,
    RuleEvent,
    Ruleset,
    SeededRandomSource,
)
from game.rules import (  # noqa: E402
    WeaponGenerationRequest,
    WeaponInstanceGenerator,
)


def main() -> None:
    catalog = assemble_official_catalog()
    executor = GameplayExecutor(catalog.ability_engine, catalog.trigger_engine)
    _assert_catalog_shape(catalog)
    _assert_instance_generation(catalog)
    _assert_all_active_abilities_execute(executor)
    _assert_random_branch_is_real(executor)
    _assert_mark_and_detonation_cycle(executor)
    _assert_periodic_damage(executor, catalog)
    _assert_current_cooldown_delay(executor)
    _assert_fast_balance(catalog)
    print("official weapon catalog test passed")


def _assert_catalog_shape(catalog) -> None:
    assert len(WEAPON_BLUEPRINTS) == 72
    assert len(WEAPON_MECHANIC_CONTENT.items) == 72
    assert len(WEAPON_MECHANIC_CONTENT.weapons) == 72
    assert len(WEAPON_MECHANIC_CONTENT.abilities) == 72
    assert len(WEAPON_MECHANIC_CONTENT.targeting) == 72
    assert len(WEAPON_MECHANIC_CONTENT.profiles) == 72
    assert len({value.key for value in WEAPON_BLUEPRINTS}) == 72
    assert len(
        {
            (value.primary, value.support, value.targeting)
            for value in WEAPON_BLUEPRINTS
        }
    ) == 72
    expected_ability_ids = {
        f"ability.weapon.{value.key}" for value in WEAPON_BLUEPRINTS
    }
    assert set(catalog.battle_ability_targeting) == expected_ability_ids
    for blueprint in WEAPON_BLUEPRINTS:
        targeting = catalog.battle_ability_targeting[
            f"ability.weapon.{blueprint.key}"
        ]
        if blueprint.targeting in {"single", "lowest", "random"}:
            assert targeting.maximum_targets == 1
        elif blueprint.targeting == "adjacent":
            assert targeting.maximum_targets == 3
        else:
            assert blueprint.targeting == "all"
            assert targeting.maximum_targets is None


def _assert_instance_generation(catalog) -> None:
    generator = WeaponInstanceGenerator(
        catalog.weapons,
        catalog.itemization_engine,
    )
    definition_ids = tuple(
        definition_id
        for definition_id in catalog.weapons.definitions.ids()
        if catalog.weapons.require(definition_id).generation_profile_id is not None
    )
    assert len(definition_ids) == 72
    replay_request = WeaponGenerationRequest(
        "weapon-replay",
        "asset-weapon-replay",
        definition_ids[0],
        catalog.report.content_fingerprint,
    )
    replay_left = generator.generate(
        replay_request,
        context=_context("weapon-replay", 7001),
    )
    replay_right = generator.generate(
        replay_request,
        context=_context("weapon-replay", 7001),
    )
    assert replay_left == replay_right
    for index, definition_id in enumerate(definition_ids):
        definition = catalog.weapons.require(definition_id)
        result = generator.generate(
            WeaponGenerationRequest(
                f"weapon-instance:{index}",
                f"asset-weapon-{index}",
                definition_id,
                catalog.report.content_fingerprint,
            ),
            context=_context(f"weapon-instance:{index}", index),
        )
        profile = catalog.itemization_engine.catalog.require_profile(
            definition.generation_profile_id
        )
        rolled_ids = {value.property_id for value in result.roll.properties}
        assert result.state.definition_id == definition_id
        assert result.state.quality_id == result.roll.quality_id
        assert result.state.roll == result.roll
        assert len(rolled_ids & profile.core_property_ids) == 1
    try:
        generator.generate(
            WeaponGenerationRequest(
                "weapon-starter-rejected",
                "asset-starter-rejected",
                STARTER_WEAPON_ID,
                catalog.report.content_fingerprint,
            ),
            context=_context("weapon-starter-rejected", 9001),
        )
        raise AssertionError("固定新手武器不得进入随机生成器")
    except ValueError as exc:
        assert "固定武器" in str(exc)


def _assert_all_active_abilities_execute(executor: GameplayExecutor) -> None:
    for index, blueprint in enumerate(WEAPON_BLUEPRINTS):
        ability_id = f"ability.weapon.{blueprint.key}"
        actor = _entity("actor", ability_id=ability_id)
        target = _entity("target")
        outcome = executor.execute_ability(
            AbilityUse(f"weapon-all:{index}", ability_id),
            actor=actor,
            target=target,
            context=_context(f"weapon-all:{index}", index),
        )
        assert outcome.failure is None, (blueprint.key, outcome.failure)
        assert outcome.value is not None
        assert outcome.value.target.resources["health.current"] < 100_000


def _assert_random_branch_is_real(executor: GameplayExecutor) -> None:
    ability_id = "ability.weapon.fate_die"
    branches = set()
    damage_values = set()
    for seed in range(32):
        outcome = executor.execute_ability(
            AbilityUse(f"fate-die:{seed}", ability_id),
            actor=_entity("actor", ability_id=ability_id),
            target=_entity("target"),
            context=_context(f"fate-die:{seed}", seed),
        )
        assert outcome.failure is None and outcome.value is not None
        choice_events = tuple(
            event
            for event in outcome.value.events
            if event.kind == "effect.choice.selected"
        )
        assert len(choice_events) == 1
        branches.add(choice_events[0].values["branch"])
        damage_values.add(
            100_000 - outcome.value.target.resources["health.current"]
        )
    assert branches == {0, 1}
    assert len(damage_values) == 2


def _assert_mark_and_detonation_cycle(executor: GameplayExecutor) -> None:
    ability_id = "ability.weapon.hidden_edge_coffer"
    first = executor.execute_ability(
        AbilityUse("mark-cycle:first", ability_id),
        actor=_entity("actor", ability_id=ability_id),
        target=_entity("target"),
        context=_context("mark-cycle:first", 11),
    )
    assert first.failure is None and first.value is not None
    assert _effect_stacks(first.value.target, WEAPON_MARK_EFFECT_ID) == 1
    first_damage = 100_000 - first.value.target.resources["health.current"]

    second_actor = replace(first.value.actor, cooldowns={})
    second = executor.execute_ability(
        AbilityUse("mark-cycle:second", ability_id),
        actor=second_actor,
        target=first.value.target,
        context=_context("mark-cycle:second", 12),
    )
    assert second.failure is None and second.value is not None
    second_damage = (
        first.value.target.resources["health.current"]
        - second.value.target.resources["health.current"]
    )
    assert second_damage > first_damage
    assert _effect_stacks(second.value.target, WEAPON_MARK_EFFECT_ID) == 1


def _assert_periodic_damage(executor: GameplayExecutor, catalog) -> None:
    ability_id = "ability.weapon.plague_banner"
    applied = executor.execute_ability(
        AbilityUse("periodic:apply", ability_id),
        actor=_entity("actor", ability_id=ability_id),
        target=_entity("target"),
        context=_context("periodic:apply", 21),
    )
    assert applied.failure is None and applied.value is not None
    health_before = applied.value.target.resources["health.current"]
    turn_context = _context("periodic:turn", 22)
    event = RuleEvent.from_context(
        turn_context,
        kind="combat.turn.started",
        source_id="target",
        target_id="target",
        subject_id="combat.turn",
    )
    result = catalog.trigger_engine.process(
        (event,),
        entities={"actor": applied.value.actor, "target": applied.value.target},
        context=turn_context,
    )
    assert result.entity("target").resources["health.current"] < health_before
    assert any(
        value.kind == "combat.damage.dealt"
        and value.values.get("damage_type") == "damage.poison"
        for value in result.events
    )


def _assert_current_cooldown_delay(executor: GameplayExecutor) -> None:
    ability_id = "ability.weapon.null_blade"
    target = _entity("target", cooldowns={"ability.basic_attack": 2})
    outcome = executor.execute_ability(
        AbilityUse("cooldown-delay", ability_id),
        actor=_entity("actor", ability_id=ability_id),
        target=target,
        context=_context("cooldown-delay", 31),
    )
    assert outcome.failure is None and outcome.value is not None
    assert outcome.value.target.cooldowns["ability.basic_attack"] == 3


def _assert_fast_balance(catalog) -> None:
    static_start = perf_counter()
    static_report = WeaponBalanceAuditor().audit()
    assert len(static_report.entries) == 72
    assert not static_report.outliers(22.0)
    assert perf_counter() - static_start < 1.0

    generation_start = perf_counter()
    generation_report = ItemizationBalanceAuditor(
        catalog.itemization_engine
    ).audit(
        profile_ids=tuple(
            value.id for value in WEAPON_MECHANIC_CONTENT.profiles
        ),
        content_fingerprint=catalog.report.content_fingerprint,
        samples_per_profile=128,
    )
    elapsed = perf_counter() - generation_start
    assert generation_report.total_samples == 72 * 128
    assert set(generation_report.quality_counts) == set(QUALITY_IDS)
    assert not generation_report.profiles_above_attempts(1.05)
    assert elapsed < 15.0, elapsed
    ratios = {
        quality_id: amount / generation_report.total_samples
        for quality_id, amount in generation_report.quality_counts.items()
    }
    assert 0.40 <= ratios["quality.common"] <= 0.52
    assert 0.24 <= ratios["quality.fine"] <= 0.36
    assert 0.10 <= ratios["quality.rare"] <= 0.20
    assert 0.04 <= ratios["quality.epic"] <= 0.11
    assert 0.005 <= ratios["quality.legendary"] <= 0.03


def _context(trace_id: str, seed: int) -> RuleContext:
    return RuleContext(
        trace_id,
        "rules.weapon_catalog_test",
        Ruleset("ruleset.weapon_catalog_test"),
        datetime(2026, 7, 16, tzinfo=timezone.utc),
        SeededRandomSource(seed),
    )


def _entity(
    entity_id: str,
    *,
    ability_id: str | None = None,
    cooldowns=None,
) -> RuleEntity:
    return RuleEntity(
        entity_id,
        base_attributes={
            "health.maximum": 100_000,
            "spirit.maximum": 1_000,
            "combat.attack": 100,
            "combat.defense.physical": 0,
            "combat.speed": 100,
            "combat.accuracy": 1,
            "combat.critical.chance": 0,
        },
        resources={
            "health.current": 100_000,
            "spirit.current": 1_000,
            "combat.shield.current": 0,
        },
        base_abilities=frozenset({ability_id}) if ability_id else frozenset(),
        cooldowns=cooldowns or {},
    )


def _effect_stacks(entity: RuleEntity, effect_id: str) -> int:
    return sum(
        value.stacks
        for value in entity.active_effects
        if value.definition_id == effect_id
    )


if __name__ == "__main__":
    main()
