"""伙伴业务快照与幂等回执白名单。"""

from game.rules.companion import (
    CompanionAcquisitionKind,
    CompanionInstance,
    CompanionKind,
    CompanionRosterState,
    CompanionSanctuaryState,
    CompanionSanctuaryStatus,
    CompanionTrace,
    PersonBondState,
)

from .models import CompanionOperationReceipt


def companion_codec_registrations() -> tuple[tuple[str, type[object]], ...]:
    return (
        ("game.companion.acquisition_kind.v1", CompanionAcquisitionKind),
        ("game.companion.kind.v1", CompanionKind),
        ("game.companion.instance.v2", CompanionInstance),
        ("game.companion.person_bond.v1", PersonBondState),
        ("game.companion.trace.v1", CompanionTrace),
        ("game.companion.sanctuary_status.v1", CompanionSanctuaryStatus),
        ("game.companion.roster_state.v2", CompanionRosterState),
        ("game.companion.sanctuary_state.v1", CompanionSanctuaryState),
        ("game.companion.operation_receipt.v1", CompanionOperationReceipt),
    )


__all__ = ["companion_codec_registrations"]
