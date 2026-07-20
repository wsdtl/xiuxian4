"""正式敌人名录、遭遇生成、共享特效、AI 与展示回归测试。"""

from datetime import datetime, timezone
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game.content import build_official_content  # noqa: E402
from game.content.catalog import (  # noqa: E402
    PERSONAL_ELITE_ENCOUNTER_ID,
    PERSONAL_NORMAL_ENCOUNTER_ID,
)
from game.content.catalog.enemy import (  # noqa: E402
    BEHAVIOR_BLUEPRINTS,
    PARTY_BOSS_ENEMIES,
    PERSONAL_BOSS_ENEMIES,
    REGULAR_ENEMIES,
)
from game.content.catalog.disaster.combat import DISASTER_ENEMY_DEFINITIONS  # noqa: E402
from game.core.gameplay import (  # noqa: E402
    BATTLE_AI_FOUNDATION_VERSION,
    COMBAT_SPEED,
    HEALTH_CURRENT,
    BattleEngine,
    BattleParticipant,
    BattleRules,
    EnemyInstance,
    ENEMY_FOUNDATION_VERSION,
    GameplayExecutor,
    AbilityUse,
    RuleEntity,
    RuleContext,
    Ruleset,
    SeededRandomSource,
)
from game.rules import EnemyDefeatRewardPlanner, EnemyEncounterGenerator  # noqa: E402
from game.rules.battle_report import KNOWN_BATTLE_EVENT_KINDS  # noqa: E402


def main() -> None:
    assert BATTLE_AI_FOUNDATION_VERSION == "combat-ai.foundation.v2"
    assert ENEMY_FOUNDATION_VERSION == "enemy.foundation.v1"
    cultivation = build_official_content()
    magic = build_official_content("skin.magic")
    catalog = cultivation.catalog

    assert len(BEHAVIOR_BLUEPRINTS) == 32
    assert len(REGULAR_ENEMIES) == 60
    assert len(PERSONAL_BOSS_ENEMIES) == 30
    assert len(PARTY_BOSS_ENEMIES) == 20
    assert len(DISASTER_ENEMY_DEFINITIONS) == 20
    assert len(catalog.enemies.definitions.ids()) == 130
    assert len(catalog.enemies.behaviors.ids()) == 32
    assert len(catalog.enemies.encounters.ids()) == 4
    personal_ids = {value.id for value in PERSONAL_BOSS_ENEMIES}
    party_ids = {value.id for value in PARTY_BOSS_ENEMIES}
    disaster_ids = {value.id for value in DISASTER_ENEMY_DEFINITIONS}
    assert not personal_ids & party_ids
    assert not personal_ids & disaster_ids
    assert not party_ids & disaster_ids

    shared_enemy = catalog.abilities.require("ability.enemy.heavy_strike")
    shared_weapon = catalog.abilities.require("ability.weapon.mountain_cleaver")
    assert shared_enemy.effects == shared_weapon.effects
    assert shared_enemy.costs == shared_weapon.costs
    assert shared_enemy.cooldown_turns == shared_weapon.cooldown_turns

    generator = EnemyEncounterGenerator(
        catalog.enemies,
        content_version=catalog.report.content_fingerprint,
    )
    first = generator.generate(
        PERSONAL_ELITE_ENCOUNTER_ID,
        level=36,
        generation_seed="elite-demo",
        random=SeededRandomSource("elite-demo"),
    )
    repeated = generator.generate(
        PERSONAL_ELITE_ENCOUNTER_ID,
        level=36,
        generation_seed="elite-demo",
        random=SeededRandomSource("elite-demo"),
    )
    assert first == repeated
    assert len(first.enemies) == 1
    elite = first.enemies[0]
    assert len(elite.behavior_ids) == 2

    cultivation_name = cultivation.enemy_projector.enemy(elite).name
    magic_name = magic.enemy_projector.enemy(elite).name
    assert "·" in cultivation_name and "·" in magic_name
    assert cultivation_name == cultivation.enemy_projector.enemy(elite).name
    assert cultivation_name != magic_name

    boss = EnemyInstance(
        "enemy-instance-boss",
        "enemy.boss.nine_headed_plague",
        50,
        "enemy.rank.boss",
        tuple(sorted(PERSONAL_BOSS_ENEMIES[0].default_behavior_ids)),
        "boss-demo",
        catalog.report.content_fingerprint,
    )
    assert cultivation.enemy_projector.enemy(boss).name == "化蛇·洪涛妖君"
    assert magic.enemy_projector.enemy(boss).name == "九头蛇·沼泽暴君"

    reward = EnemyDefeatRewardPlanner(catalog.enemy_threat).quote(first.enemies)
    assert reward.character_experience > 0
    assert reward.weapon_experience > 0
    assert reward.threat_score > 0
    assert reward.loot and reward.loot[0].table_id == "loot.enemy.elite"

    _assert_ai_executes(cultivation)
    _assert_all_behavior_abilities_execute(cultivation)
    print("official enemy catalog test passed")


