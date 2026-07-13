"""由持续 Effect 授予的可注册伤害干预器。"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Callable, Mapping

from ..context import RuleContext
from ..entity import InterceptorBinding, RuleEntity
from ..ids import StableId, stable_id
from ..registry import DefinitionRegistry
from ..tags import EMPTY_TAGS, TagSet
from .models import (
    DamageFrame,
    DamageInterceptionRecord,
    DamageRedirect,
    DamageRequest,
    DamageStage,
    InterceptorSide,
)


@dataclass(frozen=True)
class DamageInterceptorDefinition:
    id: StableId
    handler_id: StableId
    stage: DamageStage
    side: InterceptorSide
    priority: int = 0
    required_damage_tags: TagSet = EMPTY_TAGS
    blocked_damage_tags: TagSet = EMPTY_TAGS
    configuration: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="interceptor id"))
        object.__setattr__(self, "handler_id", stable_id(self.handler_id, field="handler id"))
        object.__setattr__(self, "configuration", MappingProxyType(dict(self.configuration)))


InterceptorHandler = Callable[
    [
        DamageInterceptorDefinition,
        InterceptorBinding,
        DamageFrame,
        DamageRequest,
        RuleEntity,
        RuleEntity,
        RuleContext,
    ],
    DamageFrame,
]


class DamageInterceptorRegistry:
    """按固定阶段执行来源与目标当前拥有的伤害干预器。"""

    def __init__(self, definitions: DefinitionRegistry[DamageInterceptorDefinition]) -> None:
        self.definitions = definitions
        self._handlers: dict[StableId, InterceptorHandler] = {}
        self._frozen = False

    def register_handler(self, handler_id: StableId, handler: InterceptorHandler) -> None:
        if self._frozen:
            raise RuntimeError("伤害干预器注册表已经冻结")
        key = stable_id(handler_id, field="handler id")
        if key in self._handlers:
            raise ValueError(f"伤害干预处理器重复：{key}")
        self._handlers[key] = handler

    def register_default_handlers(self) -> None:
        self.register_handler("interceptor.multiply", _multiply)
        self.register_handler("interceptor.flat", _flat)
        self.register_handler("interceptor.cap", _cap)
        self.register_handler("interceptor.immunity", _immunity)
        self.register_handler("interceptor.bypass_shield", _bypass_shield)
        self.register_handler("interceptor.death_guard", _death_guard)
        self.register_handler("interceptor.convert", _convert)
        self.register_handler(
            "interceptor.redirect_to_grant_source",
            _redirect_to_grant_source,
        )

    def freeze(self) -> None:
        for definition in self.definitions:
            if definition.handler_id not in self._handlers:
                raise KeyError(
                    f"伤害干预器 {definition.id} 引用了未知处理器：{definition.handler_id}"
                )
            if (
                definition.handler_id == "interceptor.convert"
                and definition.stage is not DamageStage.RAW
            ):
                raise ValueError("伤害类型转换只能在 RAW 阶段执行")
        self.definitions.freeze()
        self._frozen = True

    def apply(
        self,
        stage: DamageStage,
        frame: DamageFrame,
        *,
        request: DamageRequest,
        source: RuleEntity,
        target: RuleEntity,
        context: RuleContext,
    ) -> tuple[DamageFrame, tuple[DamageInterceptionRecord, ...]]:
        bindings = [
            (source, binding)
            for binding in source.interceptor_bindings
            if self.definitions.require(binding.interceptor_id).side
            in {InterceptorSide.SOURCE, InterceptorSide.BOTH}
        ]
        bindings.extend(
            (target, binding)
            for binding in target.interceptor_bindings
            if self.definitions.require(binding.interceptor_id).side
            in {InterceptorSide.TARGET, InterceptorSide.BOTH}
        )
        bindings.sort(
            key=lambda item: (
                self.definitions.require(item[1].interceptor_id).priority,
                item[1].interceptor_id,
                item[1].effect_instance_id,
            )
        )
        records: list[DamageInterceptionRecord] = []
        current = frame
        for owner, binding in bindings:
            definition = self.definitions.require(binding.interceptor_id)
            if definition.stage is not stage:
                continue
            if not request.tags.allows(
                required=definition.required_damage_tags,
                blocked=definition.blocked_damage_tags,
            ):
                continue
            before = current
            current = self._handlers[definition.handler_id](
                definition,
                binding,
                current,
                request,
                source,
                target,
                context,
            )
            if current.amount < 0 or current.minimum_health < 0:
                raise ValueError(f"伤害干预器 {definition.id} 返回了非法 DamageFrame")
            if current != before:
                records.append(
                    DamageInterceptionRecord(
                        definition.id,
                        owner.id,
                        binding.source_id,
                        stage,
                        before,
                        current,
                    )
                )
        return current, tuple(records)

    def ids(self) -> frozenset[StableId]:
        return frozenset(self.definitions.ids())


def _number(definition: DamageInterceptorDefinition, key: str) -> float:
    try:
        return float(definition.configuration[key])
    except KeyError as exc:
        raise ValueError(f"伤害干预器 {definition.id} 缺少配置：{key}") from exc


def _multiply(definition, _binding, frame, *_args) -> DamageFrame:
    return replace(frame, amount=max(0.0, frame.amount * _number(definition, "multiplier")))


def _flat(definition, _binding, frame, *_args) -> DamageFrame:
    return replace(frame, amount=max(0.0, frame.amount + _number(definition, "amount")))


def _cap(definition, _binding, frame, *_args) -> DamageFrame:
    return replace(frame, amount=min(frame.amount, max(0.0, _number(definition, "maximum"))))


def _immunity(_definition, _binding, frame, *_args) -> DamageFrame:
    return replace(frame, amount=0.0)


def _bypass_shield(_definition, _binding, frame, *_args) -> DamageFrame:
    return replace(frame, bypass_shield=True)


def _death_guard(definition, _binding, frame, *_args) -> DamageFrame:
    return replace(
        frame,
        minimum_health=max(frame.minimum_health, _number(definition, "minimum_health")),
    )


def _convert(definition, _binding, frame, *_args) -> DamageFrame:
    try:
        damage_type = stable_id(definition.configuration["damage_type"], field="damage type id")
    except KeyError as exc:
        raise ValueError(f"伤害干预器 {definition.id} 缺少 damage_type") from exc
    return replace(frame, damage_type=damage_type)


def _redirect_to_grant_source(
    definition,
    binding,
    frame,
    *_args,
) -> DamageFrame:
    ratio = min(1.0, max(0.0, _number(definition, "ratio")))
    redirected = frame.amount * ratio
    if redirected <= 0:
        return frame
    damage_type = definition.configuration.get("damage_type", frame.damage_type)
    return replace(
        frame,
        amount=frame.amount - redirected,
        redirects=(
            *frame.redirects,
            DamageRedirect(binding.source_id, redirected, damage_type),
        ),
    )


__all__ = [
    "DamageInterceptorDefinition",
    "DamageInterceptorRegistry",
    "InterceptorHandler",
]
