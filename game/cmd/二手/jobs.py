"""二手组件的到期挂单处理触发器。"""

from datetime import datetime
from zoneinfo import ZoneInfo

from game.app import current_game_services
from launch import C, Scheduler, config, logger


@Scheduler._sync(
    "interval",
    seconds=60,
    id="game_market_expiration",
    max_instances=1,
    coalesce=True,
)
def expire_market_listings() -> None:
    """释放到期挂单及其库存预约。"""

    try:
        current_game_services().economy.expire_due(
            logical_time=datetime.now(ZoneInfo(config.project.timezone))
        )
    except Exception as exc:
        logger.opt(colors=True, exception=exc).error(C.fail("二手挂单到期处理失败"))


__all__ = ["expire_market_listings"]
