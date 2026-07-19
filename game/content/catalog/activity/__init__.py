"""全服活动展示策略的稳定入口。"""

from .policy import (
    GLOBAL_ACTIVITY_CLOSING_WINDOW,
    GLOBAL_ACTIVITY_OPENING_WINDOW,
    GLOBAL_ACTIVITY_SPOTLIGHT_LIMIT,
)


__all__ = [name for name in globals() if not name.startswith("_")]
