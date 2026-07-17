"""与具体世界皮肤和玩法组件无关的战斗伤害底座。"""

COMBAT_FOUNDATION_VERSION = "combat.foundation.v4"

from .engine import DamageEngine
from .control import (
    ApplyControl,
    ControlDefinition,
    ControlEngine,
    ControlResolution,
    ControlStats,
    register_control_operation,
)
from .interceptors import (
    DamageInterceptorDefinition,
    DamageInterceptorRegistry,
    InterceptorHandler,
)
from .integration import DealDamage, register_damage_operation
from .models import (
    CombatStats,
    DamageBreakdown,
    DamageFrame,
    DamageInterceptionRecord,
    DamageRequest,
    DamageRedirect,
    DamageResolution,
    DamageRules,
    DamageStage,
    DamageTypeDefinition,
    InterceptorSide,
)
from .targeting import (
    TargetConstraintDefinition,
    TargetConstraintKind,
    TargetConstraintRegistry,
    TargetRequest,
    TargetSelector,
    TargetSelectorRegistry,
    TargetingContext,
)
from .recovery import (
    GrantShield,
    Heal,
    HealingResolution,
    RecoveryEngine,
    RecoveryStats,
    register_recovery_operations,
)
from .timeline import (
    BattleAction,
    BattleAbilityTargeting,
    BattleEngine,
    BattleParticipant,
    BattleRules,
    BattleState,
    BattleStatus,
    BattleStepResult,
)
from .timeline_operations import (
    RequestExtraTurn,
    RequestInterrupt,
    RequestTurnDelay,
    register_timeline_operations,
)

__all__ = [
    "COMBAT_FOUNDATION_VERSION",
    "CombatStats",
    "ApplyControl",
    "BattleAction",
    "BattleAbilityTargeting",
    "BattleEngine",
    "BattleParticipant",
    "BattleRules",
    "BattleState",
    "BattleStatus",
    "BattleStepResult",
    "ControlDefinition",
    "ControlEngine",
    "ControlResolution",
    "ControlStats",
    "DamageBreakdown",
    "DamageFrame",
    "DamageInterceptionRecord",
    "DamageInterceptorDefinition",
    "DamageInterceptorRegistry",
    "DamageEngine",
    "DamageRequest",
    "DamageRedirect",
    "DamageResolution",
    "DamageRules",
    "DamageStage",
    "DamageTypeDefinition",
    "DealDamage",
    "GrantShield",
    "Heal",
    "HealingResolution",
    "InterceptorHandler",
    "InterceptorSide",
    "RecoveryEngine",
    "RecoveryStats",
    "RequestExtraTurn",
    "RequestInterrupt",
    "RequestTurnDelay",
    "TargetRequest",
    "TargetConstraintDefinition",
    "TargetConstraintKind",
    "TargetConstraintRegistry",
    "TargetSelector",
    "TargetSelectorRegistry",
    "TargetingContext",
    "register_damage_operation",
    "register_control_operation",
    "register_recovery_operations",
    "register_timeline_operations",
]
