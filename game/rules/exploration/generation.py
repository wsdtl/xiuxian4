"""按区域生态生成可审计的十分钟探险批次。"""

from game.content.catalog.enemy import (
    PERSONAL_BOSS_ENCOUNTER_ID,
    PERSONAL_ELITE_ENCOUNTER_ID,
    PERSONAL_NORMAL_ENCOUNTER_ID,
)
from game.content.catalog.exploration import ExplorationRegionCatalog
from game.core.gameplay import RandomSource
from game.rules.encounter import EnemyEncounterGenerator

from .models import ExplorationBatchPlan, ExplorationEncounterKind


class ExplorationBatchPlanner:
    def __init__(
        self,
        regions: ExplorationRegionCatalog,
        encounters: EnemyEncounterGenerator,
    ) -> None:
        self.regions = regions
        self.encounters = encounters

    def plan(
        self,
        *,
        session_id: str,
        batch_index: int,
        region_id: str,
        character_level: int,
        random: RandomSource,
    ) -> ExplorationBatchPlan:
        region = self.regions.require(region_id)
        seed = f"{session_id}:batch:{batch_index}"
        kind = self._kind(region.encounter_weights, random)
        level = region.enemy_level(character_level)
        if kind is ExplorationEncounterKind.EMPTY:
            return ExplorationBatchPlan(
                session_id,
                batch_index,
                region.id,
                region.location_id,
                kind,
                level,
                seed,
                loot_modifiers=region.loot_modifiers,
            )
        encounter_id = {
            ExplorationEncounterKind.NORMAL: PERSONAL_NORMAL_ENCOUNTER_ID,
            ExplorationEncounterKind.ELITE: PERSONAL_ELITE_ENCOUNTER_ID,
            ExplorationEncounterKind.BOSS: PERSONAL_BOSS_ENCOUNTER_ID,
        }[kind]
        allowed = (
            region.boss_enemy_ids
            if kind is ExplorationEncounterKind.BOSS
            else region.regular_enemy_ids
        )
        encounter = self.encounters.generate(
            encounter_id,
            level=level,
            generation_seed=seed,
            random=random,
            instance_id=f"exploration:{seed}",
            allowed_enemy_ids=allowed,
        )
        return ExplorationBatchPlan(
            session_id,
            batch_index,
            region.id,
            region.location_id,
            kind,
            level,
            seed,
            encounter,
            region.loot_modifiers,
        )

    @staticmethod
    def _kind(weights, random: RandomSource) -> ExplorationEncounterKind:
        values = (
            (ExplorationEncounterKind.NORMAL, weights.normal),
            (ExplorationEncounterKind.ELITE, weights.elite),
            (ExplorationEncounterKind.BOSS, weights.boss),
            (ExplorationEncounterKind.EMPTY, weights.empty),
        )
        total = sum(weight for _, weight in values)
        sampled = random.randint(1, total)
        cursor = 0
        for kind, weight in values:
            cursor += weight
            if sampled <= cursor:
                return kind
        raise AssertionError("探险遭遇权重采样越界")


__all__ = ["ExplorationBatchPlanner"]
