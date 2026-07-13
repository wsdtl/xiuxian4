"""协议和具体玩法无关的公共游戏核心包。

根入口只标识核心整体版本。具体类型必须从 gameplay、account 或 persistence
所属领域导入，避免再次形成包含数百符号的公共命名空间。
"""

GAME_CORE_VERSION = "game-core.v1"

CORE_LAYERS = (
    "game.core.gameplay",
    "game.core.account",
    "game.core.persistence",
)

__all__ = ["CORE_LAYERS", "GAME_CORE_VERSION"]
