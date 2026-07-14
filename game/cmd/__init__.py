"""游戏消息命令与小游戏 HTTP 接口总入口。

二级组件使用中文命名。当前 router 为空；小游戏提供真实 HTTP 路由时由本入口统一挂载。
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()

__all__ = ["router"]
