"""敌人阶位使用的多轨掉落表；具体奖励由探险玩法翻译。"""

from game.core.gameplay import (
    LootEntry,
    LootGroup,
    LootGroupMode,
    LootTableDefinition,
)


NORMAL_ENEMY_LOOT_TABLE_ID = "loot.enemy.normal"
ELITE_ENEMY_LOOT_TABLE_ID = "loot.enemy.elite"
BOSS_ENEMY_LOOT_TABLE_ID = "loot.enemy.boss"

AWARD_REGION_TROPHY_ID = "award.enemy.trophy.region"
AWARD_ENEMY_TROPHY_ID = "award.enemy.trophy.identity"
AWARD_BOSS_TROPHY_ID = "award.enemy.trophy.boss"
AWARD_WORLD_CURIO_ID = "award.enemy.trophy.curio"
AWARD_SMALL_HEALTH_MEDICINE_ID = "award.enemy.medicine.small_health"
AWARD_SMALL_SPIRIT_MEDICINE_ID = "award.enemy.medicine.small_spirit"
AWARD_MEDIUM_HEALTH_MEDICINE_ID = "award.enemy.medicine.medium_health"
AWARD_MEDIUM_SPIRIT_MEDICINE_ID = "award.enemy.medicine.medium_spirit"
AWARD_LARGE_HEALTH_MEDICINE_ID = "award.enemy.medicine.large_health"
AWARD_LARGE_SPIRIT_MEDICINE_ID = "award.enemy.medicine.large_spirit"
AWARD_RANDOM_EQUIPMENT_ID = "award.enemy.gear.equipment"
AWARD_RANDOM_WEAPON_ID = "award.enemy.gear.weapon"


