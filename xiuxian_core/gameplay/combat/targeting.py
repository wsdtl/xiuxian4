"""可注册的战斗目标选择器。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Callable, Mapping

from ..attributes import AttributeResolver, ResourceDefinition
from ..context import RandomSource
from ..entity import RuleEntity
from ..errors import RuleViolation
from ..ids import StableId, stable_id
from ..registry import DefinitionRegistry
from ..tags import EMPTY_TAGS, TagSet


@dataclass(frozen=True)
class TargetRequest:
    """一次目标选择请求；显式目标只保存内部实体 id。"""

    selector_id: StableId
    explicit_ids: tuple[str, ...] = ()
    maximum_targets: int | None = None
    required_tags: TagSet = EMPTY_TAGS
    blocked_tags: TagSet = EMPTY_TAGS

    def __post_init__(self) -> None:
        object.__setattr__(self, "selector_id", stable_id(self.selector_id, field="selector id"))
        if len(set(self.explicit_ids)) != len(self.explicit_ids):
            raise ValueError("TargetRequest.explicit_ids 不能重复")
        if self.maximum_targets is not None and self.maximum_targets < 1:
            raise ValueError("TargetRequest.maximum_targets 必须大于 0")


@dataclass(frozen=True)
class TargetingContext:
    actor_id: str
    entities: Mapping[str, RuleEntity]
    teams: Mapping[str, StableId]
    slots: Mapping[str, int]
    attributes: AttributeResolver
    health: ResourceDefinition
    random: RandomSource
    inactive_ids: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        object.__setattr__(self, "entities", MappingProxyType(dict(self.entities)))
        object.__setattr__(self, "teams", MappingProxyType(dict(self.teams)))
        object.__setattr__(self, "slots", MappingProxyType(dict(self.slots)))
        if self.actor_id not in self.entities:
            raise KeyError(f"目标选择缺少行动实体：{self.actor_id}")

    def alive(self, entity_id: str) -> bool:
        if entity_id in self.inactive_ids:
            return False
        entity = self.entities[entity_id]
        return entity.resources.get(self.health.id, self.health.minimum) > self.health.minimum

    def health_ratio(self, entity_id: str) -> float:
        entity = self.entities[entity_id]
        current = entity.resources.get(self.health.id, self.health.minimum)
        if self.health.maximum_attribute:
            maximum = entity.snapshot(self.attributes).value(self.health.maximum_attribute)
        else:
            maximum = self.health.fixed_maximum
        if maximum is None or maximum <= self.health.minimum:
            return 0.0
        return (current - self.health.minimum) / (maximum - self.health.minimum)

    def relation(self, entity_id: str) -> str:
        if entity_id == self.actor_id:
            return "self"
        return "ally" if self.teams[entity_id] == self.teams[self.actor_id] else "enemy"


TargetSelector = Callable[[TargetRequest, TargetingContext], tuple[str, ...]]


class TargetConstraintKind(str, Enum):
    UNTARGETABLE = "untargetable"
    FORCE_GRANT_SOURCE = "force_grant_source"


@dataclass(frozen=True)
class TargetConstraintDefinition:
    id: StableId
    kind: TargetConstraintKind
    applies_to_relations: frozenset[str] = frozenset({"enemy"})
    single_target_only: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="target constraint id"))
        unknown = set(self.applies_to_relations) - {"self", "ally", "enemy"}
        if unknown:
            raise ValueError(f"目标约束包含未知关系：{', '.join(sorted(unknown))}")


class TargetConstraintRegistry:
    """统一执行嘲讽、隐身和不可选中等服务端目标约束。"""

    def __init__(self, definitions: DefinitionRegistry[TargetConstraintDefinition]) -> None:
        self.definitions = definitions

    def apply(
        self,
        selected: tuple[str, ...],
        context: TargetingContext,
    ) -> tuple[str, ...]:
        result = selected
        forced_ids: set[str] = set()
        for binding in context.entities[context.actor_id].target_constraint_bindings:
            definition = self.definitions.require(binding.constraint_id)
            if definition.kind is not TargetConstraintKind.FORCE_GRANT_SOURCE:
                continue
            if definition.single_target_only and len(result) != 1:
                continue
            if (
                binding.source_id in context.entities
                and context.alive(binding.source_id)
                and context.relation(binding.source_id) in definition.applies_to_relations
            ):
                forced_ids.add(binding.source_id)
        if forced_ids:
            result = tuple(entity_id for entity_id in result if entity_id in forced_ids)

        visible: list[str] = []
        for entity_id in result:
            blocked = False
            relation = context.relation(entity_id)
            for binding in context.entities[entity_id].target_constraint_bindings:
                definition = self.definitions.require(binding.constraint_id)
                if (
                    definition.kind is TargetConstraintKind.UNTARGETABLE
                    and relation in definition.applies_to_relations
                    and (not definition.single_target_only or len(result) == 1)
                ):
                    blocked = True
                    break
            if not blocked:
                visible.append(entity_id)
        return tuple(visible)

    def freeze(self) -> None:
        self.definitions.freeze()

    def ids(self) -> frozenset[StableId]:
        return frozenset(self.definitions.ids())


class TargetSelectorRegistry:
    """目标算法注册表；战斗时间线只依赖稳定 selector id。"""

    def __init__(self, constraints: TargetConstraintRegistry | None = None) -> None:
        self._selectors: dict[StableId, TargetSelector] = {}
        self._frozen = False
        self.constraints = constraints

    def register(self, selector_id: StableId, selector: TargetSelector) -> None:
        if self._frozen:
            raise RuntimeError("目标选择器注册表已经冻结")
        key = stable_id(selector_id, field="selector id")
        if key in self._selectors:
            raise ValueError(f"目标选择器重复：{key}")
        self._selectors[key] = selector

    def select(
        self,
        request: TargetRequest,
        context: TargetingContext,
        *,
        bypass_constraints: bool = False,
    ) -> tuple[str, ...]:
        try:
            selector = self._selectors[request.selector_id]
        except KeyError as exc:
            raise RuleViolation(
                "target.selector_unknown",
                f"未知目标选择器：{request.selector_id}",
                {"selector_id": request.selector_id},
            ) from exc
        selected = selector(request, context)
        if len(set(selected)) != len(selected):
            raise RuleViolation(
                "target.selector_invalid_result",
                f"目标选择器 {request.selector_id} 返回了重复实体",
                {"selector_id": request.selector_id, "target_ids": selected},
            )
        unknown = tuple(entity_id for entity_id in selected if entity_id not in context.entities)
        if unknown:
            raise RuleViolation(
                "target.selector_invalid_result",
                f"目标选择器 {request.selector_id} 返回了未知实体",
                {"selector_id": request.selector_id, "target_ids": unknown},
            )
        selected = tuple(
            entity_id
            for entity_id in selected
            if context.alive(entity_id)
            and context.entities[entity_id].tags.allows(
                required=request.required_tags,
                blocked=request.blocked_tags,
            )
        )
        if request.maximum_targets is not None:
            selected = selected[: request.maximum_targets]
        if self.constraints and not bypass_constraints:
            selected = self.constraints.apply(selected, context)
        if not selected:
            raise RuleViolation(
                "target.no_valid_target",
                "当前没有符合条件的战斗目标",
                {
                    "actor_id": context.actor_id,
                    "selector_id": request.selector_id,
                },
            )
        return selected

    @classmethod
    def with_defaults(
        cls,
        constraints: TargetConstraintRegistry | None = None,
    ) -> "TargetSelectorRegistry":
        result = cls(constraints)
        result.register("target.self", _self)
        result.register("target.enemy.explicit", _explicit_enemy)
        result.register("target.ally.explicit", _explicit_ally)
        result.register("target.enemy.first", _first_enemy)
        result.register("target.enemy.all", _all_enemies)
        result.register("target.ally.all", _all_allies)
        result.register("target.enemy.random", _random_enemy)
        result.register("target.enemy.lowest_health", _lowest_health_enemy)
        result.register("target.ally.lowest_health", _lowest_health_ally)
        result.register("target.enemy.adjacent", _adjacent_enemies)
        return result

    def ids(self) -> tuple[StableId, ...]:
        return tuple(sorted(self._selectors))

    def freeze(self) -> None:
        if self.constraints:
            self.constraints.freeze()
        self._frozen = True

    @property
    def frozen(self) -> bool:
        return self._frozen


def _candidates(context: TargetingContext, relation: str) -> tuple[str, ...]:
    return tuple(
        entity_id
        for entity_id in sorted(
            context.entities,
            key=lambda value: (context.teams[value], context.slots[value], value),
        )
        if context.alive(entity_id) and context.relation(entity_id) == relation
    )


def _explicit(
    request: TargetRequest,
    context: TargetingContext,
    relation: str,
) -> tuple[str, ...]:
    if not request.explicit_ids:
        raise RuleViolation(
            "target.explicit_required",
            "该目标选择器需要显式目标",
            {"selector_id": request.selector_id},
        )
    invalid = tuple(
        entity_id
        for entity_id in request.explicit_ids
        if entity_id not in context.entities
        or not context.alive(entity_id)
        or context.relation(entity_id) != relation
    )
    if invalid:
        raise RuleViolation(
            "target.explicit_invalid",
            "显式目标不存在、已经败退或阵营关系不符",
            {"actor_id": context.actor_id, "target_ids": invalid},
        )
    return request.explicit_ids


def _self(_request: TargetRequest, context: TargetingContext) -> tuple[str, ...]:
    return (context.actor_id,) if context.alive(context.actor_id) else ()


def _explicit_enemy(request: TargetRequest, context: TargetingContext) -> tuple[str, ...]:
    return _explicit(request, context, "enemy")


def _explicit_ally(request: TargetRequest, context: TargetingContext) -> tuple[str, ...]:
    return _explicit(request, context, "ally")


def _first_enemy(_request: TargetRequest, context: TargetingContext) -> tuple[str, ...]:
    return _candidates(context, "enemy")[:1]


def _all_enemies(_request: TargetRequest, context: TargetingContext) -> tuple[str, ...]:
    return _candidates(context, "enemy")


def _all_allies(_request: TargetRequest, context: TargetingContext) -> tuple[str, ...]:
    values = list(_candidates(context, "ally"))
    if context.alive(context.actor_id):
        values.append(context.actor_id)
    return tuple(sorted(set(values), key=lambda value: (context.slots[value], value)))


def _random_enemy(_request: TargetRequest, context: TargetingContext) -> tuple[str, ...]:
    values = _candidates(context, "enemy")
    return (context.random.choice(values),) if values else ()


def _lowest_health_enemy(_request: TargetRequest, context: TargetingContext) -> tuple[str, ...]:
    values = _candidates(context, "enemy")
    if not values:
        return ()
    return (min(values, key=lambda value: (context.health_ratio(value), context.slots[value], value)),)


def _lowest_health_ally(_request: TargetRequest, context: TargetingContext) -> tuple[str, ...]:
    values = (*_candidates(context, "ally"), context.actor_id)
    values = tuple(value for value in values if context.alive(value))
    if not values:
        return ()
    return (min(values, key=lambda value: (context.health_ratio(value), context.slots[value], value)),)


def _adjacent_enemies(request: TargetRequest, context: TargetingContext) -> tuple[str, ...]:
    primary_ids = _explicit(request, context, "enemy")
    if len(primary_ids) != 1:
        raise RuleViolation(
            "target.primary_required",
            "相邻目标选择器只接受一个主目标",
            {"target_ids": primary_ids},
        )
    primary = primary_ids[0]
    team = context.teams[primary]
    slot = context.slots[primary]
    return tuple(
        entity_id
        for entity_id in _candidates(context, "enemy")
        if context.teams[entity_id] == team and abs(context.slots[entity_id] - slot) <= 1
    )


__all__ = [
    "TargetRequest",
    "TargetConstraintDefinition",
    "TargetConstraintKind",
    "TargetConstraintRegistry",
    "TargetSelector",
    "TargetSelectorRegistry",
    "TargetingContext",
]