def _assert_ai_executes(content) -> None:
    catalog = content.catalog
    fingerprint = catalog.report.content_fingerprint
    attacker = EnemyInstance(
        "enemy-attacker",
        "enemy.mountain_ape",
        20,
        "enemy.rank.normal",
        ("enemy.behavior.heavy_strike",),
        "ai-attacker",
        fingerprint,
    )
    target = EnemyInstance(
        "enemy-target",
        "enemy.stone_guardian",
        20,
        "enemy.rank.normal",
        ("enemy.behavior.block",),
        "ai-target",
        fingerprint,
    )
    attacker_projection = catalog.enemy_projector.project(attacker)
    target_projection = catalog.enemy_projector.project(target)
    context = RuleContext(
        "enemy-ai-test",
        "rule.enemy.test.v1",
        Ruleset("ruleset.enemy.test"),
        datetime.now(timezone.utc),
        SeededRandomSource("enemy-ai-test"),
    )
    engine = BattleEngine(
        GameplayExecutor(catalog.ability_engine, catalog.trigger_engine),
        BattleRules(HEALTH_CURRENT, COMBAT_SPEED),
        catalog.battle_ability_targeting,
        catalog.target_selectors,
    )
    started = engine.start(
        "battle-enemy-ai",
        participants=(
            BattleParticipant(attacker.id, "team.attackers", 0),
            BattleParticipant(target.id, "team.targets", 0),
        ),
        entities={
            attacker.id: attacker_projection.entity,
            target.id: target_projection.entity,
        },
        context=context,
    )
    assert started.ok
    state = started.value.state
    rules_by_id = {
        attacker.id: attacker_projection.ai_rules,
        target.id: target_projection.ai_rules,
    }
    actor_id = state.current_actor_id
    assert actor_id is not None
    action = catalog.battle_ai_engine.decide(
        rules_by_id[actor_id],
        state,
        actor_id,
        context=context,
    )
    assert action is not None
    assert action.ability_id.startswith("ability.enemy.")
    result = engine.execute_turn(state, action, context=context)
    assert result.ok
    assert any(event.kind == "combat.turn.ended" for event in result.value.events)


def _assert_all_behavior_abilities_execute(content) -> None:
    catalog = content.catalog
    executor = GameplayExecutor(catalog.ability_engine, catalog.trigger_engine)
    covered = set()
    for index, behavior in enumerate(catalog.enemies.behaviors):
        assert len(behavior.contribution.abilities) == 1
        ability_id = next(iter(behavior.contribution.abilities))
        actor = _effect_combatant("actor", ability_id)
        target = _effect_combatant("target")
        outcome = executor.execute_ability(
            AbilityUse(f"enemy-behavior:{index}", ability_id),
            actor=actor,
            target=target,
            context=RuleContext(
                f"enemy-behavior:{index}",
                "rule.enemy.behavior_test.v1",
                Ruleset("ruleset.enemy.behavior_test"),
                datetime.now(timezone.utc),
                SeededRandomSource(index),
            ),
        )
        assert outcome.failure is None, (behavior.id, outcome.failure)
        assert outcome.value is not None
        unknown = {
            str(event.kind) for event in outcome.value.events
        } - KNOWN_BATTLE_EVENT_KINDS
        assert not unknown, (behavior.id, unknown)
        covered.add(behavior.id)
    assert covered == set(catalog.enemies.behaviors.ids())
    phase_behavior_ids = {
        behavior_id
        for enemy in catalog.enemies.definitions
        for phase in enemy.phases
        for behavior_id in phase.behavior_ids
    }
    assert phase_behavior_ids.issubset(covered)


def _effect_combatant(entity_id: str, ability_id: str | None = None) -> RuleEntity:
    return RuleEntity(
        entity_id,
        base_attributes={
            "health.maximum": 100_000,
            "spirit.maximum": 10_000,
            "combat.attack": 1_000,
            "combat.defense.physical": 100,
            "combat.speed": 100,
            "combat.accuracy": 1,
            "combat.critical.chance": 0.5,
            "combat.critical.damage": 0.5,
        },
        resources={
            "health.current": 50_000,
            "spirit.current": 10_000,
            "combat.shield.current": 1_000,
        },
        base_abilities=frozenset({ability_id}) if ability_id else frozenset(),
    )


if __name__ == "__main__":
    main()
