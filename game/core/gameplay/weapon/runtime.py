"""武器经验成长和角色贡献投影。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ..character import CharacterContribution, merge_contribution_specs
from ..context import RuleContext
from ..errors import RuleOutcome, RuleViolation
from ..events import RuleEvent
from ..ids import StableId, stable_id
from .models import WeaponCatalog, WeaponState, weapon_level_contribution


@dataclass(frozen=True)
class WeaponExperienceTransaction:
    id: str
    actor_id: str
    expected_revision: int
    amount: int
    source_kind: StableId
    source_id: str

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.actor_id.strip() or not self.source_id.strip():
            raise ValueError("WeaponExperienceTransaction 缺少必要身份")
        if self.expected_revision < 0:
            raise ValueError("expected_revision 不能小于 0")
        if isinstance(self.amount, bool) or not isinstance(self.amount, int):
            raise ValueError("武器经验必须使用整数")
        object.__setattr__(self, "source_kind", stable_id(self.source_kind, field="source kind"))


@dataclass(frozen=True)
class WeaponExecution:
    transaction_id: str
    state: WeaponState
    events: tuple[RuleEvent, ...]


class WeaponEngine:
    def __init__(self, catalog: WeaponCatalog) -> None:
        if not catalog.finalized:
            catalog.finalize()
        self.catalog = catalog

    def grant_experience(
        self,
        transaction: WeaponExperienceTransaction,
        *,
        state: WeaponState,
        context: RuleContext,
    ) -> RuleOutcome[WeaponExecution]:
        checkpoint = context.random.checkpoint()
        try:
            if state.revision != transaction.expected_revision:
                self._fail(
                    "weapon.revision_conflict",
                    "武器状态版本与事务预期不一致",
                    {"expected": transaction.expected_revision, "actual": state.revision},
                )
            if transaction.amount < 1:
                self._fail("weapon.invalid_experience", "增加的武器经验必须大于 0")
            definition = self.catalog.require(state.definition_id)
            try:
                profile = definition.quality_profiles[state.quality_id]
            except KeyError:
                self._fail("weapon.quality_invalid", "武器品质不属于当前武器定义")
            if state.level > profile.maximum_level:
                self._fail("weapon.level_invalid", "武器等级超过品质成长上限")
            level = state.level
            experience = state.experience + transaction.amount
            total = state.total_experience + transaction.amount
            events = [
                self._event(
                    context,
                    transaction,
                    state,
                    "weapon.experience.gained",
                    definition.id,
                    {
                        "amount": transaction.amount,
                        "level_before": level,
                        "experience_before": state.experience,
                        "total_experience": total,
                    },
                )
            ]
            while True:
                required = profile.required_for_next_level(level)
                if required is None or experience < required:
                    break
                previous = level
                experience -= required
                level += 1
                events.append(
                    self._event(
                        context,
                        transaction,
                        state,
                        "weapon.level.increased",
                        definition.id,
                        {
                            "from_level": previous,
                            "to_level": level,
                            "experience_spent": required,
                            "experience_remaining": experience,
                        },
                    )
                )
            result = WeaponState(
                state.asset_id,
                state.definition_id,
                state.quality_id,
                level,
                experience,
                total,
                state.revision + 1,
                state.roll,
            )
            return RuleOutcome.success(
                WeaponExecution(transaction.id, result, tuple(events))
            )
        except RuleViolation as exc:
            context.random.restore(checkpoint)
            return RuleOutcome.failed(exc.failure)

    @staticmethod
    def _event(
        context: RuleContext,
        transaction: WeaponExperienceTransaction,
        state: WeaponState,
        kind: StableId,
        subject_id: StableId,
        values: Mapping[str, object],
    ) -> RuleEvent:
        return RuleEvent.from_context(
            context,
            kind=kind,
            source_id=transaction.source_id,
            target_id=state.asset_id,
            subject_id=subject_id,
            values={
                "transaction_id": transaction.id,
                "actor_id": transaction.actor_id,
                "source_kind": transaction.source_kind,
                "source_id": transaction.source_id,
                **values,
            },
        )

    @staticmethod
    def _fail(
        code: StableId,
        message: str,
        details: Mapping[str, object] | None = None,
    ) -> None:
        raise RuleViolation(code, message, details or {})


class WeaponContributionProvider:
    def __init__(self, catalog: WeaponCatalog) -> None:
        if not catalog.finalized:
            catalog.finalize()
        self.catalog = catalog

    def contribution(self, state: WeaponState) -> CharacterContribution:
        definition = self.catalog.require(state.definition_id)
        try:
            profile = definition.quality_profiles[state.quality_id]
        except KeyError as exc:
            raise KeyError(f"武器 {definition.id} 不支持品质：{state.quality_id}") from exc
        return CharacterContribution(
            definition.id,
            "source.weapon_instance",
            state.asset_id,
            merge_contribution_specs(
                definition.base_contribution,
                profile.contribution,
                weapon_level_contribution(profile, state.level),
                self._random_contribution(definition.generation_profile_id, state),
            ),
        )

    def _random_contribution(
        self,
        generation_profile_id: StableId | None,
        state: WeaponState,
    ):
        if generation_profile_id is None:
            if state.roll is not None:
                raise ValueError("固定武器实例不能携带随机属性")
            return merge_contribution_specs()
        if state.roll is None or state.roll.profile_id != generation_profile_id:
            raise ValueError("生成型武器实例缺少有效随机属性")
        if state.roll.quality_id != state.quality_id:
            raise ValueError("生成型武器实例品质与随机属性不一致")
        if self.catalog.itemization is None:
            raise RuntimeError("生成型武器目录缺少物品化引擎")
        return self.catalog.itemization.validate_roll(state.roll)


__all__ = [
    "WeaponContributionProvider",
    "WeaponEngine",
    "WeaponExecution",
    "WeaponExperienceTransaction",
]
