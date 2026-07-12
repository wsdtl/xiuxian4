"""只汇总当前已装配资产的角色贡献。"""

from __future__ import annotations

from collections.abc import Callable

from ..character import CharacterContribution
from .models import LoadoutState, STANDARD_LOADOUT_SLOT_ORDER


class LoadoutContributionAssembler:
    """武器和装备组件通过同一个解析回调接入，不互相导入。"""

    def assemble(
        self,
        loadout: LoadoutState,
        resolve: Callable[[str], CharacterContribution],
    ) -> tuple[CharacterContribution, ...]:
        contributions: list[CharacterContribution] = []
        for slot_id in STANDARD_LOADOUT_SLOT_ORDER:
            asset_id = loadout.slots.get(slot_id)
            if asset_id is None:
                continue
            contribution = resolve(asset_id)
            if contribution.source_id != asset_id:
                raise ValueError(
                    f"装配贡献来源与槽位资产不一致：{contribution.source_id} != {asset_id}"
                )
            contributions.append(contribution)
        return tuple(contributions)


__all__ = ["LoadoutContributionAssembler"]
