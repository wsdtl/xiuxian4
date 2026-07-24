"""世界志已读状态的结构化持久化注册。"""

from .models import WorldLoreState


def world_lore_codec_registrations() -> tuple[tuple[str, type[object]], ...]:
    return (("game.world_lore.state.v1", WorldLoreState),)


__all__ = ["world_lore_codec_registrations"]
