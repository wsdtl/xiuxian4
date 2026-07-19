"""次元灾厄业务快照的类型登记。"""

from game.rules.disaster import (
    DimensionalDisasterOutcome,
    DimensionalDisasterState,
    DimensionalDisasterStatus,
    DisasterChallengeReceipt,
    DisasterCombatSnapshot,
    DisasterNarrativeSnapshot,
)


def dimensional_disaster_codec_registrations() -> tuple[tuple[str, type[object]], ...]:
    return (
        ("product.disaster_status", DimensionalDisasterStatus),
        ("product.disaster_outcome", DimensionalDisasterOutcome),
        ("product.disaster_narrative", DisasterNarrativeSnapshot),
        ("product.disaster_combat", DisasterCombatSnapshot),
        ("product.disaster_challenge_receipt", DisasterChallengeReceipt),
        ("product.dimensional_disaster_state", DimensionalDisasterState),
    )


__all__ = ["dimensional_disaster_codec_registrations"]
