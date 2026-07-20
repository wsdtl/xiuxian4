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
from .catalog.companion import COMPANION_CATALOG, CompanionCatalog
from .catalog.disaster import build_dimensional_disaster_catalog
from .catalog.enemy import (
    PARTY_BOSS_SOURCE_CATALOG,
    PERSONAL_BOSS_ENEMIES,
    PartyBossSourceCatalog,
)
from .catalog.exploration import EXPLORATION_REGION_CATALOG, ExplorationRegionCatalog
from .presentation import EnemyNameProjector, GearProjector
from .world_skins import (
    CULTIVATION_SKIN_ID,
    PLAYABLE_WORLD_SKIN_IDS,
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
    exploration_regions: ExplorationRegionCatalog
    companions: CompanionCatalog
    party_bosses: PartyBossSourceCatalog


class WorldViewCatalog:
    """复用同一规则目录，按世界皮肤缓存完整玩家展示投影。"""

    def __init__(
        self,
        catalog: ContentRuntime,
        playable_skin_ids: tuple[StableId, ...] | None = None,
    ) -> None:
        self.catalog = catalog
        values = tuple(playable_skin_ids or catalog.skins.skin_ids())
        normalized = tuple(catalog.skins.require(value).id for value in values)
        if not normalized or len(normalized) != len(set(normalized)):
            raise ValueError("可进入世界皮肤必须存在且不能重复")
        self._playable_skin_ids = normalized
        self._views: dict[tuple[StableId, int], OfficialContent] = {}

    def require(
        self,
        skin_id: StableId,
        version: int | None = None,
    ) -> OfficialContent:
        skin = self.catalog.skins.require(skin_id, version)
        key = (skin.id, skin.version)
        view = self._views.get(key)
        if view is None:
            view = select_world_skin(self.catalog, skin.id, version=skin.version)
            self._views[key] = view
        return view

    def resolve(self, value: object) -> OfficialContent | None:
        """按稳定 ID 或玩家可见世界名解析最新世界皮肤。"""

        token = " ".join(str(value or "").strip().casefold().split())
        if not token:
            return None
        for skin_id in self.skin_ids():
            view = self.require(skin_id)
            if token in {view.skin.id.casefold(), view.skin.name.casefold()}:
                return view
        return None

    def skin_ids(self) -> tuple[StableId, ...]:
        return self._playable_skin_ids

    def registered_skin_ids(self) -> tuple[StableId, ...]:
        return self.catalog.skins.skin_ids()

    def latest_views(self) -> tuple[OfficialContent, ...]:
        return tuple(self.require(skin_id) for skin_id in self.skin_ids())


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
    EXPLORATION_REGION_CATALOG.validate(catalog)
    COMPANION_CATALOG.validate(catalog, PLAYABLE_WORLD_SKIN_IDS)
    PARTY_BOSS_SOURCE_CATALOG.validate(catalog, PLAYABLE_WORLD_SKIN_IDS)
    validate_enemy_narrative_identities(projector, skin.id)
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
        EXPLORATION_REGION_CATALOG,
        COMPANION_CATALOG,
        PARTY_BOSS_SOURCE_CATALOG,
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


def validate_enemy_narrative_identities(
    projector: SkinProjector,
    skin_id: StableId,
) -> None:
    """防止同一世界来源的个人、组队和灾厄重复使用中文主身份。"""

    identities: dict[str, str] = {}
    enemy_ids = (
        *(value.id for value in PERSONAL_BOSS_ENEMIES),
        *sorted(PARTY_BOSS_SOURCE_CATALOG.require(skin_id).enemy_ids),
    )
    for enemy_id in enemy_ids:
        name = projector.name(enemy_id)
        token = _narrative_identity(name)
        previous = identities.get(token)
        if previous is not None:
            raise ValueError(
                f"世界皮肤的个人与组队首领中文身份重复：{previous} / {name}"
            )
        identities[token] = name
    disasters = build_dimensional_disaster_catalog().for_source(skin_id)
    collisions = tuple(
        (identities[token], disaster.name)
        for disaster in disasters
        for token in (_narrative_identity(disaster.name),)
        if token in identities
    )
    if collisions:
        details = ", ".join(f"{left} / {right}" for left, right in collisions)
        raise ValueError(f"世界皮肤的首领与灾厄中文身份重复：{details}")


def _narrative_identity(name: str) -> str:
    return str(name or "").split("·", 1)[0].strip()


def build_world_view_catalog() -> WorldViewCatalog:
    """装配一次正式规则目录，并为角色级世界投影提供缓存入口。"""

    return WorldViewCatalog(
        assemble_official_catalog(),
        PLAYABLE_WORLD_SKIN_IDS,
    )


__all__ = [
    "DEFAULT_SKIN_ID",
    "OFFICIAL_PACKAGES",
    "OfficialContent",
    "WorldViewCatalog",
    "assemble_official_catalog",
    "build_official_content",
    "build_world_view_catalog",
    "select_world_skin",
    "validate_enemy_narrative_identities",
]
