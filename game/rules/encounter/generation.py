"""正式遭遇与敌人实例的确定性生成规则。"""

from game.core.gameplay import EnemyCatalog, EnemyEncounterInstance, EnemyInstance, RandomSource


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
                desired = max(desired, len(enemy.default_behavior_ids))
                behavior_ids = self._behaviors(enemy, desired, random)
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

    def _behaviors(self, enemy, desired: int, random: RandomSource) -> tuple[str, ...]:
        selected = list(sorted(enemy.default_behavior_ids))
        candidates = [
            value
            for value in sorted(enemy.available_behavior_ids)
            if value not in selected and self._compatible(value, selected)
        ]
        while len(selected) < desired and candidates:
            candidate = random.choice(tuple(candidates))
            selected.append(candidate)
            candidates = [
                value
                for value in candidates
                if value != candidate and self._compatible(value, selected)
            ]
        if len(selected) < desired:
            raise ValueError(f"敌人 {enemy.id} 无法生成 {desired} 个兼容行为")
        return tuple(selected)

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
