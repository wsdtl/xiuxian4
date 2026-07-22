"""游戏消息命令与小游戏 HTTP 接口总入口。

二级组件使用中文命名。当前 router 为空；小游戏提供真实 HTTP 路由时由本入口统一挂载。
"""

from __future__ import annotations

from importlib import import_module

from fastapi import APIRouter

from . import access_guard as access_guard  # noqa: F401


def _load_component_router(component_name: str) -> APIRouter:
    """动态加载中文二级组件，避免 Python 静态导包路径出现中文。"""

    module = import_module(f"{__name__}.{component_name}")
    component_router = getattr(module, "router", None)
    if not isinstance(component_router, APIRouter):
        raise TypeError(f"二级组件未暴露 APIRouter：{component_name}")
    return component_router

router = APIRouter()
router.include_router(_load_component_router("战报"))
router.include_router(_load_component_router("web"))

__all__ = ["router"]
