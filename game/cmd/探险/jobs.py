"""探险组件的后台结算触发器。"""

from datetime import datetime
from zoneinfo import ZoneInfo

from game.app import current_game_services
from launch import C, Scheduler, config, logger


@Scheduler._sync(
    "interval",
    seconds=60,
    id="game_exploration_settlement",
    max_instances=1,
    coalesce=True,
)
def settle_running_explorations() -> None:
    """发现到期探险；具体批次由 ExplorationFeature 原子结算。"""

    try:
        current_game_services().exploration.settle_all_due(
            logical_time=datetime.now(ZoneInfo(config.project.timezone))
        )
    except Exception as exc:
        logger.opt(colors=True, exception=exc).error(C.fail("探险后台结算失败"))


__all__ = ["settle_running_explorations"]