ENEMY_LOOT_TABLES = (
    LootTableDefinition(
        NORMAL_ENEMY_LOOT_TABLE_ID,
        3,
        (
            LootGroup(
                "loot_group.enemy.normal.income",
                LootGroupMode.ALL,
                (LootEntry("loot_entry.enemy.normal.region_trophy", AWARD_REGION_TROPHY_ID),),
            ),
            LootGroup(
                "loot_group.enemy.normal.identity",
                LootGroupMode.INDEPENDENT,
                (LootEntry("loot_entry.enemy.normal.identity_trophy", AWARD_ENEMY_TROPHY_ID, chance=100_000),),
            ),
            LootGroup(
                "loot_group.enemy.normal.supply",
                LootGroupMode.INDEPENDENT,
                (
                    LootEntry("loot_entry.enemy.normal.small_health", AWARD_SMALL_HEALTH_MEDICINE_ID, chance=40_000),
                    LootEntry("loot_entry.enemy.normal.small_spirit", AWARD_SMALL_SPIRIT_MEDICINE_ID, chance=30_000),
                ),
            ),
            LootGroup(
                "loot_group.enemy.normal.gear",
                LootGroupMode.WEIGHTED_ONE,
                (
                    LootEntry("loot_entry.enemy.normal.empty", None, weight=93),
                    LootEntry("loot_entry.enemy.normal.equipment", AWARD_RANDOM_EQUIPMENT_ID, weight=7),
                ),
            ),
            LootGroup(
                "loot_group.enemy.normal.curio",
                LootGroupMode.INDEPENDENT,
                (LootEntry("loot_entry.enemy.normal.curio", AWARD_WORLD_CURIO_ID, chance=500),),
            ),
        ),
    ),
    LootTableDefinition(
        ELITE_ENEMY_LOOT_TABLE_ID,
        3,
        (
            LootGroup(
                "loot_group.enemy.elite.income",
                LootGroupMode.ALL,
                (LootEntry("loot_entry.enemy.elite.region_trophy", AWARD_REGION_TROPHY_ID, minimum_quantity=2, maximum_quantity=2),),
            ),
            LootGroup(
                "loot_group.enemy.elite.identity",
                LootGroupMode.INDEPENDENT,
                (LootEntry("loot_entry.enemy.elite.identity_trophy", AWARD_ENEMY_TROPHY_ID, chance=400_000),),
            ),
            LootGroup(
                "loot_group.enemy.elite.supply",
                LootGroupMode.INDEPENDENT,
                (
                    LootEntry("loot_entry.enemy.elite.small_health", AWARD_SMALL_HEALTH_MEDICINE_ID, chance=120_000),
                    LootEntry("loot_entry.enemy.elite.small_spirit", AWARD_SMALL_SPIRIT_MEDICINE_ID, chance=100_000),
                    LootEntry("loot_entry.enemy.elite.medium_health", AWARD_MEDIUM_HEALTH_MEDICINE_ID, chance=40_000),
                    LootEntry("loot_entry.enemy.elite.medium_spirit", AWARD_MEDIUM_SPIRIT_MEDICINE_ID, chance=30_000),
                ),
            ),
            LootGroup(
                "loot_group.enemy.elite.gear",
                LootGroupMode.WEIGHTED_ONE,
                (
                    LootEntry("loot_entry.enemy.elite.empty", None, weight=80),
                    LootEntry("loot_entry.enemy.elite.equipment", AWARD_RANDOM_EQUIPMENT_ID, weight=15),
                    LootEntry("loot_entry.enemy.elite.weapon", AWARD_RANDOM_WEAPON_ID, weight=5),
                ),
            ),
            LootGroup(
                "loot_group.enemy.elite.curio",
                LootGroupMode.INDEPENDENT,
                (LootEntry("loot_entry.enemy.elite.curio", AWARD_WORLD_CURIO_ID, chance=2_000),),
            ),
        ),
    ),
    LootTableDefinition(
        BOSS_ENEMY_LOOT_TABLE_ID,
        3,
        (
            LootGroup(
                "loot_group.enemy.boss.income",
                LootGroupMode.ALL,
                (LootEntry("loot_entry.enemy.boss.region_trophy", AWARD_REGION_TROPHY_ID, minimum_quantity=5, maximum_quantity=5),),
            ),
            LootGroup(
                "loot_group.enemy.boss.relic",
                LootGroupMode.ALL,
                (LootEntry("loot_entry.enemy.boss.identity_trophy", AWARD_BOSS_TROPHY_ID),),
            ),
            LootGroup(
                "loot_group.enemy.boss.supply",
                LootGroupMode.INDEPENDENT,
                (
                    LootEntry("loot_entry.enemy.boss.medium_health", AWARD_MEDIUM_HEALTH_MEDICINE_ID, chance=250_000),
                    LootEntry("loot_entry.enemy.boss.medium_spirit", AWARD_MEDIUM_SPIRIT_MEDICINE_ID, chance=200_000),
                    LootEntry("loot_entry.enemy.boss.large_health", AWARD_LARGE_HEALTH_MEDICINE_ID, chance=60_000),
                    LootEntry("loot_entry.enemy.boss.large_spirit", AWARD_LARGE_SPIRIT_MEDICINE_ID, chance=50_000),
                ),
            ),
            LootGroup(
                "loot_group.enemy.boss.gear",
                LootGroupMode.WEIGHTED_ONE,
                (
                    LootEntry("loot_entry.enemy.boss.equipment", AWARD_RANDOM_EQUIPMENT_ID, weight=70),
                    LootEntry("loot_entry.enemy.boss.weapon", AWARD_RANDOM_WEAPON_ID, weight=30),
                ),
            ),
            LootGroup(
                "loot_group.enemy.boss.curio",
                LootGroupMode.INDEPENDENT,
                (LootEntry("loot_entry.enemy.boss.curio", AWARD_WORLD_CURIO_ID, chance=10_000),),
            ),
        ),
    ),
)


__all__ = [
    "AWARD_BOSS_TROPHY_ID",
    "AWARD_ENEMY_TROPHY_ID",
    "AWARD_LARGE_HEALTH_MEDICINE_ID",
    "AWARD_LARGE_SPIRIT_MEDICINE_ID",
    "AWARD_MEDIUM_HEALTH_MEDICINE_ID",
    "AWARD_MEDIUM_SPIRIT_MEDICINE_ID",
    "AWARD_RANDOM_EQUIPMENT_ID",
    "AWARD_RANDOM_WEAPON_ID",
    "AWARD_REGION_TROPHY_ID",
    "AWARD_SMALL_HEALTH_MEDICINE_ID",
    "AWARD_SMALL_SPIRIT_MEDICINE_ID",
    "AWARD_WORLD_CURIO_ID",
    "BOSS_ENEMY_LOOT_TABLE_ID",
    "ELITE_ENEMY_LOOT_TABLE_ID",
    "ENEMY_LOOT_TABLES",
    "NORMAL_ENEMY_LOOT_TABLE_ID",
]
