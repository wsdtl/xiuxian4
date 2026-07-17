"""把敌人威胁报价汇总为统一奖励结算之前的业务计划。"""

from dataclasses import dataclass

from game.core.gameplay import EnemyInstance, EnemyThreatEvaluator, StableId


@dataclass(frozen=True)
class EnemyLootQuote:
    table_id: StableId
    rolls: int


@dataclass(frozen=True)
class EnemyDefeatRewardQuote:
    character_experience: int
    weapon_experience: int
    loot: tuple[EnemyLootQuote, ...]
    threat_score: float


class EnemyDefeatRewardPlanner:
    """只决定奖励内容，不写库存、角色或经济快照。"""

    def __init__(self, evaluator: EnemyThreatEvaluator) -> None:
        self.evaluator = evaluator

    def quote(self, enemies: tuple[EnemyInstance, ...]) -> EnemyDefeatRewardQuote:
        if not enemies:
            raise ValueError("敌人奖励报价不能为空")
        character_experience = 0
        weapon_experience = 0
        threat_score = 0.0
        loot_rolls: dict[StableId, int] = {}
        for enemy in enemies:
            quote = self.evaluator.reward_quote(enemy)
            character_experience += quote.character_experience
            weapon_experience += quote.weapon_experience
            threat_score += quote.threat_score
            if quote.loot_table_id is not None and quote.loot_rolls > 0:
                loot_rolls[quote.loot_table_id] = loot_rolls.get(quote.loot_table_id, 0) + quote.loot_rolls
        return EnemyDefeatRewardQuote(
            character_experience,
            weapon_experience,
            tuple(EnemyLootQuote(table_id, rolls) for table_id, rolls in sorted(loot_rolls.items())),
            threat_score,
        )


__all__ = ["EnemyDefeatRewardPlanner", "EnemyDefeatRewardQuote", "EnemyLootQuote"]
