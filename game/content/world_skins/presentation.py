"""官方世界皮肤的武器装备展示样式注册表。"""

from game.core.gameplay import StableId, stable_id

from ..presentation import GearPresentationStyle
from .cultivation.presentation import (
    CULTIVATION_ENEMY_PRESENTATION,
    CULTIVATION_GEAR_PRESENTATION,
)
from .magic.presentation import MAGIC_ENEMY_PRESENTATION, MAGIC_GEAR_PRESENTATION
from .stellar_ring.presentation import (
    STELLAR_RING_ENEMY_PRESENTATION,
    STELLAR_RING_GEAR_PRESENTATION,
)


_GEAR_PRESENTATIONS = {
    (value.skin_id, value.skin_version): value
    for value in (
        CULTIVATION_GEAR_PRESENTATION,
        MAGIC_GEAR_PRESENTATION,
        STELLAR_RING_GEAR_PRESENTATION,
    )
}
_ENEMY_PRESENTATIONS = {
    (value.skin_id, value.skin_version): value
    for value in (
        CULTIVATION_ENEMY_PRESENTATION,
        MAGIC_ENEMY_PRESENTATION,
        STELLAR_RING_ENEMY_PRESENTATION,
    )
}


def gear_presentation_style(
    skin_id: StableId,
    version: int,
) -> GearPresentationStyle:
    key = stable_id(skin_id, field="skin id")
    try:
        return _GEAR_PRESENTATIONS[(key, int(version))]
    except KeyError as exc:
        raise KeyError(
            f"世界皮肤没有登记武器装备展示样式：{key}@{version}"
        ) from exc


def enemy_presentation_style(skin_id: StableId, version: int):
    key = stable_id(skin_id, field="skin id")
    try:
        return _ENEMY_PRESENTATIONS[(key, int(version))]
    except KeyError as exc:
        raise KeyError(f"世界皮肤没有登记敌人展示样式：{key}@{version}") from exc


__all__ = ["enemy_presentation_style", "gear_presentation_style"]
