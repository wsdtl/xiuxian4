"""构筑试炼业务结果与存储边界。"""

from __future__ import annotations

from dataclasses import dataclass

from game.rules.battle_report import BattleReportReference
from game.rules.build_trial import BuildTrialBattleOutcome


@dataclass(frozen=True)
class BuildTrialStorageKinds:
    character: str
    character_world: str
    inventory: str
    loadout: str
    companion_roster: str
    inscription_preference: str


@dataclass(frozen=True)
class BuildTrialResult:
    status: str
    mode: object
    report: BattleReportReference | None = None
    outcome: BuildTrialBattleOutcome | None = None


__all__ = ["BuildTrialResult", "BuildTrialStorageKinds"]
