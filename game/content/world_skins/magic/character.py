"""魔法世界的人物与境界展示。"""

from game.core.gameplay import SkinEntry

from ...catalog import (
    CHARACTER_LEVEL_PROGRESSION_ID,
    DEFAULT_CHARACTER_TEMPLATE_ID,
    MORTAL_PHYSIQUE_FEATURE_ID,
    ORIGIN_HUMAN_FEATURE_ID,
)
from ..validation import build_character_realm_entries


MAGIC_CHARACTER_ENTRIES = {
    **build_character_realm_entries(
        (
            ("见习者", "见习"),
            ("魔法学徒", "学徒"),
            ("正式法师", "法师"),
            ("高阶法师", "高阶"),
            ("大法师", "大法师"),
            ("魔导师", "魔导师"),
            ("大魔导师", "大魔导"),
            ("贤者", "贤者"),
            ("法圣", "法圣"),
            ("传奇法师", "传奇"),
            ("圣域法师", "圣域"),
            ("半神法师", "半神"),
            ("神使", "神使"),
            ("神眷者", "神眷"),
            ("神裔", "神裔"),
            ("真神", "真神"),
            ("主神", "主神"),
            ("神王", "神王"),
            ("创世神", "创世"),
        )
    ),
    ORIGIN_HUMAN_FEATURE_ID: SkinEntry(name="人类"),
    MORTAL_PHYSIQUE_FEATURE_ID: SkinEntry(name="常人体魄"),
    CHARACTER_LEVEL_PROGRESSION_ID: SkinEntry(name="冒险等级"),
    DEFAULT_CHARACTER_TEMPLATE_ID: SkinEntry(name="人类冒险者"),
}


__all__ = ["MAGIC_CHARACTER_ENTRIES"]
