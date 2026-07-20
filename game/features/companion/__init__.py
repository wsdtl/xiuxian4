"""伙伴正式业务入口。"""

from .battle import CompanionSanctuaryBattleOutcome, CompanionSanctuaryBattleSimulator
from .codec import companion_codec_registrations
from .models import (
    CompanionOperationReceipt,
    CompanionOperationResult,
    CompanionStorageKinds,
    CompanionView,
)
from .service import CompanionFeature


__all__ = [
    "CompanionFeature",
    "CompanionOperationReceipt",
    "CompanionOperationResult",
    "CompanionSanctuaryBattleOutcome",
    "CompanionSanctuaryBattleSimulator",
    "CompanionStorageKinds",
    "CompanionView",
    "companion_codec_registrations",
]
