"""伙伴业务快照与幂等回执白名单。"""

from game.rules.companion import (
    CompanionInstance,
    CompanionRosterState,
    CompanionSanctuaryState,
    CompanionSanctuaryStatus,
    CompanionTrace,
)

from .models import CompanionOperationReceipt


def companion_codec_registrations() -> tuple[tuple[str, type[object]], ...]:
    return (
        ("game.companion.instance.v1", CompanionInstance),
        ("game.companion.trace.v1", CompanionTrace),
        ("game.companion.sanctuary_status.v1", CompanionSanctuaryStatus),
        ("game.companion.roster_state.v1", CompanionRosterState),
        ("game.companion.sanctuary_state.v1", CompanionSanctuaryState),
        ("game.companion.operation_receipt.v1", CompanionOperationReceipt),
    )


__all__ = ["companion_codec_registrations"]
