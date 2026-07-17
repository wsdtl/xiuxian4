"""武器与装备实例的统一玩家展示投影。"""

from __future__ import annotations

from dataclasses import dataclass

from game.core.gameplay import (
    EquipmentState,
    InscriptionPreference,
    InscriptionProjector,
    ItemRollState,
    ItemInstance,
    SkinProjector,
    StableId,
    WeaponState,
    stable_id,
)


@dataclass(frozen=True)
class GearPresentationStyle:
    """一套世界皮肤对品质全名和评分术语的格式约定。"""

    skin_id: StableId
    skin_version: int
    name_template: str
    score_label: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "skin_id", stable_id(self.skin_id, field="skin id"))
        if self.skin_version < 1:
            raise ValueError("装备展示样式版本必须从 1 开始")
        template = self.name_template.strip()
        score_label = self.score_label.strip()
        if "{quality}" not in template or "{name}" not in template:
            raise ValueError("装备名称模板必须同时包含 {quality} 和 {name}")
        if not score_label:
            raise ValueError("装备展示缺少评分名称")
        try:
            template.format(quality="Q", name="N")
        except (KeyError, ValueError) as exc:
            raise ValueError("装备名称模板包含未知占位符") from exc
        object.__setattr__(self, "name_template", template)
        object.__setattr__(self, "score_label", score_label)

    def full_name(self, quality_name: str, definition_name: str) -> str:
        return self.name_template.format(
            quality=quality_name.strip(),
            name=definition_name.strip(),
        )


@dataclass(frozen=True)
class GearDisplay:
    """命令层可直接展示的完整物品名与非货币评分。"""

    name: str
    base_name: str
    definition_name: str
    quality_name: str
    score_label: str
    score: float | None

    @property
    def score_text(self) -> str:
        if self.score is None:
            return ""
        value = f"{self.score:.2f}".rstrip("0").rstrip(".")
        return f"{self.score_label}: {value}"


class GearProjector:
    """组合世界皮肤、品质、随机评分和实例铭刻。"""

    def __init__(
        self,
        projector: SkinProjector,
        style: GearPresentationStyle,
    ) -> None:
        if (
            projector.pack.id != style.skin_id
            or projector.pack.version != style.skin_version
        ):
            raise ValueError("装备展示样式与世界皮肤不匹配")
        self.projector = projector
        self.style = style

    def weapon(
        self,
        state: WeaponState,
        instance: ItemInstance | None = None,
        *,
        inscription_preference: InscriptionPreference | None = None,
    ) -> GearDisplay:
        return self._project(
            state.asset_id,
            state.definition_id,
            state.quality_id,
            state.roll,
            instance,
            inscription_preference,
        )

    def equipment(
        self,
        state: EquipmentState,
        instance: ItemInstance | None = None,
        *,
        inscription_preference: InscriptionPreference | None = None,
    ) -> GearDisplay:
        return self._project(
            state.asset_id,
            state.definition_id,
            state.quality_id,
            state.roll,
            instance,
            inscription_preference,
        )

    def _project(
        self,
        asset_id: str,
        definition_id: StableId,
        quality_id: StableId,
        roll: ItemRollState | None,
        instance: ItemInstance | None,
        inscription_preference: InscriptionPreference | None,
    ) -> GearDisplay:
        if instance is not None and instance.id != asset_id:
            raise ValueError("装备状态与展示实例不是同一资产")
        definition_name = self.projector.name(definition_id)
        quality_name = self.projector.name(quality_id)
        base_name = self.style.full_name(quality_name, definition_name)
        name = (
            InscriptionProjector(inscription_preference).asset_name(base_name, instance)
            if instance is not None
            else base_name
        )
        score = None if roll is None else roll.intrinsic_value.total
        return GearDisplay(
            name,
            base_name,
            definition_name,
            quality_name,
            self.style.score_label,
            score,
        )


__all__ = ["GearDisplay", "GearPresentationStyle", "GearProjector"]
