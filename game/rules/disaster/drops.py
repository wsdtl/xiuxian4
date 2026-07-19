"""次元灾厄战斗掉落的纯判定规则。"""

from __future__ import annotations


DISASTER_DROP_CHANCE_SCALE = 1_000_000


def roll_draw_ticket_drop(
    random,
    *,
    chance: int,
    effective_damage: int,
    available_capacity: int,
) -> int:
    """有效伤害且库存可接收时，按内容概率判定一张抽奖签。"""

    if not 0 <= chance <= DISASTER_DROP_CHANCE_SCALE:
        raise ValueError("灾厄掉落概率超出边界")
    if effective_damage <= 0 or available_capacity <= 0 or chance == 0:
        return 0
    return int(random.randint(1, DISASTER_DROP_CHANCE_SCALE) <= chance)


__all__ = ["DISASTER_DROP_CHANCE_SCALE", "roll_draw_ticket_drop"]
