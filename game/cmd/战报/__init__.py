"""公开战报 HTTP 组件与保留期任务入口。"""

from . import jobs as jobs  # noqa: F401
from .site import router

__all__ = ["router"]
