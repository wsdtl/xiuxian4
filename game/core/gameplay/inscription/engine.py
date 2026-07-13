"""消耗铭刻之羽并原子改写物品实例展示数据。"""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json

from ..context import RuleContext
from ..errors import RuleOutcome, RuleViolation
from ..events import RuleEvent
from ..equipment import EquipmentCatalog
from ..inventory import (
    ConsumeInstance,
    InventoryEngine,
    InventoryState,
    InventoryTransaction,
    ItemAssetKind,
    ItemCatalog,
    ItemInstance,
)
from ..weapon import WeaponCatalog, WeaponContributionProvider, WeaponState
from .models import (
    INSCRIPTION_DATA_KEY,
    INSCRIPTION_MEDIUM_DATA_KEY,
    AssetInscriptionTarget,
    InscriptionCommand,
    InscriptionData,
    InscriptionExecution,
    InscriptionMediumData,
    InscriptionReceipt,
    WeaponAbilityInscriptionTarget,
    inscription_data,
)


class InscriptionEngine:
    """只允许铭刻武器、装备和具体武器实际拥有的 Ability。"""

    def __init__(
        self,
        items: ItemCatalog,
        weapons: WeaponCatalog,
        equipment: EquipmentCatalog,
    ) -> None:
        if not items.finalized:
            items.finalize()
        if not weapons.finalized:
            weapons.finalize()
        if not equipment.finalized:
            equipment.finalize()
        self.items = items
        self.weapons = weapons
        self.equipment = equipment
        self.inventory_engine = InventoryEngine(items)
        self.weapon_contributions = WeaponContributionProvider(weapons)

    def apply(
        self,
        command: InscriptionCommand,
        *,
        inventory: InventoryState,
        context: RuleContext,
        weapon_state: WeaponState | None = None,
    ) -> RuleOutcome[InscriptionExecution]:
        checkpoint = context.random.checkpoint()
        try:
            if (
                command.expected_inventory_revision is not None
                and inventory.revision != command.expected_inventory_revision
            ):
                self._fail("inscription.inventory_revision_conflict", "库存 revision 不符合预期")
            target_asset_id = self._target_asset_id(command)
            target = self._require_owned_instance(inventory, target_asset_id, command.actor_id)
            if (
                command.expected_asset_revision is not None
                and target.revision != command.expected_asset_revision
            ):
                self._fail("inscription.asset_revision_conflict", "目标资产 revision 不符合预期")
            if target.id == command.medium_asset_id:
                self._fail("inscription.target_is_medium", "铭刻目标不能是被消耗的铭刻之羽")
            medium = self._require_owned_instance(
                inventory,
                command.medium_asset_id,
                command.actor_id,
            )
            medium_definition = self.items.require(medium.definition_id)
            if (
                medium_definition.asset_kind is not ItemAssetKind.INSTANCE
                or not medium_definition.tags.has("item.inscription_medium")
            ):
                self._fail("inscription.medium_invalid", "指定物品不是铭刻之羽")
            medium_data = medium.data.get(INSCRIPTION_MEDIUM_DATA_KEY)
            if not isinstance(medium_data, InscriptionMediumData):
                self._fail("inscription.medium_data_invalid", "铭刻之羽缺少标题或故事")

            current = inscription_data(target.data.get(INSCRIPTION_DATA_KEY))
            updated = self._updated_data(
                command,
                target,
                current,
                weapon_state,
            )
            paid = self.inventory_engine.execute(
                InventoryTransaction(
                    command.id,
                    command.actor_id,
                    "inventory.inscription_cost",
                    (ConsumeInstance(command.medium_asset_id),),
                ),
                state=inventory,
                context=context,
            )
            if paid.failure:
                return RuleOutcome.failed(paid.failure)
            assert paid.value is not None
            paid_target = paid.value.state.instances[target.id]
            target_data = dict(paid_target.data)
            target_data[INSCRIPTION_DATA_KEY] = updated
            changed_target = replace(
                paid_target,
                data=target_data,
                revision=paid_target.revision + 1,
            )
            instances = dict(paid.value.state.instances)
            instances[target.id] = changed_target
            changed_inventory = InventoryState(
                paid.value.state.containers,
                paid.value.state.stacks,
                instances,
                paid.value.state.reservations,
                paid.value.state.revision,
            )
            receipt = InscriptionReceipt(
                command.id,
                command.actor_id,
                command.target,
                command.medium_asset_id,
                medium_data.title,
                medium_data.flavor_text,
                command.custom_name,
            )
            event = RuleEvent.from_context(
                context,
                kind="inscription.applied",
                source_id=command.actor_id,
                target_id=target.id,
                subject_id=(
                    command.target.ability_id
                    if isinstance(command.target, WeaponAbilityInscriptionTarget)
                    else target.definition_id
                ),
                values={
                    "transaction_id": command.id,
                    "medium_asset_id": medium.id,
                    "medium_title": medium_data.title,
                    "custom_name": command.custom_name,
                    "target_kind": (
                        "weapon_ability"
                        if isinstance(command.target, WeaponAbilityInscriptionTarget)
                        else "asset"
                    ),
                },
            )
            return RuleOutcome.success(
                InscriptionExecution(
                    changed_inventory,
                    receipt,
                    (*paid.value.events, event),
                )
            )
        except RuleViolation as exc:
            context.random.restore(checkpoint)
            return RuleOutcome.failed(exc.failure)
        except Exception:
            context.random.restore(checkpoint)
            raise

    def _updated_data(
        self,
        command: InscriptionCommand,
        target: ItemInstance,
        current: InscriptionData,
        weapon_state: WeaponState | None,
    ) -> InscriptionData:
        definition = self.items.require(target.definition_id)
        if isinstance(command.target, AssetInscriptionTarget):
            is_weapon = definition.tags.has("item.weapon") and self._has_weapon_item(
                definition.id
            )
            is_equipment = (
                definition.tags.has("item.equipment")
                and self._has_equipment_item(definition.id)
            )
            if not (is_weapon or is_equipment):
                self._fail("inscription.target_invalid", "只有武器和装备实例可以铭刻名称")
            if current.asset_name == command.custom_name:
                self._fail("inscription.name_unchanged", "目标已经使用这个铭刻名")
            return InscriptionData(command.custom_name, current.ability_names)

        if not definition.tags.has("item.weapon"):
            self._fail("inscription.ability_target_not_weapon", "Ability 铭刻目标必须是武器")
        if (
            weapon_state is None
            or weapon_state.asset_id != target.id
            or weapon_state.definition_id not in self.weapons.definitions.ids()
        ):
            self._fail("inscription.weapon_state_missing", "缺少与目标资产匹配的武器状态")
        if weapon_state.definition_id != self._weapon_definition_for_item(target.definition_id):
            self._fail("inscription.weapon_state_mismatch", "武器状态与物品实例不匹配")
        contribution = self.weapon_contributions.contribution(weapon_state).contribution
        if command.target.ability_id not in contribution.abilities:
            self._fail("inscription.ability_not_owned", "这把武器不提供指定 Ability")
        if current.ability_names.get(command.target.ability_id) == command.custom_name:
            self._fail("inscription.name_unchanged", "目标 Ability 已经使用这个铭刻名")
        names = dict(current.ability_names)
        names[command.target.ability_id] = command.custom_name
        return InscriptionData(current.asset_name, names)

    def _weapon_definition_for_item(self, item_definition_id: str) -> str:
        for definition in self.weapons.definitions:
            if definition.item_definition_id == item_definition_id:
                return definition.id
        self._fail("inscription.weapon_definition_missing", "物品实例没有对应武器定义")
        raise AssertionError("unreachable")

    def _has_weapon_item(self, item_definition_id: str) -> bool:
        return any(
            definition.item_definition_id == item_definition_id
            for definition in self.weapons.definitions
        )

    def _has_equipment_item(self, item_definition_id: str) -> bool:
        return any(
            definition.item_definition_id == item_definition_id
            for definition in self.equipment.definitions
        )

    @staticmethod
    def _target_asset_id(command: InscriptionCommand) -> str:
        if isinstance(command.target, AssetInscriptionTarget):
            return command.target.asset_id
        return command.target.weapon_asset_id

    @staticmethod
    def _require_owned_instance(
        inventory: InventoryState,
        asset_id: str,
        actor_id: str,
    ) -> ItemInstance:
        try:
            instance = inventory.instances[asset_id]
        except KeyError:
            InscriptionEngine._fail("inscription.asset_unknown", "找不到指定独立物品")
        if inventory.owner_of(instance.id) != actor_id:
            InscriptionEngine._fail("inscription.asset_not_owned", "只能使用自己拥有的资产")
        return instance

    @staticmethod
    def _fail(code: str, message: str) -> None:
        raise RuleViolation(code, message)


def inscription_fingerprint(command: InscriptionCommand) -> str:
    if isinstance(command.target, AssetInscriptionTarget):
        target = {"kind": "asset", "asset_id": command.target.asset_id}
    else:
        target = {
            "kind": "weapon_ability",
            "asset_id": command.target.weapon_asset_id,
            "ability_id": command.target.ability_id,
        }
    payload = {
        "actor_id": command.actor_id,
        "target": target,
        "medium_asset_id": command.medium_asset_id,
        "custom_name": command.custom_name,
        "expected_inventory_revision": command.expected_inventory_revision,
        "expected_asset_revision": command.expected_asset_revision,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


__all__ = ["InscriptionEngine", "inscription_fingerprint"]
