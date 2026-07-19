"""把物品 Ability 结果安全映射回角色持久状态。"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime
from enum import Enum
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Mapping

from ..abilities import AbilityUse
from ..character import (
    PERSISTENT_RESOURCE_IDS,
    ChangeCharacterResource,
    CharacterEngine,
    CharacterProjector,
    CharacterState,
    CharacterTransaction,
    CharacterContribution,
)
from ..context import RuleContext
from ..entity import RuleEntity
from ..errors import RuleOutcome, RuleViolation
from ..events import RuleEvent
from ..ids import StableId, stable_id
from .integration import (
    ITEM_ABILITY_COMPONENT_ID,
    InventoryAbilityExecutor,
    ItemAbilityComponent,
    ItemAbilityUse,
)
from .models import InventoryState


@dataclass(frozen=True)
class CharacterItemUse:
    """一次可持久化的物品使用请求。"""

    id: str
    actor_id: str
    target_id: str
    asset_id: str
    ability_use: AbilityUse
    reservation_id: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("id", "actor_id", "target_id", "asset_id"):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"CharacterItemUse 缺少 {field_name}")
        if self.reservation_id is not None and not self.reservation_id.strip():
            raise ValueError("CharacterItemUse.reservation_id 不能为空字符串")


@dataclass(frozen=True)
class ItemUseReceipt:
    """物品使用提交后的稳定回执，不保存展示文本。"""

    transaction_id: str
    actor_id: str
    target_id: str
    asset_id: str
    item_definition_id: StableId
    ability_id: StableId
    consumed_quantity: int
    resource_changes: Mapping[str, Mapping[StableId, float]] = field(default_factory=dict)
    replayed: bool = False

    def __post_init__(self) -> None:
        for field_name in ("transaction_id", "actor_id", "target_id", "asset_id"):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"ItemUseReceipt 缺少 {field_name}")
        object.__setattr__(
            self,
            "item_definition_id",
            stable_id(self.item_definition_id, field="item definition id"),
        )
        object.__setattr__(self, "ability_id", stable_id(self.ability_id, field="ability id"))
        if self.consumed_quantity < 0:
            raise ValueError("ItemUseReceipt.consumed_quantity 不能小于 0")
        changes = {
            str(character_id): MappingProxyType(
                {
                    stable_id(resource_id, field="persistent resource id"): float(delta)
                    for resource_id, delta in values.items()
                }
            )
            for character_id, values in self.resource_changes.items()
        }
        if any(not character_id.strip() for character_id in changes):
            raise ValueError("ItemUseReceipt.resource_changes 包含空角色 ID")
        object.__setattr__(self, "resource_changes", MappingProxyType(changes))


@dataclass(frozen=True)
class CharacterItemUseExecution:
    inventory: InventoryState
    characters: Mapping[str, CharacterState]
    receipt: ItemUseReceipt
    events: tuple[RuleEvent, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "characters", MappingProxyType(dict(self.characters)))


class CharacterItemUseEngine:
    """原子计算库存成本、Ability 结果和角色持久资源变化。"""

    def __init__(
        self,
        item_abilities: InventoryAbilityExecutor,
        characters: CharacterEngine,
        projector: CharacterProjector,
    ) -> None:
        self.item_abilities = item_abilities
        self.characters = characters
        self.projector = projector

    def execute(
        self,
        command: CharacterItemUse,
        *,
        inventory: InventoryState,
        characters: Mapping[str, CharacterState],
        contributions: Mapping[str, tuple[CharacterContribution, ...]] | None = None,
        context: RuleContext,
    ) -> RuleOutcome[CharacterItemUseExecution]:
        checkpoint = context.random.checkpoint()
        try:
            actor = self._require_character(characters, command.actor_id)
            target = self._require_character(characters, command.target_id)
            contribution_map = contributions or {}
            actor_entity = self.projector.project(
                actor,
                contributions=contribution_map.get(actor.id, ()),
            ).entity
            target_entity = (
                actor_entity
                if actor.id == target.id
                else self.projector.project(
                    target,
                    contributions=contribution_map.get(target.id, ()),
                ).entity
            )
            try:
                asset = inventory.asset(command.asset_id)
            except KeyError as exc:
                raise RuleViolation(
                    "inventory.asset_unknown",
                    "找不到要使用的物品资产",
                    {"asset_id": command.asset_id},
                ) from exc
            definition = self.item_abilities.catalog.require(asset.definition_id)
            try:
                component = definition.component(
                    ITEM_ABILITY_COMPONENT_ID,
                    ItemAbilityComponent,
                )
            except (KeyError, TypeError) as exc:
                raise RuleViolation(
                    "inventory.item_not_usable",
                    "物品没有有效的 Ability 使用组件",
                    {"asset_id": command.asset_id},
                ) from exc
            outcome = self.item_abilities.execute(
                ItemAbilityUse(
                    command.id,
                    command.asset_id,
                    command.ability_use,
                    command.reservation_id,
                ),
                inventory_state=inventory,
                actor=actor_entity,
                target=target_entity,
                context=context,
            )
            if outcome.failure:
                raise RuleViolation(
                    outcome.failure.code,
                    outcome.failure.message,
                    outcome.failure.details,
                )
            assert outcome.value is not None
            results = {command.actor_id: outcome.value.actor}
            if command.target_id != command.actor_id:
                results[command.target_id] = outcome.value.target

            next_characters = dict(characters)
            resource_changes: dict[str, Mapping[StableId, float]] = {}
            character_events: list[RuleEvent] = []
            for character_id in dict.fromkeys((command.actor_id, command.target_id)):
                previous = self._require_character(characters, character_id)
                projected = actor_entity if character_id == command.actor_id else target_entity
                result = results[character_id]
                self._require_persistable(projected, result)
                deltas = {
                    resource_id: result.resources[resource_id] - projected.resources[resource_id]
                    for resource_id in sorted(PERSISTENT_RESOURCE_IDS)
                    if result.resources[resource_id] != projected.resources[resource_id]
                }
                resource_changes[character_id] = deltas
                if not deltas:
                    continue
                character_outcome = self.characters.execute(
                    CharacterTransaction(
                        f"{command.id}:character:{character_id}",
                        command.actor_id,
                        previous.revision,
                        "character.item_use",
                        tuple(
                            ChangeCharacterResource(
                                resource_id,
                                delta,
                                "source.item_use",
                                command.id,
                            )
                            for resource_id, delta in deltas.items()
                        ),
                    ),
                    state=previous,
                    context=context,
                )
                if character_outcome.failure:
                    raise RuleViolation(
                        character_outcome.failure.code,
                        character_outcome.failure.message,
                        character_outcome.failure.details,
                    )
                assert character_outcome.value is not None
                next_characters[character_id] = character_outcome.value.state
                character_events.extend(character_outcome.value.events)

            receipt = ItemUseReceipt(
                command.id,
                command.actor_id,
                command.target_id,
                command.asset_id,
                definition.id,
                component.ability_id,
                component.consume_quantity,
                resource_changes,
            )
            return RuleOutcome.success(
                CharacterItemUseExecution(
                    outcome.value.inventory,
                    next_characters,
                    receipt,
                    (*outcome.value.events, *character_events),
                )
            )
        except RuleViolation as exc:
            context.random.restore(checkpoint)
            return RuleOutcome.failed(exc.failure)

    @staticmethod
    def _require_character(
        characters: Mapping[str, CharacterState],
        character_id: str,
    ) -> CharacterState:
        try:
            return characters[character_id]
        except KeyError as exc:
            raise RuleViolation(
                "item_use.character_unknown",
                "找不到物品使用涉及的角色",
                {"character_id": character_id},
            ) from exc

    @staticmethod
    def _require_persistable(previous: RuleEntity, current: RuleEntity) -> None:
        persistent_shape_unchanged = (
            current.id == previous.id
            and dict(current.base_attributes) == dict(previous.base_attributes)
            and current.base_tags == previous.base_tags
            and current.base_abilities == previous.base_abilities
            and current.active_effects == previous.active_effects
            and dict(current.cooldowns) == dict(previous.cooldowns)
            and set(current.resources) == set(PERSISTENT_RESOURCE_IDS)
        )
        if not persistent_shape_unchanged:
            raise RuleViolation(
                "item_use.transient_state_not_persistable",
                "该物品会产生临时战斗状态，不能写入角色长期存档",
                {"character_id": previous.id},
            )


def item_use_fingerprint(command: CharacterItemUse) -> str:
    """事务指纹只描述物品使用语义，不包含运行期 revision。"""

    encoded = json.dumps(
        _canonical(command),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(encoded.encode("utf-8")).hexdigest()


def _canonical(value: object) -> object:
    if is_dataclass(value):
        return {item.name: _canonical(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {
            str(key): _canonical(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    if isinstance(value, (set, frozenset)):
        items = [_canonical(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True))
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"物品使用指纹不支持类型：{type(value).__name__}")


__all__ = [
    "CharacterItemUse",
    "CharacterItemUseEngine",
    "CharacterItemUseExecution",
    "ItemUseReceipt",
    "item_use_fingerprint",
]
