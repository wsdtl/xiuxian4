"""归航公约拥有且不随世界同化的公共展示。"""

from game.core.gameplay import SkinEntry

from .catalog.item.exchange import EXCHANGE_MATERIAL_ITEM_ID


COVENANT_ITEM_ENTRIES = {
    EXCHANGE_MATERIAL_ITEM_ID: SkinEntry(
        name="定相尘",
        description="归航公约注销组队首领遗物后留下的稳定兑换材料。",
        icon="◆",
    ),
}


__all__ = ["COVENANT_ITEM_ENTRIES"]
