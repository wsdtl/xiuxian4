"""世界行纪持久状态的结构化白名单。"""

from game.rules.world_progress import WorldProgressState


def world_progress_codec_registrations() -> tuple[tuple[str, type[object]], ...]:
    return (("game.world_progress.state.v1", WorldProgressState),)


__all__ = ["world_progress_codec_registrations"]
