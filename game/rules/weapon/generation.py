"""正式武器实例的受约束随机属性生成规则。"""

from __future__ import annotations

from dataclasses import dataclass

from game.core.gameplay import (
    ItemGenerationCommand,
    ItemRollState,
    ItemizationEngine,
    RuleContext,
    WeaponCatalog,
    WeaponState,
)


WEAPON_GENERATION_PROTOCOL_VERSION = "rules.weapon_generation.v1"


@dataclass(frozen=True)
class WeaponGenerationRequest:
    id: str
    asset_id: str
    definition_id: str
    content_fingerprint: str

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (
                self.id,
                self.asset_id,
                self.definition_id,
                self.content_fingerprint,
            )
        ):
            raise ValueError("武器生成请求缺少身份或内容指纹")


@dataclass(frozen=True)
class WeaponGenerationResult:
    state: WeaponState
    roll: ItemRollState


class WeaponInstanceGenerator:
    """按武器自身生成策略滚取核心特色、兼容属性与最终品质。"""

    def __init__(
        self,
        weapons: WeaponCatalog,
        itemization: ItemizationEngine,
    ) -> None:
        if not weapons.finalized:
            weapons.finalize()
        if weapons.itemization is not itemization:
            raise ValueError("武器目录与实例生成器必须使用同一个物品化引擎")
        self.weapons = weapons
        self.itemization = itemization

    def generate(
        self,
        request: WeaponGenerationRequest,
        *,
        context: RuleContext,
    ) -> WeaponGenerationResult:
        definition = self.weapons.require(request.definition_id)
        if definition.generation_profile_id is None:
            raise ValueError(f"武器 {definition.id} 是固定武器，不能随机生成")
        checkpoint = context.random.checkpoint()
        try:
            execution = self.itemization.generate(
                ItemGenerationCommand(
                    request.id,
                    definition.generation_profile_id,
                    request.content_fingerprint,
                ),
                context=context,
            )
            state = self.weapons.create_state(
                asset_id=request.asset_id,
                definition_id=definition.id,
                quality_id=execution.roll.quality_id,
                roll=execution.roll,
            )
            return WeaponGenerationResult(state, execution.roll)
        except Exception:
            context.random.restore(checkpoint)
            raise


__all__ = [
    "WEAPON_GENERATION_PROTOCOL_VERSION",
    "WeaponGenerationRequest",
    "WeaponGenerationResult",
    "WeaponInstanceGenerator",
]
