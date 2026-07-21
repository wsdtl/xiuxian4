"""跨界灾厄组件的周期维护触发器。"""

from datetime import datetime
from zoneinfo import ZoneInfo

from game.app import current_game_services
from launch import C, Scheduler, config, logger


@Scheduler._sync(
    "interval",
    seconds=60,
    id="game_dimensional_disaster_maintenance",
    max_instances=1,
    coalesce=True,
)
def maintain_dimensional_disasters() -> None:
    """触发灾厄开放、封榜和奖励重试。"""

    try:
        current_game_services().dimensional_disasters.maintain(
            logical_time=datetime.now(ZoneInfo(config.project.timezone))
        )
    except Exception as exc:
        logger.opt(colors=True, exception=exc).error(C.fail("跨界灾厄维护失败"))


__all__ = ["maintain_dimensional_disasters"]
