"""敌人阶位使用的基础掉落表；具体奖励由业务层翻译。"""

from game.core.gameplay import (
    LootEntry,
    LootGroup,
    LootGroupMode,
    LootTableDefinition,
)


NORMAL_ENEMY_LOOT_TABLE_ID = "loot.enemy.normal"
ELITE_ENEMY_LOOT_TABLE_ID = "loot.enemy.elite"
BOSS_ENEMY_LOOT_TABLE_ID = "loot.enemy.boss"

AWARD_COMMON_MATERIAL_ID = "award.enemy.material.common"
AWARD_RARE_MATERIAL_ID = "award.enemy.material.rare"
AWARD_RANDOM_EQUIPMENT_ID = "award.enemy.gear.equipment"
AWARD_RANDOM_WEAPON_ID = "award.enemy.gear.weapon"


ENEMY_LOOT_TABLES = (
    LootTableDefinition(
        NORMAL_ENEMY_LOOT_TABLE_ID,
        1,
        (
            LootGroup(
                "loot_group.enemy.normal",
                LootGroupMode.WEIGHTED_ONE,
                (
                    LootEntry("loot_entry.enemy.normal.empty", None, weight=45),
                    LootEntry("loot_entry.enemy.normal.material", AWARD_COMMON_MATERIAL_ID, weight=48),
                    LootEntry("loot_entry.enemy.normal.equipment", AWARD_RANDOM_EQUIPMENT_ID, weight=7),
                ),
            ),
        ),
    ),
    LootTableDefinition(
        ELITE_ENEMY_LOOT_TABLE_ID,
        1,
        (
            LootGroup(
                "loot_group.enemy.elite",
                LootGroupMode.WEIGHTED_ONE,
                (
                    LootEntry("loot_entry.enemy.elite.empty", None, weight=18),
                    LootEntry("loot_entry.enemy.elite.material", AWARD_COMMON_MATERIAL_ID, weight=42),
                    LootEntry("loot_entry.enemy.elite.rare", AWARD_RARE_MATERIAL_ID, weight=20),
                    LootEntry("loot_entry.enemy.elite.equipment", AWARD_RANDOM_EQUIPMENT_ID, weight=15),
                    LootEntry("loot_entry.enemy.elite.weapon", AWARD_RANDOM_WEAPON_ID, weight=5),
                ),
            ),
        ),
    ),
    LootTableDefinition(
        BOSS_ENEMY_LOOT_TABLE_ID,
        1,
        (
            LootGroup(
                "loot_group.enemy.boss.guaranteed",
                LootGroupMode.ALL,
                (
                    LootEntry(
                        "loot_entry.enemy.boss.material",
                        AWARD_RARE_MATERIAL_ID,
                        minimum_quantity=2,
                        maximum_quantity=4,
                    ),
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
        ),
    ),
)


__all__ = [
    "AWARD_COMMON_MATERIAL_ID",
    "AWARD_RANDOM_EQUIPMENT_ID",
    "AWARD_RANDOM_WEAPON_ID",
    "AWARD_RARE_MATERIAL_ID",
    "BOSS_ENEMY_LOOT_TABLE_ID",
    "ELITE_ENEMY_LOOT_TABLE_ID",
    "ENEMY_LOOT_TABLES",
    "NORMAL_ENEMY_LOOT_TABLE_ID",
]
