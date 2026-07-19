"""二手市场与税务查询二级组件命令。"""

from __future__ import annotations

from launch.adapter import Depends

from ..command import GameCommand
from ..dependencies import current_character_overview
from . import jobs as jobs  # noqa: F401
from . import service


@GameCommand.handler(cmd="二手")
async def market(message: str = "", overview=Depends(current_character_overview)) -> None:
    await service.market(message, overview)


@GameCommand.handler(cmd="上架")
async def list_item(message: str = "", overview=Depends(current_character_overview)) -> None:
    await service.list_item(message, overview)


@GameCommand.handler(cmd="下架")
async def cancel_listing(message: str = "", overview=Depends(current_character_overview)) -> None:
    await service.cancel_listing(message, overview)


@GameCommand.handler(cmd="购买")
async def buy(message: str = "", overview=Depends(current_character_overview)) -> None:
    await service.buy(message, overview)


@GameCommand.handler(cmd="我的上架")
async def my_listings(message: str = "", overview=Depends(current_character_overview)) -> None:
    await service.my_listings(message, overview)


@GameCommand.handler(cmd="税务")
async def tax(overview=Depends(current_character_overview)) -> None:
    await service.tax(overview)


@GameCommand.handler(cmd="economy_market_list_confirm")
async def confirm_listing(message: str = "", overview=Depends(current_character_overview)) -> None:
    await service.confirm_listing(message, overview)


@GameCommand.handler(cmd="economy_market_buy_confirm")
async def confirm_purchase(message: str = "", overview=Depends(current_character_overview)) -> None:
    await service.confirm_purchase(message, overview)


__all__ = []
