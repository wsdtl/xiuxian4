"""角色成长、永久特征和持久资源的原子事务。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol

from ..context import RuleContext
from ..errors import RuleOutcome, RuleViolation
from ..events import RuleEvent
from ..ids import StableId, stable_id
from ..phases import ExecutionPhase
from .definitions import CharacterCatalog, ProgressionMilestone
from .models import (
    CORE_ATTRIBUTE_IDS,
    HEALTH_CURRENT,
    HEALTH_MAXIMUM,
    PERSISTENT_RESOURCE_IDS,
    CharacterState,
    CharacterStatus,
    ProgressionState,
)


class CharacterOperation(Protocol):
    """角色事务接受的原子操作标记。"""


@dataclass(frozen=True)
class GrantExperience:
    progression_id: StableId
    amount: int
    source_kind: StableId
    source_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "progression_id", stable_id(self.progression_id, field="progression id"))
        object.__setattr__(self, "source_kind", stable_id(self.source_kind, field="source kind"))
        if not self.source_id.strip():
            raise ValueError("GrantExperience 缺少 source_id")


@dataclass(frozen=True)
class GrantCoreAttribute:
    attribute_id: StableId
    amount: float
    source_kind: StableId
    source_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "attribute_id", stable_id(self.attribute_id, field="core attribute id"))
        object.__setattr__(self, "source_kind", stable_id(self.source_kind, field="source kind"))
        if not self.source_id.strip():
            raise ValueError("GrantCoreAttribute 缺少 source_id")


@dataclass(frozen=True)
class UnlockFeature:
    feature_id: StableId
    source_kind: StableId
    source_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "feature_id", stable_id(self.feature_id, field="feature id"))
        object.__setattr__(self, "source_kind", stable_id(self.source_kind, field="source kind"))
        if not self.source_id.strip():
            raise ValueError("UnlockFeature 缺少 source_id")


@dataclass(frozen=True)
class UnlockProgression:
    progression_id: StableId
    source_kind: StableId
    source_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "progression_id", stable_id(self.progression_id, field="progression id"))
        object.__setattr__(self, "source_kind", stable_id(self.source_kind, field="source kind"))
        if not self.source_id.strip():
            raise ValueError("UnlockProgression 缺少 source_id")


@dataclass(frozen=True)
class ChangeCharacterResource:
    resource_id: StableId
    delta: float
    source_kind: StableId
    source_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "resource_id", stable_id(self.resource_id, field="resource id"))
        object.__setattr__(self, "source_kind", stable_id(self.source_kind, field="source kind"))
        if not self.source_id.strip():
            raise ValueError("ChangeCharacterResource 缺少 source_id")


@dataclass(frozen=True)
class RetireCharacter:
    source_kind: StableId
    source_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_kind", stable_id(self.source_kind, field="source kind"))
        if not self.source_id.strip():
            raise ValueError("RetireCharacter 缺少 source_id")


@dataclass(frozen=True)
class CharacterTransaction:
    id: str
    actor_id: str
    expected_revision: int
    reason: StableId
    operations: tuple[CharacterOperation, ...]

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("CharacterTransaction 缺少 id")
        if not self.actor_id.strip():
            raise ValueError("CharacterTransaction 缺少 actor_id")
        if self.expected_revision < 0:
            raise ValueError("CharacterTransaction.expected_revision 不能小于 0")
        object.__setattr__(self, "reason", stable_id(self.reason, field="transaction reason"))
        if not self.operations:
            raise ValueError("CharacterTransaction.operations 不能为空")


@dataclass(frozen=True)
class CharacterExecution:
    transaction_id: str
    state: CharacterState
    events: tuple[RuleEvent, ...]


@dataclass
class _Draft:
    core_attributes: dict[StableId, float]
    resources: dict[StableId, float]
    progressions: dict[StableId, ProgressionState]
    features: set[StableId]
    status: CharacterStatus
    events: list[RuleEvent]


class CharacterEngine:
    """在角色不可变快照上执行全有或全无的长期成长。"""

    def __init__(self, catalog: CharacterCatalog) -> None:
        if not catalog.finalized:
            catalog.finalize()
        self.catalog = catalog

    def execute(
        self,
        transaction: CharacterTransaction,
        *,
        state: CharacterState,
        context: RuleContext,
    ) -> RuleOutcome[CharacterExecution]:
        checkpoint = context.random.checkpoint()
        try:
            if state.revision != transaction.expected_revision:
                self._fail(
                    "character.revision_conflict",
                    "角色状态版本与事务预期不一致",
                    {"expected": transaction.expected_revision, "actual": state.revision},
                )
            if state.status is not CharacterStatus.ACTIVE:
                self._fail("character.not_active", "非活跃角色不能继续成长")
            self._validate_state_references(state)
            draft = _Draft(
                dict(state.core_attributes),
                dict(state.resources),
                dict(state.progressions),
                set(state.features),
                state.status,
                [],
            )
            for operation in transaction.operations:
                if draft.status is not CharacterStatus.ACTIVE:
                    self._fail("character.not_active", "角色退隐后不能继续执行其他操作")
                self._apply(operation, draft, state, transaction, context)
            result = CharacterState(
                state.id,
                state.account_id,
                state.name,
                state.template_id,
                state.created_at,
                draft.core_attributes,
                draft.resources,
                draft.progressions,
                frozenset(draft.features),
                draft.status,
                state.revision + 1,
            )
            return RuleOutcome.success(
                CharacterExecution(transaction.id, result, tuple(draft.events))
            )
        except RuleViolation as exc:
            context.random.restore(checkpoint)
            return RuleOutcome.failed(exc.failure)

    def _apply(
        self,
        operation: CharacterOperation,
        draft: _Draft,
        original: CharacterState,
        transaction: CharacterTransaction,
        context: RuleContext,
    ) -> None:
        handlers = {
            GrantExperience: self._grant_experience,
            GrantCoreAttribute: self._grant_core_attribute,
            UnlockFeature: self._unlock_feature,
            UnlockProgression: self._unlock_progression,
            ChangeCharacterResource: self._change_resource,
            RetireCharacter: self._retire_character,
        }
        try:
            handler = handlers[type(operation)]
        except KeyError as exc:
            raise TypeError(f"未知角色操作：{type(operation).__name__}") from exc
        handler(operation, draft, original, transaction, context)

    def _grant_experience(
        self,
        operation: GrantExperience,
        draft: _Draft,
        original: CharacterState,
        transaction: CharacterTransaction,
        context: RuleContext,
    ) -> None:
        if operation.amount < 1:
            self._fail("character.invalid_experience", "增加的成长经验必须大于 0")
        try:
            current = draft.progressions[operation.progression_id]
        except KeyError:
            self._fail(
                "character.progression_not_owned",
                "角色没有指定成长轨道",
                {"progression_id": operation.progression_id},
            )
        definition = self.catalog.progressions.require(operation.progression_id)
        experience = current.experience + operation.amount
        total = current.total_experience + operation.amount
        level = current.level
        self._event(
            draft,
            original,
            transaction,
            context,
            "character.experience.gained",
            definition.id,
            operation.source_id,
            {
                "amount": operation.amount,
                "source_kind": operation.source_kind,
                "source_id": operation.source_id,
                "level_before": level,
                "experience_before": current.experience,
                "total_experience": total,
            },
        )
        while True:
            required = definition.required_for_next_level(level)
            if required is None or experience < required:
                break
            previous = level
            experience -= required
            level += 1
            milestone = definition.milestones.get(level)
            if milestone is not None:
                self._apply_milestone(
                    milestone,
                    definition.id,
                    operation,
                    draft,
                    original,
                    transaction,
                    context,
                )
            self._event(
                draft,
                original,
                transaction,
                context,
                "character.progression.advanced",
                definition.id,
                operation.source_id,
                {
                    "from_level": previous,
                    "to_level": level,
                    "experience_spent": required,
                    "experience_remaining": experience,
                    "source_kind": operation.source_kind,
                    "source_id": operation.source_id,
                },
            )
        draft.progressions[definition.id] = ProgressionState(
            definition.id,
            level,
            experience,
            total,
        )

    def _apply_milestone(
        self,
        milestone: ProgressionMilestone,
        progression_id: StableId,
        operation: GrantExperience,
        draft: _Draft,
        original: CharacterState,
        transaction: CharacterTransaction,
        context: RuleContext,
    ) -> None:
        for attribute_id, delta in milestone.core_attribute_deltas.items():
            draft.core_attributes[attribute_id] += delta
        self._validate_core_values(draft.core_attributes)
        health_growth = float(milestone.core_attribute_deltas.get(HEALTH_MAXIMUM, 0.0))
        if health_growth > 0:
            before = draft.resources[HEALTH_CURRENT]
            draft.resources[HEALTH_CURRENT] = before + health_growth
            self._event(
                draft,
                original,
                transaction,
                context,
                "character.resource.changed",
                HEALTH_CURRENT,
                operation.source_id,
                {
                    "delta": health_growth,
                    "before": before,
                    "current": draft.resources[HEALTH_CURRENT],
                    "progression_id": progression_id,
                    "milestone_level": milestone.level,
                    "source_kind": operation.source_kind,
                    "source_id": operation.source_id,
                    "reason": "maximum_health_growth",
                },
            )
        for feature_id in sorted(milestone.feature_ids):
            if feature_id in draft.features:
                continue
            draft.features.add(feature_id)
            self._event(
                draft,
                original,
                transaction,
                context,
                "character.feature.unlocked",
                feature_id,
                operation.source_id,
                {
                    "progression_id": progression_id,
                    "milestone_level": milestone.level,
                    "source_kind": operation.source_kind,
                    "source_id": operation.source_id,
                },
            )
        self._event(
            draft,
            original,
            transaction,
            context,
            "character.milestone.applied",
            progression_id,
            operation.source_id,
            {
                "level": milestone.level,
                "core_attribute_deltas": dict(milestone.core_attribute_deltas),
                "feature_ids": tuple(sorted(milestone.feature_ids)),
            },
        )

    def _grant_core_attribute(
        self,
        operation: GrantCoreAttribute,
        draft: _Draft,
        original: CharacterState,
        transaction: CharacterTransaction,
        context: RuleContext,
    ) -> None:
        if operation.attribute_id not in CORE_ATTRIBUTE_IDS:
            self._fail(
                "character.not_core_attribute",
                "永久成长不能直接写入非核心属性",
                {"attribute_id": operation.attribute_id},
            )
        before = draft.core_attributes[operation.attribute_id]
        draft.core_attributes[operation.attribute_id] = before + float(operation.amount)
        self._validate_core_values(draft.core_attributes)
        self._event(
            draft,
            original,
            transaction,
            context,
            "character.core_attribute.changed",
            operation.attribute_id,
            operation.source_id,
            {
                "delta": float(operation.amount),
                "before": before,
                "current": draft.core_attributes[operation.attribute_id],
                "source_kind": operation.source_kind,
                "source_id": operation.source_id,
            },
        )

    def _unlock_feature(
        self,
        operation: UnlockFeature,
        draft: _Draft,
        original: CharacterState,
        transaction: CharacterTransaction,
        context: RuleContext,
    ) -> None:
        try:
            self.catalog.features.require(operation.feature_id)
        except KeyError:
            self._fail(
                "character.feature_unknown",
                "找不到要解锁的永久特征",
                {"feature_id": operation.feature_id},
            )
        if operation.feature_id in draft.features:
            self._fail("character.feature_already_unlocked", "角色已经拥有该永久特征")
        draft.features.add(operation.feature_id)
        self._event(
            draft,
            original,
            transaction,
            context,
            "character.feature.unlocked",
            operation.feature_id,
            operation.source_id,
            {
                "source_kind": operation.source_kind,
                "source_id": operation.source_id,
            },
        )

    def _change_resource(
        self,
        operation: ChangeCharacterResource,
        draft: _Draft,
        original: CharacterState,
        transaction: CharacterTransaction,
        context: RuleContext,
    ) -> None:
        if operation.resource_id not in PERSISTENT_RESOURCE_IDS:
            self._fail(
                "character.resource_unknown",
                "角色档案不保存该资源",
                {"resource_id": operation.resource_id},
            )
        before = draft.resources[operation.resource_id]
        current = before + float(operation.delta)
        if current < 0:
            self._fail(
                "character.resource_insufficient",
                "角色持久资源不足",
                {"resource_id": operation.resource_id, "current": before, "delta": operation.delta},
            )
        draft.resources[operation.resource_id] = current
        self._event(
            draft,
            original,
            transaction,
            context,
            "character.resource.changed",
            operation.resource_id,
            operation.source_id,
            {
                "delta": float(operation.delta),
                "before": before,
                "current": current,
                "source_kind": operation.source_kind,
                "source_id": operation.source_id,
            },
            phase=ExecutionPhase.PAY_COST if operation.delta < 0 else ExecutionPhase.RESOLVE,
        )

    def _unlock_progression(
        self,
        operation: UnlockProgression,
        draft: _Draft,
        original: CharacterState,
        transaction: CharacterTransaction,
        context: RuleContext,
    ) -> None:
        try:
            self.catalog.progressions.require(operation.progression_id)
        except KeyError:
            self._fail(
                "character.progression_unknown",
                "找不到要解锁的成长轨道",
                {"progression_id": operation.progression_id},
            )
        if operation.progression_id in draft.progressions:
            self._fail("character.progression_already_unlocked", "角色已经拥有该成长轨道")
        draft.progressions[operation.progression_id] = ProgressionState(operation.progression_id)
        self._event(
            draft,
            original,
            transaction,
            context,
            "character.progression.unlocked",
            operation.progression_id,
            operation.source_id,
            {
                "source_kind": operation.source_kind,
                "source_id": operation.source_id,
            },
        )

    def _retire_character(
        self,
        operation: RetireCharacter,
        draft: _Draft,
        original: CharacterState,
        transaction: CharacterTransaction,
        context: RuleContext,
    ) -> None:
        draft.status = CharacterStatus.RETIRED
        self._event(
            draft,
            original,
            transaction,
            context,
            "character.retired",
            original.template_id,
            operation.source_id,
            {"source_kind": operation.source_kind, "source_id": operation.source_id},
        )

    def _validate_state_references(self, state: CharacterState) -> None:
        self.catalog.templates.require(state.template_id)
        unknown_progressions = set(state.progressions) - set(self.catalog.progressions.ids())
        unknown_features = set(state.features) - set(self.catalog.features.ids())
        if unknown_progressions or unknown_features:
            self._fail(
                "character.reference_invalid",
                "角色状态包含未知内容引用",
                {
                    "progressions": tuple(sorted(unknown_progressions)),
                    "features": tuple(sorted(unknown_features)),
                },
            )
        for progression_id, progression in state.progressions.items():
            definition = self.catalog.progressions.require(progression_id)
            if progression.level > definition.maximum_level:
                self._fail(
                    "character.progression_invalid",
                    "角色成长等级超过定义上限",
                    {"progression_id": progression_id, "level": progression.level},
                )

    @staticmethod
    def _validate_core_values(values: Mapping[StableId, float]) -> None:
        # 通过临时状态构造会引入无关字段，这里只复用相同的数值边界。
        from .models import COMBAT_ATTACK, COMBAT_SPEED, HEALTH_MAXIMUM, SPIRIT_MAXIMUM

        if values[HEALTH_MAXIMUM] < 1:
            CharacterEngine._fail("character.attribute_out_of_bounds", "最大血气不能小于 1")
        for attribute_id in (SPIRIT_MAXIMUM, COMBAT_ATTACK, COMBAT_SPEED):
            if values[attribute_id] < 0:
                CharacterEngine._fail(
                    "character.attribute_out_of_bounds",
                    "角色核心属性不能小于 0",
                    {"attribute_id": attribute_id, "value": values[attribute_id]},
                )

    @staticmethod
    def _event(
        draft: _Draft,
        original: CharacterState,
        transaction: CharacterTransaction,
        context: RuleContext,
        kind: StableId,
        subject_id: StableId,
        source_id: str,
        values: Mapping[str, object],
        *,
        phase: ExecutionPhase = ExecutionPhase.RESOLVE,
    ) -> None:
        draft.events.append(
            RuleEvent.from_context(
                context,
                kind=kind,
                source_id=source_id,
                target_id=original.id,
                subject_id=subject_id,
                values={
                    "transaction_id": transaction.id,
                    "reason": transaction.reason,
                    "actor_id": transaction.actor_id,
                    **values,
                },
                phase=phase,
            )
        )

    @staticmethod
    def _fail(
        code: StableId,
        message: str,
        details: Mapping[str, object] | None = None,
    ) -> None:
        raise RuleViolation(code, message, details or {})


__all__ = [
    "ChangeCharacterResource",
    "CharacterEngine",
    "CharacterExecution",
    "CharacterOperation",
    "CharacterTransaction",
    "GrantCoreAttribute",
    "GrantExperience",
    "RetireCharacter",
    "UnlockFeature",
    "UnlockProgression",
]
