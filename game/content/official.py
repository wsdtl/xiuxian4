"""官方内容统一装配与世界皮肤选择入口。"""

from __future__ import annotations

from dataclasses import dataclass

from game.core.gameplay import (
    ContentAssembler,
    ContentRuntime,
    SkinPack,
    SkinProjector,
    StableId,
)

from .catalog import CATALOG_PACKAGE
from .presentation import EnemyNameProjector, GearProjector
from .world_skins import (
    CULTIVATION_SKIN_ID,
    WORLD_SKIN_PACKAGE,
    enemy_presentation_style,
    gear_presentation_style,
)


OFFICIAL_PACKAGES = (CATALOG_PACKAGE, WORLD_SKIN_PACKAGE)
DEFAULT_SKIN_ID = CULTIVATION_SKIN_ID


@dataclass(frozen=True)
class OfficialContent:
    """已经冻结的官方规则运行期及当前展示皮肤。"""

    catalog: ContentRuntime
    skin: SkinPack
    projector: SkinProjector
    gear_projector: GearProjector
    enemy_projector: EnemyNameProjector


def assemble_official_catalog() -> ContentRuntime:
    """装配全部官方内容；应用组合根应在启动时只调用一次。"""

    return ContentAssembler().assemble(OFFICIAL_PACKAGES)


def select_world_skin(
    catalog: ContentRuntime,
    skin_id: StableId = DEFAULT_SKIN_ID,
    *,
    version: int | None = None,
) -> OfficialContent:
    """在不改变规则和存档的前提下选择一套世界皮肤。"""

    skin = catalog.skins.require(skin_id, version)
    projector = SkinProjector(skin)
    return OfficialContent(
        catalog,
        skin,
        projector,
        GearProjector(
            projector,
            gear_presentation_style(skin.id, skin.version),
        ),
        EnemyNameProjector(
            projector,
            enemy_presentation_style(skin.id, skin.version),
        ),
    )


def build_official_content(
    skin_id: StableId = DEFAULT_SKIN_ID,
    *,
    version: int | None = None,
) -> OfficialContent:
    """用于启动装配和测试的便捷入口，正式组件不得自行调用。"""

    return select_world_skin(
        assemble_official_catalog(),
        skin_id,
        version=version,
    )


__all__ = [
    "DEFAULT_SKIN_ID",
    "OFFICIAL_PACKAGES",
    "OfficialContent",
    "assemble_official_catalog",
    "build_official_content",
    "select_world_skin",
]
