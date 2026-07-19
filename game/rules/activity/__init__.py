"""全服活动注册与热点展示规则。"""

from .models import (
    ActivitySpotlightPolicy,
    GLOBAL_ACTIVITY_SCOPE_ID,
    GlobalActivityRegistration,
    GlobalActivityPresentation,
    GlobalActivitySelection,
    GlobalActivityView,
)
from .registry import (
    GlobalActivityCatalog,
    global_activity_catalog,
    register_global_activity,
    resolve_global_activity_presentation,
)


__all__ = [
    "ActivitySpotlightPolicy",
    "GLOBAL_ACTIVITY_SCOPE_ID",
    "GlobalActivityCatalog",
    "GlobalActivityRegistration",
    "GlobalActivityPresentation",
    "GlobalActivitySelection",
    "GlobalActivityView",
    "global_activity_catalog",
    "register_global_activity",
    "resolve_global_activity_presentation",
]
