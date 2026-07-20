"""新角色模板、固定特征与一百级显式成长表。"""

from types import MappingProxyType
from typing import Iterable, Mapping

from game.core.gameplay import (
    COMBAT_ATTACK,
    COMBAT_DEFENSE,
    COMBAT_SPEED,
    HEALTH_MAXIMUM,
    SPIRIT_MAXIMUM,
    CharacterFeatureDefinition,
    CharacterTemplateDefinition,
    ContributionSpec,
    ProgressionDefinition,
    ProgressionMilestone,
    StableId,
)


ORIGIN_HUMAN_FEATURE_ID = "feature.origin_human"
MORTAL_PHYSIQUE_FEATURE_ID = "feature.physique_mortal"
BASIC_COMBAT_FEATURE_ID = "feature.basic_combat"
CHARACTER_LEVEL_PROGRESSION_ID = "progression.character_level"
DEFAULT_CHARACTER_TEMPLATE_ID = "character_template.default"

INITIAL_CORE_ATTRIBUTES: Mapping[StableId, float] = MappingProxyType(
    {
        HEALTH_MAXIMUM: 100.0,
        SPIRIT_MAXIMUM: 100.0,
        COMBAT_ATTACK: 10.0,
        COMBAT_DEFENSE: 0.0,
        COMBAT_SPEED: 100.0,
    }
)
LEVEL_CORE_ATTRIBUTE_DELTAS: Mapping[StableId, float] = MappingProxyType(
    {
        HEALTH_MAXIMUM: 10.0,
        COMBAT_ATTACK: 1.0,
    }
)


def character_level_milestone(
    level: int,
    *,
    feature_ids: Iterable[StableId] = (),
    extra_core_attribute_deltas: Mapping[StableId, float] | None = None,
) -> ProgressionMilestone:
    """生成一级标准人物成长；特殊等级可以叠加特征和额外固定值。"""

    deltas = dict(LEVEL_CORE_ATTRIBUTE_DELTAS)
    for attribute_id, value in (extra_core_attribute_deltas or {}).items():
        deltas[attribute_id] = deltas.get(attribute_id, 0.0) + float(value)
    return ProgressionMilestone(
        level=level,
        core_attribute_deltas=deltas,
        feature_ids=frozenset(feature_ids),
    )


def character_level_milestones(maximum_level: int) -> dict[int, ProgressionMilestone]:
    """生成从 2 级到指定上限的标准成长明细。"""

    if maximum_level < 1:
        raise ValueError("人物最高等级必须大于 0")
    return {
        level: character_level_milestone(level)
        for level in range(2, maximum_level + 1)
    }

# 第 n 项就是 Lv(n) 升到 Lv(n+1) 的需求。前 80 项沿用成熟曲线，
# 81 级后把单级增幅从 6% 平滑压到 2%，避免最后十级突然竖墙。
CHARACTER_LEVEL_EXPERIENCE_REQUIREMENTS = (
    720, 1632, 2715, 3959, 5356, 6901, 8591, 10422, 12390, 14495,
    16733, 19103, 21603, 24231, 26986, 29867, 32873, 36002, 39253, 42625,
    46118, 49731, 53462, 57311, 61277, 65360, 69558, 73872, 78300, 82841,
    87497, 92264, 97144, 102136, 107239, 112453, 117777, 123210, 128753,
    134405, 144822, 158671, 175260, 194555, 216664, 241750, 270025, 301724,
    337120, 376508, 420211, 468583, 522005, 580887, 645674, 716842, 794905,
    880408, 973942, 1076136, 1187655, 1309220, 1441594, 1585590, 1742063,
    1911936, 2096183, 2295838, 2511979, 2745779, 2998446, 3271278, 3565631,
    3882950, 4224731, 4592577, 4988164, 5413241, 5869658, 6359356, 6740917,
    7130392, 7526524, 7927938, 8333143, 8740541, 9148432, 9555028, 9958462,
    10356800, 10748056, 11130209, 11501215, 11859030, 12201624, 12527000,
    12833215, 13118397, 13380764,
)
CHARACTER_MAXIMUM_LEVEL = len(CHARACTER_LEVEL_EXPERIENCE_REQUIREMENTS) + 1
CHARACTER_LEVEL_CAPS = (
    *range(10, 91, 10),
    *range(91, CHARACTER_MAXIMUM_LEVEL + 1),
)

CHARACTER_FEATURES = (
    CharacterFeatureDefinition(ORIGIN_HUMAN_FEATURE_ID),
    CharacterFeatureDefinition(MORTAL_PHYSIQUE_FEATURE_ID),
    CharacterFeatureDefinition(
        BASIC_COMBAT_FEATURE_ID,
        ContributionSpec(abilities=frozenset({"ability.basic_attack"})),
    ),
)

CHARACTER_LEVEL_PROGRESSION = ProgressionDefinition(
    CHARACTER_LEVEL_PROGRESSION_ID,
    CHARACTER_LEVEL_EXPERIENCE_REQUIREMENTS,
    character_level_milestones(CHARACTER_MAXIMUM_LEVEL),
    CHARACTER_LEVEL_CAPS,
)

DEFAULT_CHARACTER_TEMPLATE = CharacterTemplateDefinition(
    DEFAULT_CHARACTER_TEMPLATE_ID,
    INITIAL_CORE_ATTRIBUTES,
    progression_ids=frozenset({CHARACTER_LEVEL_PROGRESSION_ID}),
    feature_ids=frozenset(
        {
            ORIGIN_HUMAN_FEATURE_ID,
            MORTAL_PHYSIQUE_FEATURE_ID,
            BASIC_COMBAT_FEATURE_ID,
        }
    ),
)

CHARACTER_DISPLAY_CONTENT_IDS = frozenset(
    {
        ORIGIN_HUMAN_FEATURE_ID,
        MORTAL_PHYSIQUE_FEATURE_ID,
        BASIC_COMBAT_FEATURE_ID,
        CHARACTER_LEVEL_PROGRESSION_ID,
        DEFAULT_CHARACTER_TEMPLATE_ID,
    }
)


__all__ = [
    "BASIC_COMBAT_FEATURE_ID",
    "CHARACTER_DISPLAY_CONTENT_IDS",
    "CHARACTER_FEATURES",
    "CHARACTER_LEVEL_EXPERIENCE_REQUIREMENTS",
    "CHARACTER_LEVEL_CAPS",
    "CHARACTER_MAXIMUM_LEVEL",
    "CHARACTER_LEVEL_PROGRESSION",
    "CHARACTER_LEVEL_PROGRESSION_ID",
    "DEFAULT_CHARACTER_TEMPLATE",
    "DEFAULT_CHARACTER_TEMPLATE_ID",
    "INITIAL_CORE_ATTRIBUTES",
    "LEVEL_CORE_ATTRIBUTE_DELTAS",
    "MORTAL_PHYSIQUE_FEATURE_ID",
    "ORIGIN_HUMAN_FEATURE_ID",
    "character_level_milestone",
    "character_level_milestones",
]
