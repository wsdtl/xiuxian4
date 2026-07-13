"""活动实例、参与、贡献和冻结排名状态机。"""

from __future__ import annotations

from dataclasses import replace

from ..context import RuleContext
from ..errors import RuleOutcome, RuleViolation
from ..events import RuleEvent
from .models import (
    ActivityCatalog,
    ActivityCommand,
    ActivityExecution,
    ActivityInstance,
    ActivityParticipant,
    ActivityRankEntry,
    ActivityState,
    ActivityStatus,
    ActivityTieBreaker,
    CancelActivity,
    CloseActivity,
    CreateActivity,
    FinalizeActivity,
    JoinActivity,
    OpenActivity,
    RecordActivityContribution,
)


class ActivityEngine:
    def __init__(self, catalog: ActivityCatalog) -> None:
        if not catalog.finalized:
            catalog.finalize()
        self.catalog = catalog

    def execute(
        self,
        command: ActivityCommand,
        *,
        state: ActivityState,
        context: RuleContext,
    ) -> RuleOutcome[ActivityExecution]:
        checkpoint = context.random.checkpoint()
        try:
            if state.revision != command.expected_revision:
                self._fail(
                    "activity.revision_conflict",
                    "活动状态版本与命令预期不一致",
                    {"expected": command.expected_revision, "actual": state.revision},
                )
            instances = dict(state.instances)
            operation = command.operation
            if isinstance(operation, CreateActivity):
                instance, kind, values = self._create(operation, instances, context)
            elif isinstance(operation, OpenActivity):
                instance, kind, values = self._open(operation, instances, context)
            elif isinstance(operation, JoinActivity):
                instance, kind, values = self._join(operation, instances, context)
            elif isinstance(operation, RecordActivityContribution):
                instance, kind, values = self._contribute(operation, instances, context)
            elif isinstance(operation, CloseActivity):
                instance, kind, values = self._close(operation, instances, context)
            elif isinstance(operation, FinalizeActivity):
                instance, kind, values = self._finalize(operation, instances)
            elif isinstance(operation, CancelActivity):
                instance, kind, values = self._cancel(operation, instances)
            else:
                raise TypeError(f"未知活动操作：{type(operation).__name__}")
            instances[instance.id] = instance
            next_state = ActivityState(state.scope_id, instances, state.revision + 1)
            event = RuleEvent.from_context(
                context,
                kind=kind,
                source_id=command.actor_id,
                target_id=instance.id,
                subject_id=instance.definition_id,
                values={"command_id": command.id, "instance_id": instance.id, **values},
            )
            return RuleOutcome.success(
                ActivityExecution(command.id, next_state, instance, (event,))
            )
        except RuleViolation as exc:
            context.random.restore(checkpoint)
            return RuleOutcome.failed(exc.failure)

    def _create(self, operation, instances, context):
        instance = operation.instance
        if instance.id in instances:
            self._fail("activity.instance_exists", "活动实例已经存在")
        definition = self.catalog.require(instance.definition_id)
        if instance.definition_version != definition.version:
            self._fail("activity.definition_version_mismatch", "活动实例定义版本不匹配")
        if instance.status is not ActivityStatus.SCHEDULED:
            self._fail("activity.invalid_initial_status", "新活动必须处于待开放状态")
        if context.logical_time > instance.opens_at:
            self._fail("activity.create_after_open", "不能在开放时间之后补建活动实例")
        return instance, "activity.created", {}

    def _open(self, operation, instances, context):
        instance = self._instance(instances, operation.instance_id)
        if instance.status is not ActivityStatus.SCHEDULED:
            self._fail("activity.not_scheduled", "只有待开放活动可以开放")
        if not instance.opens_at <= context.logical_time < instance.closes_at:
            self._fail("activity.outside_open_window", "当前不在活动开放窗口")
        instance = replace(instance, status=ActivityStatus.OPEN, revision=instance.revision + 1)
        return instance, "activity.opened", {}

    def _join(self, operation, instances, context):
        instance = self._instance(instances, operation.instance_id)
        definition = self.catalog.require(instance.definition_id)
        self._require_open(instance, context)
        participants = dict(instance.participants)
        if operation.subject_id in participants:
            self._fail("activity.already_joined", "参与主体已经加入活动")
        if definition.capacity is not None and len(participants) >= definition.capacity:
            self._fail("activity.capacity_reached", "活动参与容量已经用尽")
        participants[operation.subject_id] = ActivityParticipant(
            operation.subject_id,
            context.logical_time,
            metadata=operation.metadata,
        )
        instance = replace(
            instance,
            participants=participants,
            revision=instance.revision + 1,
        )
        return instance, "activity.participant.joined", {"subject_id": operation.subject_id}

    def _contribute(self, operation, instances, context):
        instance = self._instance(instances, operation.instance_id)
        definition = self.catalog.require(instance.definition_id)
        self._require_open(instance, context)
        participant = instance.participants.get(operation.subject_id)
        if participant is None:
            self._fail("activity.not_joined", "参与主体尚未加入活动")
        if (
            definition.maximum_attempts_per_participant is not None
            and participant.attempts >= definition.maximum_attempts_per_participant
        ):
            self._fail("activity.attempt_limit", "参与次数已经达到上限")
        current = replace(
            participant,
            contribution=participant.contribution + operation.amount,
            attempts=participant.attempts + 1,
            last_participated_at=context.logical_time,
        )
        participants = dict(instance.participants)
        participants[current.subject_id] = current
        instance = replace(instance, participants=participants, revision=instance.revision + 1)
        return instance, "activity.contribution.recorded", {
            "subject_id": current.subject_id,
            "amount": operation.amount,
            "contribution": current.contribution,
            "attempts": current.attempts,
        }

    def _close(self, operation, instances, context):
        instance = self._instance(instances, operation.instance_id)
        if instance.status is not ActivityStatus.OPEN:
            self._fail("activity.not_open", "只有开放活动可以进入结算")
        if context.logical_time < instance.closes_at:
            self._fail("activity.not_due", "活动尚未到达关闭时间")
        definition = self.catalog.require(instance.definition_id)
        participants = [
            value
            for value in instance.participants.values()
            if value.contribution >= definition.minimum_rank_contribution
        ]
        if definition.tie_breaker is ActivityTieBreaker.EARLIER_JOIN:
            participants.sort(key=lambda value: (-value.contribution, value.joined_at, value.subject_id))
        else:
            participants.sort(key=lambda value: (-value.contribution, value.subject_id))
        ranking = tuple(
            ActivityRankEntry(
                index,
                participant.subject_id,
                participant.contribution,
                participant.attempts,
                participant.joined_at,
            )
            for index, participant in enumerate(participants, 1)
        )
        instance = replace(
            instance,
            status=ActivityStatus.SETTLING,
            ranking=ranking,
            revision=instance.revision + 1,
        )
        return instance, "activity.ranking.frozen", {"ranked_count": len(ranking)}

    def _finalize(self, operation, instances):
        instance = self._instance(instances, operation.instance_id)
        if instance.status is not ActivityStatus.SETTLING:
            self._fail("activity.not_settling", "只有结算中的活动可以完成")
        instance = replace(instance, status=ActivityStatus.CLOSED, revision=instance.revision + 1)
        return instance, "activity.closed", {"ranked_count": len(instance.ranking)}

    def _cancel(self, operation, instances):
        instance = self._instance(instances, operation.instance_id)
        if instance.status not in {ActivityStatus.SCHEDULED, ActivityStatus.OPEN}:
            self._fail("activity.not_cancellable", "活动已经进入结算或终态")
        instance = replace(instance, status=ActivityStatus.CANCELLED, revision=instance.revision + 1)
        return instance, "activity.cancelled", {}

    @staticmethod
    def _require_open(instance: ActivityInstance, context: RuleContext) -> None:
        if instance.status is not ActivityStatus.OPEN:
            ActivityEngine._fail("activity.not_open", "活动当前没有开放")
        if not instance.opens_at <= context.logical_time < instance.closes_at:
            ActivityEngine._fail("activity.outside_open_window", "当前不在活动参与窗口")

    @staticmethod
    def _instance(instances, instance_id: str) -> ActivityInstance:
        instance = instances.get(instance_id)
        if instance is None:
            ActivityEngine._fail("activity.instance_unknown", "找不到活动实例")
        return instance

    @staticmethod
    def _fail(code: str, message: str, details: dict[str, object] | None = None) -> None:
        raise RuleViolation(code, message, details or {})


__all__ = ["ActivityEngine"]
