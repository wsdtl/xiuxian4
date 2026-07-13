"""规则内核使用的稳定标识。

稳定标识只服务于代码、配置和存储，不直接展示给玩家。世界皮肤可以修改
名称、描述和图标，但不能修改这些标识。
"""

from __future__ import annotations

import re
from typing import TypeAlias


StableId: TypeAlias = str

_STABLE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")


def stable_id(value: object, *, field: str = "id") -> StableId:
    """校验并返回稳定标识。

    标识至少包含两段，例如 ``effect.recover_health``。要求使用英文小写，
    是为了让换皮名称永远不会反向成为业务键。
    """

    text = str(value or "").strip()
    if not _STABLE_ID_PATTERN.fullmatch(text):
        raise ValueError(
            f"{field} 必须是至少两段的英文小写稳定标识，例如 effect.recover_health，当前值：{text!r}"
        )
    return text


__all__ = ["StableId", "stable_id"]
