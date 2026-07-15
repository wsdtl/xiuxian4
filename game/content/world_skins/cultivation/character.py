"""基础修仙界的人物与境界展示。"""

from game.core.gameplay import SkinEntry

from ...catalog import (
    CHARACTER_LEVEL_PROGRESSION_ID,
    DEFAULT_CHARACTER_TEMPLATE_ID,
    MORTAL_PHYSIQUE_FEATURE_ID,
    ORIGIN_HUMAN_FEATURE_ID,
)
from ..validation import build_character_realm_entries


CULTIVATION_CHARACTER_ENTRIES = {
    **build_character_realm_entries(
        (
            ("未入道", "未入道"),
            ("炼气境", "炼气"),
            ("筑基境", "筑基"),
            ("金丹境", "金丹"),
            ("元婴境", "元婴"),
            ("化神境", "化神"),
            ("炼虚境", "炼虚"),
            ("合体境", "合体"),
            ("大乘境", "大乘"),
            ("渡劫境", "渡劫"),
            ("人仙境", "人仙"),
            ("地仙境", "地仙"),
            ("天仙境", "天仙"),
            ("真仙境", "真仙"),
            ("玄仙境", "玄仙"),
            ("金仙境", "金仙"),
            ("太乙金仙", "太乙金仙"),
            ("大罗金仙", "大罗金仙"),
            ("混元道祖", "混元道祖"),
        )
    ),
    ORIGIN_HUMAN_FEATURE_ID: SkinEntry(name="人族"),
    MORTAL_PHYSIQUE_FEATURE_ID: SkinEntry(name="凡体"),
    CHARACTER_LEVEL_PROGRESSION_ID: SkinEntry(name="修为等级"),
    DEFAULT_CHARACTER_TEMPLATE_ID: SkinEntry(name="凡尘修士"),
}


__all__ = ["CULTIVATION_CHARACTER_ENTRIES"]
