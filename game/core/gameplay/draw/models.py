"""通用抽取底座的数据模型；具体物品和展示内容由正式内容包提供。"""

from __future__ import annotations

from dataclasses import dataclass

from ..events import RuleEvent
from ..ids import StableId, stable_id
from ..inventory import InventoryState
from ..loot import (
    LootAward,
    LootCatalog,
    LootRollReceipt,
    LootState,
    LootTableDefinition,
)


DRAW_FOUNDATION_VERSION = "draw.foundation.v2"


@dataclass(frozen=True)
class DrawGuaranteeEntry:
    """保底槽触发后可以发放的一个可信奖励。"""

    id: StableId
    award_id: StableId
    weight: int = 1
    quantity: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="draw guarantee entry id"))
        object.__setattr__(
            self,
            "award_id",
            stable_id(self.award_id, field="draw guarantee award id"),
        )
        if self.weight < 1 or self.quantity < 1:
            raise ValueError("保底奖励权重和数量必须大于 0")


@dataclass(frozen=True)
class DrawGuaranteeSlotDefinition:
    """独立于普通概率表推进的追加保底槽。"""

    id: StableId
    threshold: int
    entries: tuple[DrawGuaranteeEntry, ...]
    qualifying_award_ids: frozenset[StableId] = frozenset()

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="draw guarantee slot id"))
        entries = tuple(self.entries)
        if self.threshold < 1 or not entries:
            raise ValueError("保底槽必须包含奖励且阈值大于 0")
        entry_ids = tuple(value.id for value in entries)
        if len(entry_ids) != len(set(entry_ids)):
            raise ValueError("同一保底槽的奖励条目 ID 不能重复")
        qualifying = frozenset(
            stable_id(value, field="draw qualifying award id")
            for value in self.qualifying_award_ids
        ) or frozenset(value.award_id for value in entries)
        object.__setattr__(self, "entries", entries)
        object.__setattr__(self, "qualifying_award_ids", qualifying)


@dataclass(frozen=True)
class DrawGuaranteeDecision:
    """一次抽取对一个保底槽产生的完整审计结果。"""

    slot_id: StableId
    roll_index: int
    counter_before: int
    counter_after: int
    naturally_satisfied: bool = False
    forced: bool = False
    entry_id: StableId | None = None
    award_id: StableId | None = None
    sampled: int = 0
    scale: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "slot_id", stable_id(self.slot_id, field="draw guarantee slot id"))
        if self.roll_index < 0 or self.counter_before < 0 or self.counter_after < 0:
            raise ValueError("保底判定序号或计数不能小于 0")
        if self.forced:
            if self.entry_id is None or self.award_id is None:
                raise ValueError("触发保底必须记录奖励条目和奖励身份")
            if self.sampled < 1 or self.scale < 1 or self.sampled > self.scale:
                raise ValueError("保底随机采样超出边界")
        elif any(value is not None for value in (self.entry_id, self.award_id)):
            raise ValueError("未触发保底不能携带保底奖励")
        if self.entry_id is not None:
            object.__setattr__(self, "entry_id", stable_id(self.entry_id, field="draw guarantee entry id"))
        if self.award_id is not None:
            object.__setattr__(self, "award_id", stable_id(self.award_id, field="draw guarantee award id"))


@dataclass(frozen=True)
class DrawPoolDefinition:
    """一个抽取池的可信边界。奖项只能来自声明过的奖励身份。"""

    id: StableId
    version: int
    ticket_item_id: StableId
    loot_table_id: StableId
    award_ids: frozenset[StableId]
    guarantee_slots: tuple[DrawGuaranteeSlotDefinition, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="draw pool id"))
        object.__setattr__(
            self,
            "ticket_item_id",
            stable_id(self.ticket_item_id, field="draw ticket item id"),
        )
        object.__setattr__(
            self,
            "loot_table_id",
            stable_id(self.loot_table_id, field="draw loot table id"),
        )
        awards = frozenset(
            stable_id(value, field="draw award id") for value in self.award_ids
        )
        if self.version < 1 or not awards:
            raise ValueError("抽取池版本必须大于 0 且至少声明一个奖励奖项")
        if self.ticket_item_id in awards:
            raise ValueError("抽取池不能把自己的抽取签作为奖励")
        slots = tuple(self.guarantee_slots)
        slot_ids = tuple(value.id for value in slots)
        if len(slot_ids) != len(set(slot_ids)):
            raise ValueError("同一抽取池的保底槽 ID 不能重复")
        for slot in slots:
            referenced = slot.qualifying_award_ids | frozenset(
                value.award_id for value in slot.entries
            )
            if not referenced.issubset(awards):
                raise ValueError(f"保底槽 {slot.id} 引用了抽取池外奖励")
        object.__setattr__(self, "award_ids", awards)
        object.__setattr__(self, "guarantee_slots", slots)

    def validate_table(self, table: LootTableDefinition) -> None:
        """启动期检查奖池表，禁止空结果或越界奖励混入。"""

        if table.id != self.loot_table_id:
            raise ValueError("抽取池绑定了错误的掉落表")
        for group in table.groups:
            for entry in group.entries:
                if entry.award_id is None:
                    raise ValueError(f"抽取池 {self.id} 不能包含空奖项：{entry.id}")
                if entry.award_id not in self.award_ids:
                    raise ValueError(
                        f"抽取池 {self.id} 的奖励不在可信名录中：{entry.award_id}"
                    )


