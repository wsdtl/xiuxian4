"""所有战斗模式共用的战报数据入口。"""

from .codec import (
    BATTLE_REPORT_CODEC_VERSION,
    COMPRESSION_LEVEL,
    decode_segment,
    encode_segment,
)
from .events import KNOWN_BATTLE_EVENT_KINDS
from .models import (
    BattleReportDraft,
    BattleReportFrameDraft,
    BattleReportParticipantDraft,
    BattleReportReference,
    BattleReportRoundStateDraft,
    BattleReportSegmentDraft,
    BattleReportSummary,
    BattleReportTurnStateDraft,
    BattleReportTransitionDraft,
    BattleReportView,
    StoredBattleEvent,
    StoredBattleFrame,
    StoredBattleParticipant,
    StoredBattleRoundState,
    StoredBattleSegment,
    StoredBattleTurnState,
    StoredBattleTransition,
)
from .snapshot import (
    capture_battle_participant,
    capture_battle_round_states,
    capture_battle_turn_states,
    capture_battle_transitions,
)

__all__ = [
    "BATTLE_REPORT_CODEC_VERSION",
    "BattleReportDraft",
    "BattleReportFrameDraft",
    "BattleReportParticipantDraft",
    "BattleReportReference",
    "BattleReportRoundStateDraft",
    "BattleReportSegmentDraft",
    "BattleReportSummary",
    "BattleReportTurnStateDraft",
    "BattleReportTransitionDraft",
    "BattleReportView",
    "COMPRESSION_LEVEL",
    "KNOWN_BATTLE_EVENT_KINDS",
    "StoredBattleEvent",
    "StoredBattleFrame",
    "StoredBattleParticipant",
    "StoredBattleRoundState",
    "StoredBattleSegment",
    "StoredBattleTurnState",
    "StoredBattleTransition",
    "decode_segment",
    "encode_segment",
    "capture_battle_participant",
    "capture_battle_round_states",
    "capture_battle_turn_states",
    "capture_battle_transitions",
]
