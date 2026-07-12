"""xiuxian4 游戏核心包。

根入口只标识核心整体版本。具体类型必须从 gameplay、account 或 persistence
所属领域导入，避免再次形成包含数百符号的公共命名空间。
"""

XIUXIAN_CORE_VERSION = "xiuxian-core.v1"

CORE_LAYERS = (
    "xiuxian_core.gameplay",
    "xiuxian_core.account",
    "xiuxian_core.persistence",
)

__all__ = ["CORE_LAYERS", "XIUXIAN_CORE_VERSION"]
