"""统一战报的持久化、公开读取和保留期清理。"""

from __future__ import annotations

from datetime import datetime, timedelta
import json
from secrets import token_urlsafe

from game.rules.battle_report import (
    BattleReportDraft,
    BattleReportReference,
    BattleReportSummary,
    BattleReportView,
    decode_segment,
    encode_segment,
)

from .assembly import BattleReportBuilder


DETAIL_RETENTION = timedelta(days=7)
SUMMARY_RETENTION = timedelta(days=30)


class BattleReportService:
    """一张报告主表和一张片段表承接所有战斗模式。"""

    def __init__(self, database, store, builder: BattleReportBuilder) -> None:
        self.database = database
        self.store = store
        self.builder = builder

    def capture(self, draft: BattleReportDraft) -> BattleReportReference:
        with self.database.unit_of_work() as uow:
            reference = self.capture_in_uow(uow, draft)
            uow.commit()
            return reference

    def capture_in_uow(self, uow, draft: BattleReportDraft) -> BattleReportReference:
        """与玩法结算共用工作单元，战报失败时不会留下半份结算。"""

        existing = self.store.header_in_uow(uow, draft.report_id)
        if existing is None:
            share_id = self._new_share_id(uow)
            started_at = draft.segment.started_at
            finished_at = draft.segment.finished_at
            self.store.insert_header_in_uow(
                uow,
                report_id=draft.report_id,
                share_id=share_id,
                mode_id=draft.mode_id,
                content_fingerprint=draft.content_fingerprint,
                summary_payload=_encode_summary(draft.summary),
                started_at=started_at.isoformat(),
                finished_at=finished_at.isoformat(),
                detail_expires_at=(finished_at + DETAIL_RETENTION).isoformat(),
                summary_expires_at=(finished_at + SUMMARY_RETENTION).isoformat(),
                created_at=finished_at.isoformat(),
            )
        else:
            self._validate_identity(existing, draft)
            share_id = existing.share_id

        if self.store.segment_exists_in_uow(
            uow,
            draft.report_id,
            draft.segment.segment_id,
        ):
            return BattleReportReference(draft.report_id, share_id)

        compressed, uncompressed_bytes = encode_segment(draft.segment)
        self.store.append_segment_in_uow(
            uow,
            report_id=draft.report_id,
            segment_id=draft.segment.segment_id,
            detail_payload=compressed,
            uncompressed_bytes=uncompressed_bytes,
            summary_payload=_encode_summary(draft.summary),
            started_at=draft.segment.started_at.isoformat(),
            finished_at=draft.segment.finished_at.isoformat(),
            detail_expires_at=(draft.segment.finished_at + DETAIL_RETENTION).isoformat(),
            summary_expires_at=(draft.segment.finished_at + SUMMARY_RETENTION).isoformat(),
        )
        return BattleReportReference(draft.report_id, share_id)

    def reference(self, report_id: str) -> BattleReportReference | None:
        with self.database.unit_of_work(write=False) as uow:
            return self.reference_in_uow(uow, report_id)

    def reference_in_uow(self, uow, report_id: str) -> BattleReportReference | None:
        row = self.store.header_in_uow(uow, str(report_id or "").strip())
        if row is None:
            return None
        return BattleReportReference(row.report_id, row.share_id)

    def load_public(
        self,
        share_id: str,
        *,
        logical_time: datetime,
    ) -> BattleReportView | None:
        _aware(logical_time)
        stored = self.store.load_public(
            str(share_id or "").strip(),
            logical_time=logical_time.isoformat(),
        )
        if stored is None:
            return None
        row = stored.header
        segments = tuple(decode_segment(value) for value in stored.segment_payloads)
        return BattleReportView(
            share_id=row.share_id,
            mode_id=row.mode_id,
            content_fingerprint=row.content_fingerprint,
            summary=_decode_summary(row.summary_payload),
            started_at=datetime.fromisoformat(row.started_at),
            finished_at=datetime.fromisoformat(row.finished_at),
            detail_available=stored.detail_available,
            segments=segments,
        )

    def cleanup(self, *, logical_time: datetime) -> tuple[int, int]:
        """删除七天前的明细，并在三十天后删除整份摘要。"""

        _aware(logical_time)
        return self.store.cleanup(logical_time=logical_time.isoformat())

    @staticmethod
    def _validate_identity(row, draft: BattleReportDraft) -> None:
        expected = (
            draft.mode_id,
            draft.content_fingerprint,
        )
        actual = (
            row.mode_id,
            row.content_fingerprint,
        )
        if actual != expected:
            raise ValueError("同一战报身份对应了不同模式或内容版本")

    def _new_share_id(self, uow) -> str:
        while True:
            value = token_urlsafe(18)
            if not self.store.share_id_exists_in_uow(uow, value):
                return value


def _encode_summary(summary: BattleReportSummary) -> str:
    return json.dumps(
        {
            "title": summary.title,
            "outcome": summary.outcome,
            "lines": summary.lines,
            "tone": summary.tone,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _decode_summary(payload: str) -> BattleReportSummary:
    value = json.loads(payload)
    return BattleReportSummary(
        str(value["title"]),
        str(value["outcome"]),
        tuple(str(item) for item in value.get("lines", ())),
        str(value["tone"]),
    )


def _aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("战报逻辑时间必须包含时区")


__all__ = [
    "BattleReportService",
    "DETAIL_RETENTION",
    "SUMMARY_RETENTION",
]
