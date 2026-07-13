"""游戏命令与 HTTP 接口总路由。

二级组件使用中文命名。规则、状态和持久化实现不得写入本包。
"""

from __future__ import annotations

from fastapi import APIRouter

from .后台接口 import router as backend_router


router = APIRouter()
router.include_router(backend_router)

__all__ = ["router"]
