"""星环界的人物与境界展示。"""

from game.core.gameplay import SkinEntry

from ...catalog import (
    CHARACTER_LEVEL_PROGRESSION_ID,
    DEFAULT_CHARACTER_TEMPLATE_ID,
    MORTAL_PHYSIQUE_FEATURE_ID,
    ORIGIN_HUMAN_FEATURE_ID,
)
from ..validation import build_character_realm_entries


STELLAR_RING_CHARACTER_ENTRIES = {
    **build_character_realm_entries(
        (
            ("新晋登记者", "登记"),
            ("见习行者", "见习"),
            ("外环行者", "外环"),
            ("内环行者", "内环"),
            ("轨道先锋", "先锋"),
            ("星港领航", "领航"),
            ("环城执事", "执事"),
            ("序列监察", "监察"),
            ("中枢仲裁", "仲裁"),
            ("天环统御", "统御"),
            ("恒星守望", "守望"),
            ("深空行者", "深空"),
            ("界门先驱", "先驱"),
            ("群星议员", "议员"),
            ("造物继承者", "继承"),
            ("协议主宰", "主宰"),
            ("星环执掌者", "执掌"),
            ("天穹奠基者", "奠基"),
            ("文明铸造者", "铸造"),
        )
    ),
    ORIGIN_HUMAN_FEATURE_ID: SkinEntry(name="人类"),
    MORTAL_PHYSIQUE_FEATURE_ID: SkinEntry(name="标准体征"),
    CHARACTER_LEVEL_PROGRESSION_ID: SkinEntry(name="行者等级"),
    DEFAULT_CHARACTER_TEMPLATE_ID: SkinEntry(name="界门行者"),
}


__all__ = ["STELLAR_RING_CHARACTER_ENTRIES"]
