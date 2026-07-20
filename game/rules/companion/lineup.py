"""角色当前配装与独占伙伴的统一战斗阵容投影。"""

from __future__ import annotations

from dataclasses import dataclass

from game.core.gameplay import BattleAiRule, RuleEntity, TagSet

from .models import CompanionRosterState
from .projection import CompanionCombatProjection, CompanionCombatProjector


@dataclass(frozen=True)
class PlayerBattleLineup:
    """所有真实玩家战斗模式共用的角色侧阵容。"""

    player: object
    companion: CompanionCombatProjection | None = None

    @property
    def entities(self) -> dict[str, RuleEntity]:
        values = {self.player.character_id: self.player.entity}
        if self.companion is not None:
            values[self.companion.companion_id] = self.companion.entity
        return values

    @property
    def participant_ids(self) -> tuple[str, ...]:
        values = [self.player.character_id]
        if self.companion is not None:
            values.append(self.companion.companion_id)
        return tuple(values)


class PlayerBattleLineupProjector:
    """集中决定当前激活配装应带哪一只伙伴进入战斗。"""

    def __init__(
        self,
        content,
        player_combat,
        companion_combat: CompanionCombatProjector,
    ) -> None:
        self.content = content
        self.player_combat = player_combat
        self.companion_combat = companion_combat

    def project(
        self,
        character,
        inventory,
        loadout,
        roster: CompanionRosterState | None,
        *,
        context_tags: TagSet = TagSet(),
    ) -> PlayerBattleLineup:
        player = self.player_combat.project(
            character,
            inventory,
            loadout,
            context_tags=context_tags,
        )
        companion = None
        if roster is not None:
            instance = roster.companion_for_preset(loadout.active_preset_id)
            if instance is not None:
                companion = self.companion_combat.project(
                    instance,
                    context_tags=context_tags,
                )
        return PlayerBattleLineup(player, companion)

    def ai_rules(self, lineup: PlayerBattleLineup) -> dict[str, tuple[BattleAiRule, ...]]:
        rules = {
            lineup.player.character_id: automatic_player_ai_rules(
                lineup.player.entity,
                self.content,
            )
        }
        if lineup.companion is not None:
            rules[lineup.companion.companion_id] = lineup.companion.ai_rules
        return rules


def automatic_player_ai_rules(entity: RuleEntity, content) -> tuple[BattleAiRule, ...]:
    """为真实角色从当前生效能力构造统一自动行动规则。"""

    rules = []
    for ability_id in sorted(entity.abilities):
        targeting = content.battle_ability_targeting.get(ability_id)
        if targeting is None:
            continue
        selectors = tuple(
            value
            for value in sorted(targeting.allowed_selectors)
            if value != "target.enemy.explicit"
        )
        if not selectors:
            continue
        selector = (
            "target.enemy.first"
            if "target.enemy.first" in selectors
            else selectors[0]
        )
        rule_suffix = str(ability_id).removeprefix("ability.")
        rules.append(
            BattleAiRule(
                f"ai.player.{rule_suffix}",
                ability_id,
                selector,
                priority=0 if ability_id == "ability.basic_attack" else 10,
                maximum_targets=targeting.maximum_targets,
            )
        )
    if not rules:
        raise ValueError("角色当前没有可用于自动战斗的能力")
    return tuple(rules)


__all__ = [
    "PlayerBattleLineup",
    "PlayerBattleLineupProjector",
    "automatic_player_ai_rules",
]