class DrawPoolCatalog:
    """启动期冻结的抽取池名录。"""

    def __init__(self) -> None:
        self._definitions: dict[StableId, DrawPoolDefinition] = {}
        self._finalized = False

    def register(self, definition: DrawPoolDefinition) -> DrawPoolDefinition:
        if self._finalized:
            raise RuntimeError("抽取池名录已经冻结")
        if definition.id in self._definitions:
            raise ValueError(f"抽取池 ID 重复：{definition.id}")
        self._definitions[definition.id] = definition
        return definition

    def require(self, pool_id: StableId) -> DrawPoolDefinition:
        key = stable_id(pool_id, field="draw pool id")
        try:
            return self._definitions[key]
        except KeyError as exc:
            raise KeyError(f"未知抽取池：{key}") from exc

    def finalize(self, *, loot_tables: LootCatalog) -> None:
        if self._finalized:
            return
        for definition in self._definitions.values():
            try:
                table = loot_tables.require(definition.loot_table_id)
            except KeyError as exc:
                raise ValueError(
                    f"抽取池 {definition.id} 引用了未知掉落表：{definition.loot_table_id}"
                ) from exc
            definition.validate_table(table)
        self._finalized = True

    @property
    def finalized(self) -> bool:
        return self._finalized

    def ids(self) -> tuple[StableId, ...]:
        return tuple(sorted(self._definitions))


@dataclass(frozen=True)
class DrawCommand:
    id: str
    actor_id: str
    pool_id: StableId
    expected_loot_revision: int
    rolls: int = 1

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.actor_id.strip():
            raise ValueError("DrawCommand 缺少身份")
        object.__setattr__(self, "pool_id", stable_id(self.pool_id, field="draw pool id"))
        if self.expected_loot_revision < 0 or not 1 <= self.rolls <= 100:
            raise ValueError("抽取 revision 或批量次数无效")


@dataclass(frozen=True)
class DrawReceipt:
    command_id: str
    actor_id: str
    pool_id: StableId
    pool_version: int
    ticket_item_id: StableId
    rolls: int
    awards: tuple[LootAward, ...]
    loot_receipt: LootRollReceipt
    guarantee_decisions: tuple[DrawGuaranteeDecision, ...] = ()

    def __post_init__(self) -> None:
        if not self.command_id.strip() or not self.actor_id.strip() or self.rolls < 1:
            raise ValueError("抽取凭据身份或次数无效")
        object.__setattr__(self, "pool_id", stable_id(self.pool_id, field="draw pool id"))
        object.__setattr__(
            self,
            "ticket_item_id",
            stable_id(self.ticket_item_id, field="draw ticket item id"),
        )
        object.__setattr__(self, "awards", tuple(self.awards))
        object.__setattr__(self, "guarantee_decisions", tuple(self.guarantee_decisions))


@dataclass(frozen=True)
class DrawExecution:
    loot_state: LootState
    receipt: DrawReceipt
    events: tuple[RuleEvent, ...]


@dataclass(frozen=True)
class DrawInventoryCommand:
    draw: DrawCommand
    ticket_asset_id: str
    destination_container_id: str
    expected_inventory_revision: int

    def __post_init__(self) -> None:
        if not self.ticket_asset_id.strip() or not self.destination_container_id.strip():
            raise ValueError("库存抽取命令缺少签资产或目标容器")
        if self.expected_inventory_revision < 0:
            raise ValueError("库存抽取 revision 不能小于 0")


@dataclass(frozen=True)
class DrawItemAward:
    definition_id: StableId
    quantity: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "definition_id",
            stable_id(self.definition_id, field="draw award item id"),
        )
        if self.quantity < 1:
            raise ValueError("抽取物品奖励数量必须大于 0")


@dataclass(frozen=True)
class DrawInventoryReceipt:
    draw: DrawReceipt
    inventory_transaction_id: str
    ticket_asset_id: str
    ticket_quantity: int
    awards: tuple[DrawItemAward, ...]

    def __post_init__(self) -> None:
        if not self.inventory_transaction_id.strip() or not self.ticket_asset_id.strip():
            raise ValueError("库存抽取凭据缺少事务或签资产身份")
        if self.ticket_quantity < 1 or not self.awards:
            raise ValueError("库存抽取凭据缺少消耗数量或奖励")
        object.__setattr__(self, "awards", tuple(self.awards))


@dataclass(frozen=True)
class DrawInventoryExecution:
    inventory_state: InventoryState
    loot_state: LootState
    receipt: DrawInventoryReceipt
    events: tuple[RuleEvent, ...]


__all__ = [
    "DRAW_FOUNDATION_VERSION",
    "DrawCommand",
    "DrawExecution",
    "DrawGuaranteeDecision",
    "DrawGuaranteeEntry",
    "DrawGuaranteeSlotDefinition",
    "DrawInventoryCommand",
    "DrawInventoryExecution",
    "DrawInventoryReceipt",
    "DrawItemAward",
    "DrawPoolCatalog",
    "DrawPoolDefinition",
    "DrawReceipt",
]
