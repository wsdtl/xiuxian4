"""所有战斗模式共用的自解释战报数据入口。"""

from .codec import (
    BATTLE_REPORT_CODEC_VERSION,
    COMPRESSION_LEVEL,
    decode_segment,
    encode_segment,
)
from .events import KNOWN_BATTLE_EVENT_KINDS
from .models import (
    BattleReportCombatantDraft,
    BattleReportDraft,
    BattleReportEffectDraft,
    BattleReportFrameDraft,
    BattleReportGear,
    BattleReportParticipantDraft,
    BattleReportReference,
    BattleReportSegmentDraft,
    BattleReportSummary,
    BattleReportTerm,
    BattleReportTransitionDraft,
    BattleReportView,
    StoredBattleCombatant,
    StoredBattleEffect,
    StoredBattleEvent,
    StoredBattleFrame,
    StoredBattleParticipant,
    StoredBattleSegment,
    StoredBattleTransition,
)
from .snapshot import BattleSnapshotProjector

__all__ = [
    "BATTLE_REPORT_CODEC_VERSION",
    "COMPRESSION_LEVEL",
    "KNOWN_BATTLE_EVENT_KINDS",
    "BattleReportCombatantDraft",
    "BattleReportDraft",
    "BattleReportEffectDraft",
    "BattleReportFrameDraft",
    "BattleReportGear",
    "BattleReportParticipantDraft",
    "BattleReportReference",
    "BattleReportSegmentDraft",
    "BattleReportSummary",
    "BattleReportTerm",
    "BattleReportTransitionDraft",
    "BattleReportView",
    "BattleSnapshotProjector",
    "StoredBattleCombatant",
    "StoredBattleEffect",
    "StoredBattleEvent",
    "StoredBattleFrame",
    "StoredBattleParticipant",
    "StoredBattleSegment",
    "StoredBattleTransition",
    "decode_segment",
    "encode_segment",
]
