"""版本化内容包、依赖解析和统一运行期组装。"""

from .assembler import (
    CONTENT_FOUNDATION_VERSION,
    ContentAssembler,
    ContentAssemblyReport,
    ContentOwner,
    ContentRuntime,
    SelectedPackage,
    resolve_package_order,
)
from .models import (
    CombatProfileDefinition,
    ConditionRegistration,
    ContentPackage,
    ContentPackageManifest,
    ContentVersion,
    EffectOperationRegistration,
    InterceptorHandlerRegistration,
    MagnitudeRegistration,
    PackageRequirement,
    TargetSelectorRegistration,
)

__all__ = [
    "CONTENT_FOUNDATION_VERSION",
    "CombatProfileDefinition",
    "ConditionRegistration",
    "ContentAssembler",
    "ContentAssemblyReport",
    "ContentOwner",
    "ContentPackage",
    "ContentPackageManifest",
    "ContentRuntime",
    "ContentVersion",
    "EffectOperationRegistration",
    "InterceptorHandlerRegistration",
    "MagnitudeRegistration",
    "PackageRequirement",
    "SelectedPackage",
    "TargetSelectorRegistration",
    "resolve_package_order",
]
