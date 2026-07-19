"""彩票组件的后台开奖触发器。"""

from datetime import datetime
from zoneinfo import ZoneInfo

from game.app import current_game_services
from launch import C, Scheduler, config, logger


@Scheduler._sync(
    "interval",
    seconds=60,
    id="game_lottery_draw",
    max_instances=1,
    coalesce=True,
)
def draw_due_lottery_rounds() -> None:
    """触发所有到期开奖；开奖规则和账本事务仍归 LotteryFeature。"""

    try:
        current_game_services().lottery.draw_due(
            logical_time=datetime.now(ZoneInfo(config.project.timezone))
        )
    except Exception as exc:
        logger.opt(colors=True, exception=exc).error(C.fail("彩票后台开奖失败"))


__all__ = ["draw_due_lottery_rounds"]
