"""把 Ability 与 Trigger 组合为一次原子规则执行。"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .abilities import AbilityEngine, AbilityUse
from .context import RuleContext
from .entity import RuleEntity
from .errors import RuleOutcome, RuleViolation
from .events import RuleEvent
from .triggers import TriggerEngine


@dataclass(frozen=True)
class GameplayExecution:
    actor: RuleEntity
    target: RuleEntity
    events: tuple[RuleEvent, ...]


@dataclass(frozen=True)
class GameplayManyExecution:
    actor_id: str
    target_ids: tuple[str, ...]
    entities: Mapping[str, RuleEntity]
    events: tuple[RuleEvent, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "entities", MappingProxyType(dict(self.entities)))

    def entity(self, entity_id: str) -> RuleEntity:
        return self.entities[entity_id]


class GameplayExecutor:
    """规则内核对上层玩法提供的标准 Ability 执行入口。"""

    def __init__(self, abilities: AbilityEngine, triggers: TriggerEngine | None = None) -> None:
        self.abilities = abilities
        self.triggers = triggers

    def execute_ability(
        self,
        use: AbilityUse,
        *,
        actor: RuleEntity,
        target: RuleEntity,
        context: RuleContext,
    ) -> RuleOutcome[GameplayExecution]:
        entities = {actor.id: actor}
        if target.id != actor.id:
            entities[target.id] = target
        outcome = self.execute_ability_many(
            use,
            actor_id=actor.id,
            target_ids=(target.id,),
            entities=entities,
            context=context,
        )
        if outcome.failure:
            return RuleOutcome.failed(outcome.failure)
        assert outcome.value is not None
        return RuleOutcome.success(
            GameplayExecution(
                outcome.value.entity(actor.id),
                outcome.value.entity(target.id),
                outcome.value.events,
            )
        )

    def execute_ability_many(
        self,
        use: AbilityUse,
        *,
        actor_id: str,
        target_ids: tuple[str, ...],
        entities: Mapping[str, RuleEntity],
        context: RuleContext,
    ) -> RuleOutcome[GameplayManyExecution]:
        """在完整实体集合中原子执行一次单目标或多目标 Ability。"""

        checkpoint = context.random.checkpoint()
        try:
            event_processor = None
            if self.triggers is not None:
                trigger_session = self.triggers.session(context)

                def event_processor(events, entities):
                    result = trigger_session.process(events, entities)
                    return result.entities, result.events

            ability_result = self.abilities.execute_many(
                use,
                actor_id=actor_id,
                target_ids=target_ids,
                entities=entities,
                context=context,
                event_processor=event_processor,
            )
            return RuleOutcome.success(
                GameplayManyExecution(
                    ability_result.actor_id,
                    ability_result.target_ids,
                    ability_result.entities,
                    ability_result.events,
                )
            )
        except RuleViolation as exc:
            context.random.restore(checkpoint)
            return RuleOutcome.failed(exc.failure)


__all__ = ["GameplayExecution", "GameplayExecutor", "GameplayManyExecution"]
