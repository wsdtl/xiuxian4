"""把世界皮肤原名与具体资产铭刻名组合成最终展示。"""

from __future__ import annotations

from ..ids import StableId, stable_id
from ..inventory import ItemInstance
from .models import INSCRIPTION_DATA_KEY, InscriptionPreference, inscription_data


class InscriptionProjector:
    def __init__(self, preference: InscriptionPreference | None = None) -> None:
        self.preference = preference

    def asset_name(self, base_name: str, instance: ItemInstance) -> str:
        data = inscription_data(instance.data.get(INSCRIPTION_DATA_KEY))
        return self._label(base_name, data.asset_name)

    def weapon_ability_name(
        self,
        base_name: str,
        instance: ItemInstance,
        ability_id: StableId,
    ) -> str:
        ability_id = stable_id(ability_id, field="ability id")
        data = inscription_data(instance.data.get(INSCRIPTION_DATA_KEY))
        return self._label(base_name, data.ability_names.get(ability_id, ""))

    def _label(self, base_name: str, custom_name: str) -> str:
        base = str(base_name).strip()
        if not base:
            raise ValueError("世界皮肤基础名不能为空")
        if not custom_name or custom_name == base:
            return base
        show_original = self.preference is None or self.preference.show_original_name
        return f"{custom_name}（{base}）" if show_original else custom_name


__all__ = ["InscriptionProjector"]
