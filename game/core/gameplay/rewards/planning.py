"""可扩展奖励声明到既有领域事务的规划层。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Callable, Mapping

from ..character import GrantExperience, UnlockFeature, UnlockProgression
from ..economy import IssueFunds, LedgerOperation
from ..errors import RuleViolation
from ..equipment import equipment_state_data
from ..inventory import (
    AppendStack,
    GrantInstance,
    GrantStack,
    InventoryOperation,
    SourceReceipt,
)
from ..weapon import WeaponState, weapon_state_data
from .models import (
    CharacterExperienceReward,
    CharacterFeatureReward,
    CharacterProgressionReward,
    CurrencyReward,
    DuplicateUnlockPolicy,
    GeneratedEquipmentReward,
    GeneratedWeaponReward,
    InstanceItemReward,
    RewardDisposition,
    RewardLine,
    RewardSettlement,
    RewardSettlementSnapshot,
    StackItemReward,
    WeaponExperienceReward,
)


@dataclass(frozen=True)
class RewardPlan:
    inventory_operations: tuple[InventoryOperation, ...]
    ledger_operations: tuple[LedgerOperation, ...]
    character_operations: Mapping[str, tuple[object, ...]]
    weapon_experience: Mapping[str, int]
    generated_weapons: Mapping[str, WeaponState]
    lines: tuple[RewardLine, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "character_operations",
            MappingProxyType(dict(self.character_operations)),
        )
        object.__setattr__(self, "weapon_experience", MappingProxyType(dict(self.weapon_experience)))
        object.__setattr__(self, "generated_weapons", MappingProxyType(dict(self.generated_weapons)))


@dataclass
class RewardPlanBuilder:
    """扩展处理器只能向现有领域提交操作，不能直接改状态。"""

    settlement: RewardSettlement
    snapshot: RewardSettlementSnapshot
    logical_time: datetime
    inventory_operations: list[InventoryOperation] = field(default_factory=list)
    ledger_operations: list[LedgerOperation] = field(default_factory=list)
    character_operations: dict[str, list[object]] = field(default_factory=dict)
    weapon_experience: dict[str, int] = field(default_factory=dict)
    generated_weapons: dict[str, WeaponState] = field(default_factory=dict)
    lines: list[RewardLine] = field(default_factory=list)
    planned_features: set[tuple[str, str]] = field(default_factory=set)
    planned_progressions: set[tuple[str, str]] = field(default_factory=set)

    def add_inventory(self, operation: InventoryOperation, line: RewardLine) -> None:
        self.inventory_operations.append(operation)
        self.lines.append(line)

    def add_ledger(self, operation: LedgerOperation, line: RewardLine) -> None:
        self.ledger_operations.append(operation)
        self.lines.append(line)

    def add_character(self, character_id: str, operation: object, line: RewardLine) -> None:
        self.require_character(character_id)
        self.character_operations.setdefault(character_id, []).append(operation)
        self.lines.append(line)

    def add_weapon_experience(self, asset_id: str, amount: int, line: RewardLine) -> None:
        self.require_weapon(asset_id)
        self.weapon_experience[asset_id] = self.weapon_experience.get(asset_id, 0) + amount
        self.lines.append(line)

    def add_generated_weapon(
        self,
        operation: InventoryOperation,
        state: WeaponState,
        line: RewardLine,
    ) -> None:
        if state.asset_id in self.snapshot.weapons or state.asset_id in self.generated_weapons:
            self.fail("reward.weapon_exists", "生成武器资产 id 已经存在")
        self.inventory_operations.append(operation)
        self.generated_weapons[state.asset_id] = state
        self.lines.append(line)

    def skip(self, line: RewardLine) -> None:
        self.lines.append(line)

    def require_character(self, character_id: str):
        try:
            return self.snapshot.characters[character_id]
        except KeyError:
            self.fail("reward.character_unknown", "奖励引用了未知角色", {"character_id": character_id})

    def require_weapon(self, asset_id: str) -> WeaponState:
        try:
            return self.snapshot.weapons[asset_id]
        except KeyError:
            self.fail("reward.weapon_unknown", "奖励引用了未知武器", {"asset_id": asset_id})

    def require_ledger_account(self, account_id: str):
        try:
            return self.snapshot.ledger.accounts[account_id]
        except KeyError:
            self.fail("reward.ledger_account_unknown", "奖励引用了未知账本账户", {"account_id": account_id})

    def source_receipt(self, index: int, metadata: Mapping[str, object]) -> SourceReceipt:
        return SourceReceipt(
            f"{self.settlement.id}:reward:{index}",
            self.settlement.source_kind,
            self.settlement.source_id,
            self.logical_time,
            {
                "settlement_id": self.settlement.id,
                "reward_index": index,
                **metadata,
            },
        )

    def build(self) -> RewardPlan:
        return RewardPlan(
            tuple(self.inventory_operations),
            tuple(self.ledger_operations),
            {
                key: tuple(value)
                for key, value in self.character_operations.items()
            },
            self.weapon_experience,
            self.generated_weapons,
            tuple(sorted(self.lines, key=lambda value: value.index)),
        )

    @staticmethod
    def fail(code, message, details=None) -> None:
        raise RuleViolation(code, message, details or {})


RewardPlanner = Callable[[object, int, RewardPlanBuilder], None]


class RewardPlannerRegistry:
    """启动期登记奖励类型；运行期冻结，避免结算语义漂移。"""

    def __init__(self) -> None:
        self._handlers: dict[type[object], RewardPlanner] = {}
        self._finalized = False

    @classmethod
    def with_defaults(cls) -> "RewardPlannerRegistry":
        registry = cls()
        registry.register(CurrencyReward, _plan_currency)
        registry.register(StackItemReward, _plan_stack_item)
        registry.register(InstanceItemReward, _plan_instance_item)
        registry.register(CharacterExperienceReward, _plan_character_experience)
        registry.register(CharacterFeatureReward, _plan_character_feature)
        registry.register(CharacterProgressionReward, _plan_character_progression)
        registry.register(WeaponExperienceReward, _plan_weapon_experience)
        registry.register(GeneratedEquipmentReward, _plan_generated_equipment)
        registry.register(GeneratedWeaponReward, _plan_generated_weapon)
        return registry

    @property
    def finalized(self) -> bool:
        return self._finalized

    def register(self, reward_type: type[object], handler: RewardPlanner) -> None:
        if self._finalized:
            raise RuntimeError("奖励规划器已经冻结")
        if reward_type in self._handlers:
            raise ValueError(f"重复奖励规划器：{reward_type.__name__}")
        self._handlers[reward_type] = handler

    def finalize(self) -> None:
        if not self._handlers:
            raise ValueError("奖励规划器不能为空")
        self._finalized = True

    def plan(
        self,
        settlement: RewardSettlement,
        snapshot: RewardSettlementSnapshot,
        logical_time: datetime,
    ) -> RewardPlan:
        if not self._finalized:
            self.finalize()
        builder = RewardPlanBuilder(settlement, snapshot, logical_time)
        for index, reward in enumerate(settlement.rewards):
            try:
                handler = self._handlers[type(reward)]
            except KeyError:
                builder.fail(
                    "reward.type_unknown",
                    "奖励类型没有登记规划器",
                    {"reward_type": type(reward).__name__, "index": index},
                )
            handler(reward, index, builder)
        return builder.build()


def _line(index, kind, target_id, subject_id, amount, *, disposition=RewardDisposition.GRANTED):
    return RewardLine(index, kind, target_id, subject_id, amount, disposition)


def _plan_currency(reward: CurrencyReward, index: int, builder: RewardPlanBuilder) -> None:
    issuer = builder.require_ledger_account(reward.issuer_account_id)
    destination = builder.require_ledger_account(reward.destination_account_id)
    subject_id = destination.currency_id
    if issuer.currency_id != subject_id:
        builder.fail("reward.currency_mismatch", "货币奖励的发行与接收账户币种不一致")
    builder.add_ledger(
        IssueFunds(issuer.id, destination.id, reward.amount),
        _line(index, "reward.currency", destination.id, subject_id, reward.amount),
    )


def _plan_stack_item(reward: StackItemReward, index: int, builder: RewardPlanBuilder) -> None:
    existing = builder.snapshot.inventory.stacks.get(reward.asset_id)
    if existing is not None:
        if (
            existing.definition_id != reward.definition_id
            or existing.container_id != reward.container_id
        ):
            builder.fail(
                "reward.stack_identity_conflict",
                "堆叠奖励资产与既有物品身份不一致",
                {"asset_id": reward.asset_id},
            )
        operation = AppendStack(
            reward.asset_id,
            reward.quantity,
            builder.source_receipt(index, reward.metadata),
        )
    else:
        operation = GrantStack(
            reward.asset_id,
            reward.definition_id,
            reward.container_id,
            reward.quantity,
            builder.source_receipt(index, reward.metadata),
        )
    builder.add_inventory(
        operation,
        _line(index, "reward.item_stack", reward.container_id, reward.definition_id, reward.quantity),
    )


def _plan_instance_item(reward: InstanceItemReward, index: int, builder: RewardPlanBuilder) -> None:
    builder.add_inventory(
        GrantInstance(
            reward.asset_id,
            reward.definition_id,
            reward.container_id,
            builder.source_receipt(index, reward.metadata),
            reward.data,
        ),
        _line(index, "reward.item_instance", reward.container_id, reward.definition_id, 1),
    )


def _plan_generated_equipment(
    reward: GeneratedEquipmentReward,
    index: int,
    builder: RewardPlanBuilder,
) -> None:
    builder.add_inventory(
        GrantInstance(
            reward.state.asset_id,
            reward.item_definition_id,
            reward.container_id,
            builder.source_receipt(index, reward.metadata),
            equipment_state_data(reward.state),
        ),
        _line(index, "reward.generated_equipment", reward.container_id, reward.state.definition_id, 1),
    )


def _plan_generated_weapon(
    reward: GeneratedWeaponReward,
    index: int,
    builder: RewardPlanBuilder,
) -> None:
    builder.add_generated_weapon(
        GrantInstance(
            reward.state.asset_id,
            reward.item_definition_id,
            reward.container_id,
            builder.source_receipt(index, reward.metadata),
            weapon_state_data(reward.state),
        ),
        reward.state,
        _line(index, "reward.generated_weapon", reward.container_id, reward.state.definition_id, 1),
    )


def _plan_character_experience(
    reward: CharacterExperienceReward,
    index: int,
    builder: RewardPlanBuilder,
) -> None:
    builder.add_character(
        reward.character_id,
        GrantExperience(
            reward.progression_id,
            reward.amount,
            builder.settlement.source_kind,
            builder.settlement.source_id,
        ),
        _line(
            index,
            "reward.character_experience",
            reward.character_id,
            reward.progression_id,
            reward.amount,
        ),
    )


def _plan_character_feature(
    reward: CharacterFeatureReward,
    index: int,
    builder: RewardPlanBuilder,
) -> None:
    character = builder.require_character(reward.character_id)
    key = (character.id, reward.feature_id)
    already_owned = reward.feature_id in character.features or key in builder.planned_features
    line = _line(index, "reward.character_feature", character.id, reward.feature_id, 1)
    if already_owned:
        if reward.duplicate_policy is DuplicateUnlockPolicy.REJECT:
            builder.fail(
                "reward.feature_already_owned",
                "角色已经拥有奖励中的永久特征",
                {"character_id": character.id, "feature_id": reward.feature_id},
            )
        builder.skip(
            _line(
                index,
                "reward.character_feature",
                character.id,
                reward.feature_id,
                0,
                disposition=RewardDisposition.SKIPPED,
            )
        )
        return
    builder.planned_features.add(key)
    builder.add_character(
        character.id,
        UnlockFeature(reward.feature_id, builder.settlement.source_kind, builder.settlement.source_id),
        line,
    )


def _plan_character_progression(
    reward: CharacterProgressionReward,
    index: int,
    builder: RewardPlanBuilder,
) -> None:
    character = builder.require_character(reward.character_id)
    key = (character.id, reward.progression_id)
    already_owned = (
        reward.progression_id in character.progressions
        or key in builder.planned_progressions
    )
    line = _line(index, "reward.character_progression", character.id, reward.progression_id, 1)
    if already_owned:
        if reward.duplicate_policy is DuplicateUnlockPolicy.REJECT:
            builder.fail(
                "reward.progression_already_owned",
                "角色已经拥有奖励中的成长轨道",
                {"character_id": character.id, "progression_id": reward.progression_id},
            )
        builder.skip(
            _line(
                index,
                "reward.character_progression",
                character.id,
                reward.progression_id,
                0,
                disposition=RewardDisposition.SKIPPED,
            )
        )
        return
    builder.planned_progressions.add(key)
    builder.add_character(
        character.id,
        UnlockProgression(
            reward.progression_id,
            builder.settlement.source_kind,
            builder.settlement.source_id,
        ),
        line,
    )


def _plan_weapon_experience(
    reward: WeaponExperienceReward,
    index: int,
    builder: RewardPlanBuilder,
) -> None:
    builder.add_weapon_experience(
        reward.asset_id,
        reward.amount,
        _line(index, "reward.weapon_experience", reward.asset_id, reward.asset_id, reward.amount),
    )


__all__ = [
    "RewardPlan",
    "RewardPlanBuilder",
    "RewardPlanner",
    "RewardPlannerRegistry",
]
