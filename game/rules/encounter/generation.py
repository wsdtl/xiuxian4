"""正式遭遇与敌人实例的确定性、世界倾向构筑规则。"""

from typing import Mapping

from game.core.gameplay import (
    EnemyCatalog,
    EnemyEncounterInstance,
    EnemyInstance,
    EnemyPhaseLoadout,
    RandomSource,
    StableId,
)


class EnemyEncounterGenerator:
    def __init__(self, catalog: EnemyCatalog, *, content_version: str) -> None:
        if not catalog.finalized:
            raise RuntimeError("敌人目录必须先完成装配")
        if not content_version.strip():
            raise ValueError("遭遇生成器缺少内容版本")
        self.catalog = catalog
        self.content_version = content_version

    def generate(
        self,
        encounter_id: str,
        *,
        level: int,
        generation_seed: str,
        random: RandomSource,
        instance_id: str | None = None,
        allowed_enemy_ids: frozenset[str] | None = None,
        behavior_weights: Mapping[StableId, int] | None = None,
    ) -> EnemyEncounterInstance:
        definition = self.catalog.encounters.require(encounter_id)
        if not definition.minimum_level <= level <= definition.maximum_level:
            raise ValueError(
                f"遭遇 {definition.id} 等级必须位于 "
                f"{definition.minimum_level} 到 {definition.maximum_level}"
            )
        if not generation_seed.strip():
            raise ValueError("遭遇生成必须提供可审计种子")
        encounter_instance_id = instance_id or f"encounter:{definition.id}:{generation_seed}"
        enemies = []
        sequence = 0
        for spawn in definition.spawns:
            count = random.randint(spawn.minimum_count, spawn.maximum_count)
            candidates = spawn.enemy_ids
            if allowed_enemy_ids is not None:
                candidates = candidates & allowed_enemy_ids
            if not candidates:
                raise ValueError(f"遭遇 {definition.id} 与指定敌人池没有交集")
            for _ in range(count):
                enemy_id = random.choice(tuple(sorted(candidates)))
                enemy = self.catalog.require(enemy_id)
                rank = self.catalog.ranks.require(spawn.rank_id)
                desired = spawn.behavior_count
                if desired is None:
                    desired = random.randint(rank.minimum_behaviors, rank.maximum_behaviors)
                behavior_ids, phase_loadouts = self._loadout(
                    enemy,
                    desired,
                    spawn.phase_health_ratios,
                    behavior_weights or {},
                    random,
                )
                sequence += 1
                enemies.append(
                    EnemyInstance(
                        f"{encounter_instance_id}:enemy:{sequence}",
                        enemy.id,
                        level,
                        rank.id,
                        behavior_ids,
                        f"{generation_seed}:enemy:{sequence}",
                        self.content_version,
                        phase_loadouts,
                    )
                )
        return EnemyEncounterInstance(
            encounter_instance_id,
            definition.id,
            definition.scope_id,
            level,
            tuple(enemies),
            generation_seed,
            self.content_version,
        )

    def generate_loadout(
        self,
        enemy_id: StableId,
        *,
        behavior_count: int,
        phase_health_ratios: tuple[float, ...],
        behavior_weights: Mapping[StableId, int],
        random: RandomSource,
    ) -> tuple[tuple[StableId, ...], tuple[EnemyPhaseLoadout, ...]]:
        enemy = self.catalog.require(enemy_id)
        return self._loadout(
            enemy,
            behavior_count,
            phase_health_ratios,
            behavior_weights,
            random,
        )

    def _loadout(
        self,
        enemy,
        desired: int,
        phase_health_ratios: tuple[float, ...],
        behavior_weights: Mapping[StableId, int],
        random: RandomSource,
    ) -> tuple[tuple[StableId, ...], tuple[EnemyPhaseLoadout, ...]]:
        total = desired + len(phase_health_ratios)
        selected = []
        candidates = list(sorted(self.catalog.behaviors.ids()))
        while len(selected) < total and candidates:
            candidate = self._weighted_choice(candidates, behavior_weights, random)
            selected.append(candidate)
            candidates = [
                value
                for value in candidates
                if value != candidate and self._compatible(value, selected)
            ]
        if len(selected) < total:
            raise ValueError(f"敌人 {enemy.id} 无法生成 {total} 个兼容行为")
        opening = tuple(selected[:desired])
        phases = tuple(
            EnemyPhaseLoadout(
                f"enemy.phase.generated.{enemy.id.removeprefix('enemy.')}.phase_{index + 1}",
                health_ratio,
                (selected[desired + index],),
            )
            for index, health_ratio in enumerate(phase_health_ratios)
        )
        return opening, phases

    @staticmethod
    def _weighted_choice(
        candidates: list[StableId],
        weights: Mapping[StableId, int],
        random: RandomSource,
    ) -> StableId:
        values = tuple((value, max(1, int(weights.get(value, 1)))) for value in candidates)
        sampled = random.randint(1, sum(weight for _, weight in values))
        cursor = 0
        for value, weight in values:
            cursor += weight
            if sampled <= cursor:
                return value
        raise AssertionError("敌人行为权重采样越界")

    def _compatible(self, candidate_id: str, selected_ids: list[str]) -> bool:
        candidate = self.catalog.behaviors.require(candidate_id)
        for selected_id in selected_ids:
            selected = self.catalog.behaviors.require(selected_id)
            if (
                selected_id in candidate.incompatible_behavior_ids
                or candidate_id in selected.incompatible_behavior_ids
            ):
                return False
        return True


__all__ = ["EnemyEncounterGenerator"]
