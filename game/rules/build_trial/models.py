"""构筑试炼的战斗结果与可比较摘要指标。"""

from __future__ import annotations

from dataclasses import dataclass

from game.core.gameplay import BattleTrace


@dataclass(frozen=True)
class BuildTrialMetrics:
    player_actions: int
    total_damage: float
    damage_taken: float
    healing: float
    shield: float
    critical_hits: int
    trigger_activations: int
    enemies_defeated: int
    health_after: float
    health_maximum: float
    spirit_after: float
    spirit_maximum: float


@dataclass(frozen=True)
class BuildTrialBattleOutcome:
    completed: bool
    victory: bool
    draw: bool
    turns: int
    trace: BattleTrace
    metrics: BuildTrialMetrics
    player_entity_ids: tuple[str, ...]
    enemy_entity_ids: tuple[str, ...]
    companion_id: str | None = None


__all__ = ["BuildTrialBattleOutcome", "BuildTrialMetrics"]
