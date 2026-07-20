"""组队挑战快照类型登记。"""

from .models import (
    PartyBattleChallengeState,
    PartyBattleDailyState,
    PartyBattleOperationReceipt,
)


def party_battle_codec_registrations() -> tuple[tuple[str, type[object]], ...]:
    return (
        ("product.party_battle_challenge", PartyBattleChallengeState),
        ("product.party_battle_daily", PartyBattleDailyState),
        ("product.party_battle_operation_receipt", PartyBattleOperationReceipt),
    )


__all__ = ["party_battle_codec_registrations"]
