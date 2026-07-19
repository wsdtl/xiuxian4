"""协议无关、可重放的战斗自动决策。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..abilities import AbilityDefinition
from ..attributes import AttributeResolver, FixedMagnitude, ResourceDefinition
from ..context import RuleContext
from ..ids import StableId, stable_id
from ..registry import DefinitionRegistry
from .targeting import TargetSelectorRegistry, TargetingContext
from .timeline import BattleAction, BattleState


BATTLE_AI_FOUNDATION_VERSION = "combat-ai.foundation.v2"


class BattleAiConditionKind(str, Enum):
    ALWAYS = "always"
    SELF_HEALTH_BELOW = "self_health_below"
    ENEMY_HEALTH_BELOW = "enemy_health_below"
    ALLY_HEALTH_BELOW = "ally_health_below"
    ROUND_AT_LEAST = "round_at_least"


@dataclass(frozen=True)
class BattleAiCondition:
    kind: BattleAiConditionKind = BattleAiConditionKind.ALWAYS
    threshold: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", BattleAiConditionKind(self.kind))
        if self.kind is BattleAiConditionKind.ROUND_AT_LEAST:
            if self.threshold < 1 or int(self.threshold) != self.threshold:
                raise ValueError("AI 回合条件必须使用大于 0 的整数")
        elif self.kind is not BattleAiConditionKind.ALWAYS and not 0 <= self.threshold <= 1:
            raise ValueError("AI 资源比例条件必须位于 0 到 1")


@dataclass(frozen=True)
class BattleAiRule:
    """一条只负责选择 Ability 和目标模式的自动行动规则。"""

    id: StableId
    ability_id: StableId
    selector_id: StableId
    priority: int = 0
    condition: BattleAiCondition = BattleAiCondition()
    maximum_targets: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="battle ai rule id"))
        object.__setattr__(self, "ability_id", stable_id(self.ability_id, field="ability id"))
        object.__setattr__(self, "selector_id", stable_id(self.selector_id, field="selector id"))
        if self.maximum_targets is not None and self.maximum_targets < 1:
            raise ValueError("AI 最大目标数必须大于 0")


class BattleAiEngine:
    """根据结构化规则选择行动，不执行 Ability 或计算伤害。"""

    def __init__(
        self,
        abilities: DefinitionRegistry[AbilityDefinition],
        attributes: AttributeResolver,
        health: ResourceDefinition,
        selectors: TargetSelectorRegistry,
    ) -> None:
        self.abilities = abilities
        self.attributes = attributes
        self.health = health
        self.selectors = selectors

    def decide(
        self,
        rules: tuple[BattleAiRule, ...],
        state: BattleState,
        actor_id: str,
        *,
        context: RuleContext,
    ) -> BattleAction | None:
        if actor_id not in state.entities or actor_id in state.inactive_ids:
            return None
        actor = state.entities[actor_id]
        candidates = tuple(
            rule
            for rule in rules
            if rule.ability_id in actor.abilities
            and actor.cooldowns.get(rule.ability_id, 0) == 0
            and self._can_pay_fixed_costs(rule.ability_id, actor.resources)
            and self._condition_allows(rule.condition, state, actor_id)
        )
        if not candidates:
            return None
        highest = max(rule.priority for rule in candidates)
        selected = context.random.choice(
            tuple(sorted((rule for rule in candidates if rule.priority == highest), key=lambda value: value.id))
        )
        targeting_context = TargetingContext(
            actor_id=actor_id,
            entities=state.entities,
            teams={key: value.team_id for key, value in state.participants.items()},
            slots={key: value.slot for key, value in state.participants.items()},
            attributes=self.attributes,
            health=self.health,
            random=context.random,
            inactive_ids=state.inactive_ids,
        )
        return BattleAction(
            action_id=f"ai:{state.battle_id}:{state.turn_number + 1}:{actor_id}:{selected.id}",
            actor_id=actor_id,
            ability_id=selected.ability_id,
            targets=self.selectors.automatic_request(
                selected.selector_id,
                targeting_context,
                maximum_targets=selected.maximum_targets,
            ),
            decision_rule_id=selected.id,
        )

    def _condition_allows(
        self,
        condition: BattleAiCondition,
        state: BattleState,
        actor_id: str,
    ) -> bool:
        if condition.kind is BattleAiConditionKind.ALWAYS:
            return True
        if condition.kind is BattleAiConditionKind.ROUND_AT_LEAST:
            return state.round_number >= int(condition.threshold)
        actor_team = state.participants[actor_id].team_id
        if condition.kind is BattleAiConditionKind.SELF_HEALTH_BELOW:
            return self._health_ratio(state, actor_id) <= condition.threshold
        relation_ids = tuple(
            entity_id
            for entity_id, participant in state.participants.items()
            if entity_id not in state.inactive_ids
            and entity_id != actor_id
            and (
                participant.team_id != actor_team
                if condition.kind is BattleAiConditionKind.ENEMY_HEALTH_BELOW
                else participant.team_id == actor_team
            )
        )
        return any(self._health_ratio(state, entity_id) <= condition.threshold for entity_id in relation_ids)

    def _health_ratio(self, state: BattleState, entity_id: str) -> float:
        entity = state.entities[entity_id]
        current = entity.resources.get(self.health.id, self.health.minimum)
        maximum = self.health.fixed_maximum
        if self.health.maximum_attribute is not None:
            maximum = entity.snapshot(self.attributes).value(self.health.maximum_attribute)
        if maximum is None or maximum <= self.health.minimum:
            return 0.0
        return max(0.0, min(1.0, (current - self.health.minimum) / (maximum - self.health.minimum)))

    def _can_pay_fixed_costs(self, ability_id: StableId, resources) -> bool:
        definition = self.abilities.require(ability_id)
        for cost in definition.costs:
            if isinstance(cost.magnitude, FixedMagnitude):
                if resources.get(cost.resource_id, 0.0) < cost.magnitude.value:
                    return False
        return True


__all__ = [
    "BATTLE_AI_FOUNDATION_VERSION",
    "BattleAiCondition",
    "BattleAiConditionKind",
    "BattleAiEngine",
    "BattleAiRule",
]
