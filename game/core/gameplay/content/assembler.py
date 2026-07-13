"""内容包依赖解析、分阶段装配、总校验、冻结和运行指纹。"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime, time, timedelta
from enum import Enum
from hashlib import sha256
import json
import re
from types import MappingProxyType
from typing import Iterable, Mapping

from ..actions import ActionCatalog, ActionEngine
from ..abilities import AbilityDefinition, AbilityEngine
from ..attributes import AttributeDefinition, AttributeResolver, MagnitudeEvaluators, ResourceDefinition
from ..character import CharacterCatalog
from ..combat import (
    ControlDefinition,
    ControlEngine,
    DamageEngine,
    DamageInterceptorDefinition,
    DamageInterceptorRegistry,
    DamageTypeDefinition,
    RecoveryEngine,
    TargetConstraintDefinition,
    TargetConstraintRegistry,
    TargetSelectorRegistry,
    register_control_operation,
    register_damage_operation,
    register_recovery_operations,
    register_timeline_operations,
)
from ..conditions import ConditionEngine, ConditionHandlers
from ..cycles import CycleDefinition, CycleEngine, CycleScheduleHandlers
from ..economy import CurrencyCatalog
from ..effects import EffectDefinition, EffectEngine, EffectOperationHandlers
from ..equipment import EquipmentCatalog
from ..ids import StableId, stable_id
from ..inventory import (
    ItemCatalog,
    ItemComponentRegistry,
    register_item_ability_component,
)
from ..loadout import (
    QualityCatalog,
    register_loadout_item_component,
    standard_loadout_slot_catalog,
)
from ..registry import DefinitionRegistry
from ..skins import SkinCatalog
from ..triggers import TriggerDefinition, TriggerEngine
from ..weapon import WeaponCatalog
from .models import CombatProfileDefinition, ContentPackage, ContentVersion


CONTENT_FOUNDATION_VERSION = "content.foundation.v1"


@dataclass(frozen=True)
class ContentOwner:
    package_id: StableId
    category: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "package_id", stable_id(self.package_id, field="package id"))
        if not self.category.strip():
            raise ValueError("ContentOwner.category 不能为空")


@dataclass(frozen=True)
class SelectedPackage:
    id: StableId
    version: ContentVersion

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="package id"))
        if not isinstance(self.version, ContentVersion):
            raise TypeError("SelectedPackage.version 类型不正确")


@dataclass(frozen=True)
class ContentAssemblyReport:
    packages: tuple[SelectedPackage, ...]
    active_combat_profile_id: StableId
    content_fingerprint: str
    ownership: Mapping[StableId, ContentOwner]
    display_content_ids: frozenset[StableId]

    def __post_init__(self) -> None:
        packages = tuple(self.packages)
        package_ids = [value.id for value in packages]
        if not packages or len(package_ids) != len(set(package_ids)):
            raise ValueError("ContentAssemblyReport 包集合为空或重复")
        object.__setattr__(
            self,
            "active_combat_profile_id",
            stable_id(self.active_combat_profile_id, field="combat profile id"),
        )
        if not re.fullmatch(r"[0-9a-f]{64}", self.content_fingerprint):
            raise ValueError("内容指纹必须是 64 位小写十六进制 SHA-256")
        ownership = {
            stable_id(key, field="content id"): value
            for key, value in self.ownership.items()
        }
        display_ids = frozenset(
            stable_id(value, field="display content id")
            for value in self.display_content_ids
        )
        if not display_ids.issubset(ownership):
            raise ValueError("展示内容 ID 必须拥有明确内容包归属")
        unknown_owners = {
            value.package_id for value in ownership.values()
        } - set(package_ids)
        if unknown_owners:
            raise ValueError("内容归属引用了未选择的包")
        object.__setattr__(self, "packages", packages)
        object.__setattr__(self, "ownership", MappingProxyType(ownership))
        object.__setattr__(self, "display_content_ids", display_ids)


@dataclass(frozen=True)
class ContentRuntime:
    """全部目录已经校验并冻结后的唯一运行期内容入口。"""

    report: ContentAssemblyReport
    currencies: CurrencyCatalog
    items: ItemCatalog
    qualities: QualityCatalog
    characters: CharacterCatalog
    weapons: WeaponCatalog
    equipment: EquipmentCatalog
    skins: SkinCatalog
    combat_profiles: DefinitionRegistry[CombatProfileDefinition]
    attributes: Mapping[StableId, AttributeDefinition]
    resources: Mapping[StableId, ResourceDefinition]
    damage_types: DefinitionRegistry[DamageTypeDefinition]
    controls: DefinitionRegistry[ControlDefinition]
    interceptors: DefinitionRegistry[DamageInterceptorDefinition]
    target_constraints: DefinitionRegistry[TargetConstraintDefinition]
    effects: DefinitionRegistry[EffectDefinition]
    abilities: DefinitionRegistry[AbilityDefinition]
    triggers: DefinitionRegistry[TriggerDefinition]
    cycles: DefinitionRegistry[CycleDefinition]
    actions: ActionCatalog
    damage_engine: DamageEngine
    recovery_engine: RecoveryEngine
    control_engine: ControlEngine
    effect_engine: EffectEngine
    ability_engine: AbilityEngine
    trigger_engine: TriggerEngine
    target_selectors: TargetSelectorRegistry
    cycle_engine: CycleEngine
    action_engine: ActionEngine

    def __post_init__(self) -> None:
        object.__setattr__(self, "attributes", MappingProxyType(dict(self.attributes)))
        object.__setattr__(self, "resources", MappingProxyType(dict(self.resources)))


class ContentAssembler:
    def __init__(self, *, active_combat_profile_id: StableId | None = None) -> None:
        self.active_combat_profile_id = (
            stable_id(active_combat_profile_id, field="combat profile id")
            if active_combat_profile_id
            else None
        )

    def assemble(self, packages: Iterable[ContentPackage]) -> ContentRuntime:
        ordered = resolve_package_order(packages)
        ownership: dict[StableId, ContentOwner] = {}
        known_displayable: set[StableId] = set()

        item_components = ItemComponentRegistry()
        register_item_ability_component(item_components)
        register_loadout_item_component(item_components)
        currencies = CurrencyCatalog()
        qualities = QualityCatalog()
        items = ItemCatalog(item_components)
        slots = standard_loadout_slot_catalog()
        characters = CharacterCatalog()
        profiles = DefinitionRegistry[CombatProfileDefinition]("CombatProfile")
        damage_types = DefinitionRegistry[DamageTypeDefinition]("DamageType")
        controls = DefinitionRegistry[ControlDefinition]("Control")
        interceptors = DefinitionRegistry[DamageInterceptorDefinition]("DamageInterceptor")
        constraints = DefinitionRegistry[TargetConstraintDefinition]("TargetConstraint")
        effects = DefinitionRegistry[EffectDefinition]("Effect")
        abilities = DefinitionRegistry[AbilityDefinition]("Ability")
        triggers = DefinitionRegistry[TriggerDefinition]("Trigger")
        cycles = DefinitionRegistry[CycleDefinition]("Cycle")
        actions = ActionCatalog()
        attributes: dict[StableId, AttributeDefinition] = {}
        resources: dict[StableId, ResourceDefinition] = {}

        magnitudes = MagnitudeEvaluators.with_defaults()
        condition_handlers = ConditionHandlers.with_defaults()
        effect_operations = EffectOperationHandlers.with_defaults()
        cycle_handlers = CycleScheduleHandlers.with_defaults()
        extension_type_owners: dict[type[object], StableId] = {}

        for package in ordered:
            for definition in package.item_component_types:
                self._claim(
                    definition.id,
                    "item_component",
                    package.manifest.id,
                    ownership,
                )
                item_components.register(definition)
            for registration in package.magnitude_registrations:
                self._claim_extension_type(
                    registration.value_type,
                    package.manifest.id,
                    extension_type_owners,
                )
                magnitudes.register(
                    registration.value_type,
                    registration.evaluator,
                    registration.validator,
                )
            for registration in package.condition_registrations:
                self._claim_extension_type(
                    registration.value_type,
                    package.manifest.id,
                    extension_type_owners,
                )
                condition_handlers.register(
                    registration.value_type,
                    registration.handler,
                    registration.validator,
                )
            for registration in package.effect_operation_registrations:
                self._claim_extension_type(
                    registration.value_type,
                    package.manifest.id,
                    extension_type_owners,
                )
                effect_operations.register(
                    registration.value_type,
                    registration.handler,
                    registration.validator,
                )
            for registration in package.cycle_schedule_registrations:
                self._claim_extension_type(
                    registration.schedule_type,
                    package.manifest.id,
                    extension_type_owners,
                )
                cycle_handlers.register(
                    registration.schedule_type,
                    registration.ending_between,
                    registration.latest_ending_at_or_before,
                    registration.containing,
                )

        for package in ordered:
            package_id = package.manifest.id
            self._register_many(
                package,
                "currency",
                package.currencies,
                currencies.register,
                ownership,
                known_displayable,
            )
            self._register_many(
                package,
                "cycle",
                package.cycles,
                cycles.register,
                ownership,
                known_displayable,
            )
            self._register_many(
                package,
                "action",
                package.actions,
                actions.register,
                ownership,
                known_displayable,
            )
            self._register_many(
                package,
                "quality",
                package.qualities,
                qualities.register,
                ownership,
                known_displayable,
            )
            self._register_mapping(
                package,
                "attribute",
                package.attributes,
                attributes,
                ownership,
                known_displayable,
            )
            self._register_mapping(
                package,
                "resource",
                package.resources,
                resources,
                ownership,
                known_displayable,
            )
            self._register_many(
                package,
                "character_feature",
                package.character_features,
                characters.features.register,
                ownership,
                known_displayable,
            )
            self._register_many(
                package,
                "progression",
                package.progressions,
                characters.progressions.register,
                ownership,
                known_displayable,
            )
            self._register_many(
                package,
                "character_template",
                package.character_templates,
                characters.templates.register,
                ownership,
                known_displayable,
            )
            self._register_many(
                package,
                "item",
                package.items,
                items.register,
                ownership,
                known_displayable,
            )
            self._register_many(
                package,
                "combat_profile",
                package.combat_profiles,
                profiles.register,
                ownership,
                known_displayable,
            )
            self._register_many(
                package,
                "damage_type",
                package.damage_types,
                damage_types.register,
                ownership,
                known_displayable,
            )
            self._register_many(
                package,
                "control",
                package.controls,
                controls.register,
                ownership,
                known_displayable,
            )
            self._register_many(
                package,
                "interceptor",
                package.interceptors,
                interceptors.register,
                ownership,
                known_displayable,
            )
            self._register_many(
                package,
                "target_constraint",
                package.target_constraints,
                constraints.register,
                ownership,
                known_displayable,
            )
            self._register_many(
                package,
                "effect",
                package.effects,
                effects.register,
                ownership,
                known_displayable,
            )
            self._register_many(
                package,
                "ability",
                package.abilities,
                abilities.register,
                ownership,
                known_displayable,
            )
            self._register_many(
                package,
                "trigger",
                package.triggers,
                triggers.register,
                ownership,
                known_displayable,
            )

        weapons = WeaponCatalog(qualities, items)
        equipment = EquipmentCatalog(qualities, slots, items)
        for package in ordered:
            self._register_many(
                package,
                "equipment_style",
                package.equipment_styles,
                equipment.register_style,
                ownership,
                known_displayable,
            )
            self._register_many(
                package,
                "weapon",
                package.weapons,
                weapons.register,
                ownership,
                known_displayable,
            )
            self._register_many(
                package,
                "equipment",
                package.equipment,
                equipment.register,
                ownership,
                known_displayable,
            )

        for package in ordered:
            for registration in package.interceptor_handler_registrations:
                self._claim(
                    registration.id,
                    "interceptor_handler",
                    package.manifest.id,
                    ownership,
                )
            for registration in package.target_selector_registrations:
                self._claim(
                    registration.id,
                    "target_selector",
                    package.manifest.id,
                    ownership,
                )

        self._validate_declared_dependencies(
            ordered,
            ownership,
            extension_type_owners,
        )
        display_ids = frozenset(
            content_id for package in ordered for content_id in package.display_content_ids
        )
        unknown_display = display_ids - known_displayable
        if unknown_display:
            raise KeyError(
                "世界皮肤展示集合引用未知内容："
                + ", ".join(sorted(unknown_display))
            )

        profile_id = self._select_profile(profiles)
        profile = profiles.require(profile_id)
        attribute_resolver = AttributeResolver(attributes)
        condition_engine = ConditionEngine(condition_handlers)

        interceptor_runtime = DamageInterceptorRegistry(interceptors)
        interceptor_runtime.register_default_handlers()
        for package in ordered:
            for registration in package.interceptor_handler_registrations:
                interceptor_runtime.register_handler(registration.id, registration.handler)

        damage_engine = DamageEngine(
            {definition.id: definition for definition in damage_types},
            attribute_resolver,
            resources,
            profile.combat_stats,
            profile.damage_rules,
            interceptor_runtime,
        )
        recovery_engine = RecoveryEngine(
            attribute_resolver,
            resources,
            profile.recovery_stats,
        )
        control_engine = ControlEngine(controls, attribute_resolver, profile.control_stats)
        register_damage_operation(effect_operations, damage_engine)
        register_recovery_operations(effect_operations, recovery_engine)
        register_control_operation(effect_operations, control_engine)
        register_timeline_operations(effect_operations)

        effect_engine = EffectEngine(
            effects,
            attribute_resolver,
            resources,
            magnitudes=magnitudes,
            operations=effect_operations,
            conditions=condition_engine,
        )
        constraint_runtime = TargetConstraintRegistry(constraints)
        selectors = TargetSelectorRegistry.with_defaults(constraint_runtime)
        for package in ordered:
            for registration in package.target_selector_registrations:
                selectors.register(registration.id, registration.selector)

        ability_engine = AbilityEngine(
            abilities,
            effect_engine,
            trigger_ids=frozenset(triggers.ids()),
            interceptor_ids=interceptor_runtime.ids(),
            target_constraint_ids=constraint_runtime.ids(),
        )
        trigger_engine = TriggerEngine(triggers, effect_engine)
        cycle_engine = CycleEngine(cycles, cycle_handlers)
        action_engine = ActionEngine(actions)
        selectors.freeze()

        currencies.finalize()
        characters.finalize()
        weapons.finalize()
        equipment.finalize()
        profiles.freeze()
        damage_types.freeze()

        skins = SkinCatalog(display_ids)
        for package in ordered:
            for pack in package.skin_packs:
                skins.register(pack)
        skins.freeze()

        fingerprint = _content_fingerprint(ordered, profile_id)
        report = ContentAssemblyReport(
            tuple(SelectedPackage(value.manifest.id, value.manifest.version) for value in ordered),
            profile_id,
            fingerprint,
            ownership,
            display_ids,
        )
        return ContentRuntime(
            report,
            currencies,
            items,
            qualities,
            characters,
            weapons,
            equipment,
            skins,
            profiles,
            attributes,
            resources,
            damage_types,
            controls,
            interceptors,
            constraints,
            effects,
            abilities,
            triggers,
            cycles,
            actions,
            damage_engine,
            recovery_engine,
            control_engine,
            effect_engine,
            ability_engine,
            trigger_engine,
            selectors,
            cycle_engine,
            action_engine,
        )

    def _select_profile(
        self,
        profiles: DefinitionRegistry[CombatProfileDefinition],
    ) -> StableId:
        ids = profiles.ids()
        if self.active_combat_profile_id:
            profiles.require(self.active_combat_profile_id)
            return self.active_combat_profile_id
        if len(ids) != 1:
            raise ValueError("未指定 active_combat_profile_id，且当前战斗配置数量不是 1")
        return ids[0]

    @staticmethod
    def _register_many(
        package,
        category,
        definitions,
        register,
        ownership,
        displayable,
    ) -> None:
        for definition in definitions:
            ContentAssembler._claim(definition.id, category, package.manifest.id, ownership)
            register(definition)
            displayable.add(definition.id)

    @staticmethod
    def _register_mapping(
        package,
        category,
        definitions,
        target,
        ownership,
        displayable,
    ) -> None:
        for definition in definitions:
            ContentAssembler._claim(definition.id, category, package.manifest.id, ownership)
            target[definition.id] = definition
            displayable.add(definition.id)

    @staticmethod
    def _claim(content_id, category, package_id, ownership) -> None:
        previous = ownership.get(content_id)
        if previous is not None:
            raise ValueError(
                f"稳定内容 ID 冲突：{content_id} 同时属于 "
                f"{previous.package_id}/{previous.category} 和 {package_id}/{category}"
            )
        ownership[content_id] = ContentOwner(package_id, category)

    @staticmethod
    def _claim_extension_type(value_type, package_id, ownership) -> None:
        previous = ownership.get(value_type)
        if previous is not None:
            raise ValueError(
                f"内容扩展类型冲突：{value_type.__name__} 同时属于 {previous} 和 {package_id}"
            )
        ownership[value_type] = package_id

    @staticmethod
    def _validate_declared_dependencies(packages, ownership, extension_type_owners) -> None:
        closures = _dependency_closures(packages)
        for package in packages:
            referenced = _known_ids_in(package, frozenset(ownership))
            for content_id in sorted(referenced):
                owner = ownership[content_id]
                if owner.package_id == package.manifest.id:
                    continue
                if owner.package_id not in closures[package.manifest.id]:
                    raise ValueError(
                        f"内容包 {package.manifest.id} 引用了 {content_id}，"
                        f"但未依赖其所有者 {owner.package_id}"
                    )
            referenced_types = _extension_types_in(
                package,
                frozenset(extension_type_owners),
            )
            for value_type in referenced_types:
                owner_id = extension_type_owners[value_type]
                if owner_id == package.manifest.id:
                    continue
                if owner_id not in closures[package.manifest.id]:
                    raise ValueError(
                        f"内容包 {package.manifest.id} 使用扩展类型 {value_type.__name__}，"
                        f"但未依赖其所有者 {owner_id}"
                    )


def resolve_package_order(packages: Iterable[ContentPackage]) -> tuple[ContentPackage, ...]:
    values = tuple(packages)
    by_id: dict[StableId, ContentPackage] = {}
    for package in values:
        package_id = package.manifest.id
        if package_id in by_id:
            raise ValueError(f"同一运行期不能选择内容包的多个版本：{package_id}")
        by_id[package_id] = package
    if not by_id:
        raise ValueError("内容包集合不能为空")
    for package in values:
        for requirement in package.manifest.dependencies:
            dependency = by_id.get(requirement.package_id)
            if dependency is None:
                raise KeyError(
                    f"内容包 {package.manifest.id} 缺少依赖：{requirement.package_id}"
                )
            if not requirement.accepts(dependency.manifest.version):
                raise ValueError(
                    f"内容包 {package.manifest.id} 不接受依赖 "
                    f"{requirement.package_id}@{dependency.manifest.version}"
                )
    remaining = {
        package_id: {value.package_id for value in package.manifest.dependencies}
        for package_id, package in by_id.items()
    }
    ordered: list[ContentPackage] = []
    while remaining:
        ready = sorted(package_id for package_id, deps in remaining.items() if not deps)
        if not ready:
            raise ValueError(
                "内容包依赖存在环：" + ", ".join(sorted(remaining))
            )
        for package_id in ready:
            ordered.append(by_id[package_id])
            del remaining[package_id]
        for dependencies in remaining.values():
            dependencies.difference_update(ready)
    return tuple(ordered)


def _dependency_closures(packages: tuple[ContentPackage, ...]) -> dict[StableId, frozenset[StableId]]:
    direct = {
        package.manifest.id: frozenset(
            requirement.package_id for requirement in package.manifest.dependencies
        )
        for package in packages
    }
    closures: dict[StableId, frozenset[StableId]] = {}
    for package in packages:
        pending = list(direct[package.manifest.id])
        found: set[StableId] = set()
        while pending:
            package_id = pending.pop()
            if package_id in found:
                continue
            found.add(package_id)
            pending.extend(direct[package_id])
        closures[package.manifest.id] = frozenset(found)
    return closures


def _known_ids_in(value: object, known_ids: frozenset[StableId]) -> frozenset[StableId]:
    found: set[StableId] = set()

    def visit(item: object) -> None:
        if isinstance(item, str):
            if item in known_ids:
                found.add(item)
            return
        if item is None or isinstance(item, (bool, int, float, bytes, type)):
            return
        if isinstance(item, Mapping):
            for key, child in item.items():
                visit(key)
                visit(child)
            return
        if isinstance(item, (tuple, list, set, frozenset)):
            for child in item:
                visit(child)
            return
        if is_dataclass(item):
            for field_value in fields(item):
                visit(getattr(item, field_value.name))

    visit(value)
    return frozenset(found)


def _extension_types_in(
    value: object,
    known_types: frozenset[type[object]],
) -> frozenset[type[object]]:
    found: set[type[object]] = set()

    def visit(item: object) -> None:
        if type(item) in known_types:
            found.add(type(item))
        if item is None or isinstance(item, (str, bool, int, float, bytes, type)):
            return
        if isinstance(item, Mapping):
            for key, child in item.items():
                visit(key)
                visit(child)
            return
        if isinstance(item, (tuple, list, set, frozenset)):
            for child in item:
                visit(child)
            return
        if is_dataclass(item):
            for field_value in fields(item):
                visit(getattr(item, field_value.name))

    visit(value)
    return frozenset(found)


def _content_fingerprint(packages: tuple[ContentPackage, ...], profile_id: StableId) -> str:
    payload = {
        "foundation": CONTENT_FOUNDATION_VERSION,
        "active_combat_profile_id": profile_id,
        "packages": packages,
    }
    encoded = json.dumps(
        _canonical(payload),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return sha256(encoded.encode("utf-8")).hexdigest()


def _canonical(value: object) -> object:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, ContentVersion):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.isoformat()
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, type):
        return f"{value.__module__}.{value.__qualname__}"
    if callable(value):
        module = getattr(value, "__module__", "")
        name = getattr(value, "__qualname__", repr(value))
        return f"{module}.{name}"
    if isinstance(value, Mapping):
        return {
            str(key): _canonical(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    if isinstance(value, (set, frozenset)):
        values = [_canonical(item) for item in value]
        return sorted(values, key=lambda item: json.dumps(item, sort_keys=True))
    if is_dataclass(value):
        return {
            item.name: _canonical(getattr(value, item.name))
            for item in fields(value)
        }
    raise TypeError(f"内容指纹不支持类型：{type(value).__name__}")


__all__ = [
    "CONTENT_FOUNDATION_VERSION",
    "ContentAssembler",
    "ContentAssemblyReport",
    "ContentOwner",
    "ContentRuntime",
    "SelectedPackage",
    "resolve_package_order",
]
