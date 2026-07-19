"""抽奖玩法持久状态的结构化白名单。"""

from .models import DrawHistoryRecord, DrawHistoryState


def draw_codec_registrations() -> tuple[tuple[str, type[object]], ...]:
    return (
        ("game.draw.history_record.v1", DrawHistoryRecord),
        ("game.draw.history_state.v1", DrawHistoryState),
    )


__all__ = ["draw_codec_registrations"]
