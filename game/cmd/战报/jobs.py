"""战报组件的保留期清理触发器。"""

from datetime import datetime
from zoneinfo import ZoneInfo

from game.app import current_game_services
from launch import C, Scheduler, config, logger


@Scheduler._sync(
    "interval",
    hours=24,
    id="game_battle_report_cleanup",
    max_instances=1,
    coalesce=True,
)
def cleanup_battle_reports() -> None:
    """七天删除明细，三十天删除摘要。"""

    try:
        current_game_services().battle_reports.cleanup(
            logical_time=datetime.now(ZoneInfo(config.project.timezone))
        )
    except Exception as exc:
        logger.opt(colors=True, exception=exc).error(C.fail("战报保留期清理失败"))


__all__ = ["cleanup_battle_reports"]
