"""休息组件的后台完成触发器。"""

from datetime import datetime
from zoneinfo import ZoneInfo

from game.app import current_game_services
from launch import C, Scheduler, config, logger


@Scheduler._sync(
    "interval",
    seconds=60,
    id="game_rest_settlement",
    max_instances=1,
    coalesce=True,
)
def settle_completed_rest() -> None:
    """完成达到结算时间的休息；恢复规则仍归 RestFeature。"""

    try:
        current_game_services().rest.settle_all_due(
            logical_time=datetime.now(ZoneInfo(config.project.timezone))
        )
    except Exception as exc:
        logger.opt(colors=True, exception=exc).error(C.fail("休息后台结算失败"))


__all__ = ["settle_completed_rest"]
