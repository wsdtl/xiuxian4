"""伙伴成长类消耗品的类型化定义。"""

from __future__ import annotations

from dataclasses import dataclass

COMPANION_EXPERIENCE_ITEM_COMPONENT_ID = "item_component.use_companion_experience"


@dataclass(frozen=True)
class CompanionExperienceItemComponent:
    maximum_experience: int = 30_000

    def __post_init__(self) -> None:
        if isinstance(self.maximum_experience, bool) or not isinstance(
            self.maximum_experience,
            int,
        ):
            raise TypeError("CompanionExperienceItemComponent.maximum_experience 必须是整数")
        if self.maximum_experience < 1:
            raise ValueError("伙伴经验物品的单次经验上限必须大于 0")


__all__ = [
    "COMPANION_EXPERIENCE_ITEM_COMPONENT_ID",
    "CompanionExperienceItemComponent",
]
