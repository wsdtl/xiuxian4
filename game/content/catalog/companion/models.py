"""伙伴物种、世界秘境与正式平衡参数。"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from game.core.gameplay import CORE_ATTRIBUTE_IDS, DefinitionRegistry, StableId, stable_id


COMPANION_ROLES = frozenset({"assault", "swift", "guardian", "control", "sustain"})
COMPANION_KIND_PET = "pet"
COMPANION_KIND_PERSON = "person"


@dataclass(frozen=True)
class CompanionSpeciesDefinition:
    """一个来源世界固定、不会随跃迁改名的伙伴物种。"""

    id: StableId
    origin_world_id: StableId
    name: str
    description: str
    role: str
    attribute_multipliers: Mapping[StableId, float]
    core_behavior_id: StableId
    trait_behavior_ids: tuple[StableId, ...]
    capture_weight: int = 100

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="companion species id"))
        object.__setattr__(
            self,
            "origin_world_id",
            stable_id(self.origin_world_id, field="companion origin world id"),
        )
        name = " ".join(str(self.name or "").split())
        description = " ".join(str(self.description or "").split())
        role = str(self.role or "").strip().lower()
        if not name or not description:
            raise ValueError("伙伴物种必须提供名称和描述")
        if role not in COMPANION_ROLES:
            raise ValueError(f"未知伙伴定位: {self.role}")
        multipliers = {
            stable_id(key, field="companion attribute id"): float(value)
            for key, value in self.attribute_multipliers.items()
        }
        if set(multipliers) != set(CORE_ATTRIBUTE_IDS):
            raise ValueError(f"伙伴物种 {self.id} 必须完整声明五项基础属性倍率")
        if any(value <= 0 for value in multipliers.values()):
            raise ValueError(f"伙伴物种 {self.id} 的基础属性倍率必须大于零")
        core_behavior_id = stable_id(
            self.core_behavior_id,
            field="companion core behavior id",
        )
        traits = tuple(
            stable_id(value, field="companion trait behavior id")
            for value in self.trait_behavior_ids
        )
        if not traits or len(traits) != len(set(traits)):
            raise ValueError(f"伙伴物种 {self.id} 必须声明不重复的随机特性池")
        if core_behavior_id in traits:
            raise ValueError(f"伙伴物种 {self.id} 的核心行为不能重复进入特性池")
        if self.capture_weight < 1:
            raise ValueError("伙伴物种捕获权重必须大于零")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "attribute_multipliers", MappingProxyType(multipliers))
        object.__setattr__(self, "core_behavior_id", core_behavior_id)
        object.__setattr__(self, "trait_behavior_ids", traits)


@dataclass(frozen=True)
class PersonCompanionDefinition:
    """固定驻留在一个专用地点、通过关系结交的人形伙伴。"""

    id: StableId
    origin_world_id: StableId
    location_id: StableId
    name: str
    description: str
    role: str
    attribute_multipliers: Mapping[StableId, float]
    core_behavior_id: StableId
    trait_behavior_id: StableId
    quality_id: StableId
    aptitudes: Mapping[StableId, int]
    gift_values: Mapping[StableId, int]
    bond_required: int = 100

    def __post_init__(self) -> None:
        for field_name in ("id", "origin_world_id", "location_id", "quality_id"):
            object.__setattr__(
                self,
                field_name,
                stable_id(getattr(self, field_name), field=f"person companion {field_name}"),
            )
        name = " ".join(str(self.name or "").split())
        description = " ".join(str(self.description or "").split())
        role = str(self.role or "").strip().lower()
        if not name or not description:
            raise ValueError("人物伙伴必须提供名称和描述")
        if role not in COMPANION_ROLES:
            raise ValueError(f"未知人物伙伴定位: {self.role}")
        multipliers = {
            stable_id(key, field="person companion attribute id"): float(value)
            for key, value in self.attribute_multipliers.items()
        }
        if set(multipliers) != set(CORE_ATTRIBUTE_IDS) or any(
            value <= 0 for value in multipliers.values()
        ):
            raise ValueError("人物伙伴必须完整声明五项正数属性倍率")
        aptitudes = {
            stable_id(key, field="person companion aptitude id"): int(value)
            for key, value in self.aptitudes.items()
        }
        if len(aptitudes) != 4 or any(value < 60 or value > 140 for value in aptitudes.values()):
            raise ValueError("人物伙伴必须声明四项 60 至 140 的固定资质")
        gift_values = {
            stable_id(key, field="person companion gift item id"): int(value)
            for key, value in self.gift_values.items()
        }
        if not gift_values or any(value < 1 for value in gift_values.values()):
            raise ValueError("人物伙伴至少需要一种正数关系值礼物")
        if self.bond_required < 1:
            raise ValueError("人物伙伴结交门槛必须大于零")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "attribute_multipliers", MappingProxyType(multipliers))
        object.__setattr__(
            self,
            "core_behavior_id",
            stable_id(self.core_behavior_id, field="person companion core behavior id"),
        )
        object.__setattr__(
            self,
            "trait_behavior_id",
            stable_id(self.trait_behavior_id, field="person companion trait behavior id"),
        )
        object.__setattr__(self, "aptitudes", MappingProxyType(aptitudes))
        object.__setattr__(self, "gift_values", MappingProxyType(gift_values))


@dataclass(frozen=True)
class CompanionSanctuaryDefinition:
    """一个世界独立提供的宠物秘境入口和生态池。"""

    id: StableId
    world_id: StableId
    name: str
    description: str
    species_ids: tuple[StableId, ...]
    duration_seconds: int = 86_400
    trace_count: int = 3

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="companion sanctuary id"))
        object.__setattr__(
            self,
            "world_id",
            stable_id(self.world_id, field="companion sanctuary world id"),
        )
        name = " ".join(str(self.name or "").split())
        description = " ".join(str(self.description or "").split())
        species_ids = tuple(
            stable_id(value, field="companion sanctuary species id")
            for value in self.species_ids
        )
        if not name or not description:
            raise ValueError("宠物秘境必须提供名称和描述")
        if len(species_ids) < self.trace_count or len(species_ids) != len(set(species_ids)):
            raise ValueError("宠物秘境物种数量必须覆盖全部不重复踪迹")
        if self.duration_seconds < 60:
            raise ValueError("宠物秘境持续时间不能少于一分钟")
        if self.trace_count < 1:
            raise ValueError("宠物秘境踪迹数量必须大于零")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "species_ids", species_ids)


@dataclass(frozen=True)
class CompanionBalance:
    """可审计的伙伴容量、品质和资质预算。"""

    roster_capacity: int
    quality_weights: Mapping[StableId, int] = field(default_factory=dict)
    aptitude_budgets: Mapping[StableId, int] = field(default_factory=dict)
    maximum_level: int = 100

    def __post_init__(self) -> None:
        if self.roster_capacity < 1 or self.maximum_level < 1:
            raise ValueError("伙伴容量和最高等级必须大于零")
        quality_weights = {
            stable_id(key, field="companion quality id"): int(value)
            for key, value in self.quality_weights.items()
        }
        aptitude_budgets = {
            stable_id(key, field="companion quality id"): int(value)
            for key, value in self.aptitude_budgets.items()
        }
        if not quality_weights or set(quality_weights) != set(aptitude_budgets):
            raise ValueError("伙伴品质权重和资质预算必须完整对应")
        if any(value < 1 for value in quality_weights.values()):
            raise ValueError("伙伴品质权重必须大于零")
        if any(value < 240 for value in aptitude_budgets.values()):
            raise ValueError("伙伴四项资质总预算不能低于 240")
        object.__setattr__(self, "quality_weights", MappingProxyType(quality_weights))
        object.__setattr__(self, "aptitude_budgets", MappingProxyType(aptitude_budgets))


class CompanionCatalog:
    """伙伴物种和世界秘境的冻结目录。"""

    def __init__(
        self,
        species: tuple[CompanionSpeciesDefinition, ...],
        sanctuaries: tuple[CompanionSanctuaryDefinition, ...],
        balance: CompanionBalance,
        people: tuple[PersonCompanionDefinition, ...] = (),
    ) -> None:
        self.species = DefinitionRegistry[CompanionSpeciesDefinition]("CompanionSpecies")
        self.sanctuaries = DefinitionRegistry[CompanionSanctuaryDefinition](
            "CompanionSanctuary"
        )
        self.people = DefinitionRegistry[PersonCompanionDefinition]("PersonCompanion")
        for definition in species:
            self.species.register(definition)
        for definition in sanctuaries:
            self.sanctuaries.register(definition)
        for definition in people:
            self.people.register(definition)
        self.species.freeze()
        self.sanctuaries.freeze()
        self.people.freeze()
        self.balance = balance
        self._by_world = {
            definition.world_id: definition for definition in self.sanctuaries
        }
        if len(self._by_world) != len(tuple(self.sanctuaries)):
            raise ValueError("同一个世界只能登记一个宠物秘境")
        self._people_by_world_location = {
            (definition.origin_world_id, definition.location_id): definition
            for definition in self.people
        }
        if len(self._people_by_world_location) != len(tuple(self.people)):
            raise ValueError("同一世界的一个地点最多登记一名人物伙伴")
        names = tuple(value.name for value in self.people)
        if len(names) != len(set(names)):
            raise ValueError("人物伙伴名称不能重复")
        self._validate_structure()

    def sanctuary_for_world(self, world_id: StableId) -> CompanionSanctuaryDefinition | None:
        return self._by_world.get(stable_id(world_id, field="companion world id"))

    def require_sanctuary(self, world_id: StableId) -> CompanionSanctuaryDefinition:
        definition = self.sanctuary_for_world(world_id)
        if definition is None:
            raise KeyError(f"当前世界没有宠物秘境: {world_id}")
        return definition

    def require_definition(self, definition_id: StableId):
        key = stable_id(definition_id, field="companion definition id")
        if self.species.contains(key):
            return self.species.require(key)
        return self.people.require(key)

    def people_for_world(self, world_id: StableId) -> tuple[PersonCompanionDefinition, ...]:
        key = stable_id(world_id, field="companion world id")
        return tuple(
            value for value in self.people
            if value.origin_world_id == key
        )

    def person_at(
        self,
        world_id: StableId,
        location_id: StableId,
    ) -> PersonCompanionDefinition | None:
        return self._people_by_world_location.get(
            (
                stable_id(world_id, field="companion world id"),
                stable_id(location_id, field="companion person location id"),
            )
        )

    def validate(self, content, worlds) -> None:
        """启动时校验世界与伙伴引用的标准战斗行为。"""

        if set(self._by_world) != set(worlds.world_ids()):
            raise ValueError("每个可进入世界必须且只能提供一个宠物秘境")
        for definition in self.species:
            content.enemies.behaviors.require(definition.core_behavior_id)
            for behavior_id in definition.trait_behavior_ids:
                content.enemies.behaviors.require(behavior_id)
        for definition in self.people:
            if definition.origin_world_id not in worlds.world_ids():
                raise ValueError(f"人物伙伴来源世界不可进入: {definition.id}")
            binding = worlds.binding_for_display(
                definition.origin_world_id,
                definition.location_id,
            )
            if binding is None:
                raise ValueError(f"人物伙伴缺少世界地点绑定: {definition.id}")
            if binding.function_id != "location.function.companion_person":
                raise ValueError(f"人物伙伴地点不是人物专用地点: {definition.location_id}")
            if binding.content_ref != definition.id:
                raise ValueError(
                    f"人物伙伴地点没有引用对应人物: {definition.location_id}/{definition.id}"
                )
            content.qualities.require(definition.quality_id)
            content.enemies.behaviors.require(definition.core_behavior_id)
            content.enemies.behaviors.require(definition.trait_behavior_id)
            for item_id in definition.gift_values:
                item = content.items.require(item_id)
                if not item.tags.has("item.trophy"):
                    raise ValueError(f"人物伙伴礼物必须是战利品: {item_id}")

    def _validate_structure(self) -> None:
        covered: set[StableId] = set()
        for sanctuary in self.sanctuaries:
            for species_id in sanctuary.species_ids:
                species = self.species.require(species_id)
                if species.origin_world_id != sanctuary.world_id:
                    raise ValueError(f"伙伴物种 {species.id} 被登记到错误来源世界")
                if species.id in covered:
                    raise ValueError(f"伙伴物种重复进入多个秘境: {species.id}")
                covered.add(species.id)
        if covered != set(self.species.ids()):
            raise ValueError("每个伙伴物种必须且只能属于一个来源世界秘境")


__all__ = [
    "COMPANION_ROLES",
    "COMPANION_KIND_PERSON",
    "COMPANION_KIND_PET",
    "CompanionBalance",
    "CompanionCatalog",
    "CompanionSanctuaryDefinition",
    "CompanionSpeciesDefinition",
    "PersonCompanionDefinition",
]
