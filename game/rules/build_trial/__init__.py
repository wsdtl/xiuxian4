"""构筑试炼纯规则入口。"""

from .battle import BuildTrialBattleSimulator
from .metrics import summarize_build_trial
from .models import BuildTrialBattleOutcome, BuildTrialMetrics

__all__ = [
    "BuildTrialBattleOutcome",
    "BuildTrialBattleSimulator",
    "BuildTrialMetrics",
    "summarize_build_trial",
]
