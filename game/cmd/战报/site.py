"""公开战报页面与版本化 JSON 协议入口。"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from game.app import current_game_services
from game.content.presentation import GAME_NAME
from game.features.battle_report import build_public_battle_report
from launch import config
from launch.paths import static_path


router = APIRouter()
_REPORT_PAGE = static_path("battle-report", "index.html")
_PUBLIC_HEADERS = {
    "Cache-Control": "public, max-age=60",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


@router.get("/battle/{share_id}", response_class=FileResponse)
def public_battle_report(share_id: str) -> FileResponse:
    """保留公开分享地址；浏览器从同路径的 data 端点读取战报。"""

    _load_public_report(share_id)
    return FileResponse(
        _REPORT_PAGE,
        media_type="text/html",
        headers=_PUBLIC_HEADERS,
    )


@router.get("/battle/{share_id}/data", response_class=JSONResponse)
def public_battle_report_data(share_id: str) -> JSONResponse:
    """返回与具体网页实现无关的版本化公共战报文档。"""

    report, services = _load_public_report(share_id)
    document = build_public_battle_report(report)
    document["game_name"] = GAME_NAME
    return JSONResponse(document, headers=_PUBLIC_HEADERS)


def _load_public_report(share_id: str):
    services = current_game_services()
    report = services.battle_reports.load_public(
        share_id,
        logical_time=datetime.now(ZoneInfo(config.project.timezone)),
    )
    if report is None:
        raise HTTPException(status_code=404, detail="战报不存在或已经过期")
    return report, services


__all__ = ["public_battle_report", "public_battle_report_data", "router"]
