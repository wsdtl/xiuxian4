"""官方内容、真实世界运行目录与展示投影入口。"""

from __future__ import annotations

from dataclasses import dataclass

from game.core.gameplay import (
    ContentAssembler,
    ContentRuntime,
    SkinPack,
    SkinProjector,
    StableId,
    WorldDefinition,
    WorldRuntimeCatalog,
)

from .catalog import CATALOG_PACKAGE
from .worlds import PLAYABLE_WORLD_DEFINITIONS, WORLD_PACKAGE
from .catalog.companion import COMPANION_CATALOG, CompanionCatalog
from .catalog.disaster import build_dimensional_disaster_catalog
from .catalog.draw import DRAW_CATALOG_CONTENT
from .catalog.economy import audit_market_prices
from .catalog.enemy import (
    PARTY_BOSS_SOURCE_CATALOG,
    PERSONAL_BOSS_ENEMIES,
    PartyBossSourceCatalog,
)
from .catalog.exploration import EXPLORATION_REGION_CATALOG, ExplorationRegionCatalog
from .catalog.trial import BUILD_TRIAL_CATALOG, BuildTrialCatalog
from .catalog.world import PLAYABLE_WORLD_IDS, TAIXUAN_WORLD_ID
from .presentation import EnemyNameProjector, GearProjector
from .world_skins import (
    CULTIVATION_SKIN_ID,
    MAGIC_SKIN_ID,
    WORLD_SKIN_PACKAGE,
    enemy_presentation_style,
    gear_presentation_style,
)


OFFICIAL_PACKAGES = (CATALOG_PACKAGE, WORLD_SKIN_PACKAGE, WORLD_PACKAGE)
DEFAULT_SKIN_ID = CULTIVATION_SKIN_ID
DEFAULT_WORLD_ID = TAIXUAN_WORLD_ID


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
    build_trials: BuildTrialCatalog
    world: WorldDefinition
    worlds: WorldRuntimeCatalog


class WorldViewCatalog:
    """按真实世界提供运行规则，并由世界定义派生展示皮肤。"""

    def __init__(
        self,
        catalog: ContentRuntime,
        playable_worlds: tuple[WorldDefinition, ...] | None = None,
    ) -> None:
        self.catalog = catalog
        values = tuple(playable_worlds or PLAYABLE_WORLD_DEFINITIONS)
        for value in values:
            catalog.skins.require(value.skin_id)
        if catalog.world_runtime is None:
            raise ValueError("正式内容没有装配真实世界目录")
        if tuple(value.id for value in values) != catalog.world_runtime.world_ids():
            raise ValueError("应用声明的可进入世界与内容包装配结果不一致")
        self.worlds = catalog.world_runtime
        if self.worlds.world_ids() != PLAYABLE_WORLD_IDS:
            raise ValueError("正式世界定义顺序必须与可进入世界名录一致")
        self._views: dict[tuple[StableId, int], OfficialContent] = {}

    def require(
        self,
        world_id: StableId,
        version: int | None = None,
    ) -> OfficialContent:
        world = self.worlds.require_world(world_id)
        skin = self.catalog.skins.require(world.skin_id, version)
        key = (world.id, skin.version)
        view = self._views.get(key)
        if view is None:
            view = select_world_skin(
                self.catalog,
                skin.id,
                version=skin.version,
                world=world,
                worlds=self.worlds,
            )
            self._views[key] = view
        return view

    def require_skin(
        self,
        skin_id: StableId,
        version: int | None = None,
    ) -> OfficialContent:
        """只供历史战报和内容来源按展示皮肤还原，不参与玩法定位。"""

        world = self.worlds.world_for_skin(skin_id)
        return self.require(world.id, version)

    def resolve(self, value: object) -> OfficialContent | None:
        """按 world_id、skin_id 或玩家可见世界名解析真实世界视图。"""

        token = " ".join(str(value or "").strip().casefold().split())
        if not token:
            return None
        for world_id in self.world_ids():
            view = self.require(world_id)
            if token in {
                view.world.id.casefold(),
                view.skin.id.casefold(),
                view.skin.name.casefold(),
            }:
                return view
        return None

    def world_ids(self) -> tuple[StableId, ...]:
        return self.worlds.world_ids()

    def skin_ids(self) -> tuple[StableId, ...]:
        return self.worlds.skin_ids()

    def registered_skin_ids(self) -> tuple[StableId, ...]:
        return self.catalog.skins.skin_ids()

    def latest_views(self) -> tuple[OfficialContent, ...]:
        return tuple(self.require(world_id) for world_id in self.world_ids())


def assemble_official_catalog() -> ContentRuntime:
    """装配全部官方内容；应用组合根应在启动时只调用一次。"""

    runtime = ContentAssembler().assemble(OFFICIAL_PACKAGES)
    audit_market_prices(runtime.items, DRAW_CATALOG_CONTENT)
    return runtime


def select_world_skin(
    catalog: ContentRuntime,
    skin_id: StableId = DEFAULT_SKIN_ID,
    *,
    version: int | None = None,
    world: WorldDefinition | None = None,
    worlds: WorldRuntimeCatalog | None = None,
) -> OfficialContent:
    """在不改变规则和存档的前提下选择一套世界皮肤。"""

    skin = catalog.skins.require(skin_id, version)
    runtime = worlds or catalog.world_runtime
    if runtime is None:
        raise ValueError("正式内容没有装配真实世界目录")
    selected_world = world or runtime.world_for_skin(skin.id)
    projector = SkinProjector(skin)
    EXPLORATION_REGION_CATALOG.validate(catalog, runtime)
    COMPANION_CATALOG.validate(catalog, runtime)
    PARTY_BOSS_SOURCE_CATALOG.validate(catalog, runtime.world_ids())
    validate_enemy_narrative_identities(projector, selected_world.id, skin.id)
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
        BUILD_TRIAL_CATALOG,
        selected_world,
        runtime,
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
    world_id: StableId,
    skin_id: StableId,
) -> None:
    """防止同一世界来源的个人、组队和灾厄重复使用中文主身份。"""

    identities: dict[str, str] = {}
    enemy_ids = (
        *(value.id for value in PERSONAL_BOSS_ENEMIES),
        *sorted(PARTY_BOSS_SOURCE_CATALOG.require(world_id).enemy_ids),
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
    disasters = build_dimensional_disaster_catalog().for_source(world_id)
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
        PLAYABLE_WORLD_DEFINITIONS,
    )


__all__ = [
    "DEFAULT_SKIN_ID",
    "DEFAULT_WORLD_ID",
    "OFFICIAL_PACKAGES",
    "OfficialContent",
    "PLAYABLE_WORLD_DEFINITIONS",
    "WorldViewCatalog",
    "assemble_official_catalog",
    "build_official_content",
    "build_world_view_catalog",
    "select_world_skin",
    "validate_enemy_narrative_identities",
]
