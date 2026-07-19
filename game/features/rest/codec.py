"""休息玩法持久化类型登记。"""

from game.rules.rest import RestRecoveryState


def rest_codec_registrations() -> tuple[tuple[str, type[object]], ...]:
    return (("product.rest_recovery_state", RestRecoveryState),)


__all__ = ["rest_codec_registrations"]
