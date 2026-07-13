"""组织、社会请求和关系状态的 SQLite 持久化。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256

from ..gameplay.context import RuleContext
from ..gameplay.errors import RuleOutcome
from ..gameplay.social import SocialCommand, SocialEngine, SocialExecution, SocialState

from .errors import TransactionMismatch
from .snapshots import SOCIAL_AGGREGATE, SnapshotRepository
from .sqlite import SqliteDatabase


@dataclass(frozen=True)
class PersistedSocialExecution:
    execution: SocialExecution
    replayed: bool = False


class PersistedSocialService:
    def __init__(
        self,
        database: SqliteDatabase,
        engine: SocialEngine,
        snapshots: SnapshotRepository | None = None,
    ) -> None:
        self.database = database
        self.engine = engine
        self.snapshots = snapshots or SnapshotRepository()

    def initialize(self, scope_id: str, *, logical_time: datetime) -> SocialState:
        _aware(logical_time)
        initial = SocialState(scope_id)
        with self.database.unit_of_work() as uow:
            current = self.snapshots.load(uow, SOCIAL_AGGREGATE, scope_id, SocialState)
            if current is None:
                self.snapshots.insert(
                    uow,
                    SOCIAL_AGGREGATE,
                    scope_id,
                    initial,
                    logical_time,
                )
                current = initial
            uow.commit()
        return current

    def load(self, scope_id: str) -> SocialState | None:
        with self.database.unit_of_work(write=False) as uow:
            return self.snapshots.load(uow, SOCIAL_AGGREGATE, scope_id, SocialState)

    def execute(
        self,
        scope_id: str,
        command: SocialCommand,
        *,
        context: RuleContext,
    ) -> RuleOutcome[PersistedSocialExecution]:
        checkpoint = context.random.checkpoint()
        try:
            with self.database.unit_of_work() as uow:
                fingerprint = self._fingerprint(scope_id, command)
                previous_tx = uow.load_transaction(command.id)
                if previous_tx is not None:
                    if previous_tx.fingerprint != fingerprint or previous_tx.scope_id != scope_id:
                        raise TransactionMismatch(
                            f"同一社会事务 ID 对应不同内容：{command.id}"
                        )
                    execution = self.snapshots.codec.loads(
                        previous_tx.receipt_payload,
                        SocialExecution,
                    )
                    return RuleOutcome.success(PersistedSocialExecution(execution, True))
                state = self.snapshots.require(
                    uow,
                    SOCIAL_AGGREGATE,
                    scope_id,
                    SocialState,
                )
                outcome = self.engine.execute(command, state=state, context=context)
                if outcome.failure:
                    return RuleOutcome.failed(outcome.failure)
                assert outcome.value is not None
                self.snapshots.update(
                    uow,
                    SOCIAL_AGGREGATE,
                    scope_id,
                    state,
                    outcome.value.state,
                    context.logical_time,
                )
                timestamp = context.logical_time.isoformat()
                uow.insert_transaction(
                    command.id,
                    fingerprint,
                    scope_id,
                    self.snapshots.codec.dumps(outcome.value),
                    timestamp,
                )
                for sequence, event in enumerate(outcome.value.events):
                    uow.append_outbox(
                        command.id,
                        sequence,
                        event.kind,
                        self.snapshots.codec.dumps(event),
                        timestamp,
                    )
                uow.commit()
                return RuleOutcome.success(PersistedSocialExecution(outcome.value))
        except Exception:
            context.random.restore(checkpoint)
            raise

    def _fingerprint(self, scope_id: str, command: SocialCommand) -> str:
        payload = "\0".join(
            ("social-command.v1", scope_id, self.snapshots.codec.dumps(command))
        )
        return sha256(payload.encode("utf-8")).hexdigest()


def _aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("社会持久化逻辑时间必须包含时区")


__all__ = ["PersistedSocialExecution", "PersistedSocialService"]
