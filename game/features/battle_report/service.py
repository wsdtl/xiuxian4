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


DETAIL_RETENTION = timedelta(days=7)
SUMMARY_RETENTION = timedelta(days=30)


class BattleReportService:
    """一张报告主表和一张片段表承接所有战斗模式。"""

    def __init__(self, database) -> None:
        self.database = database

    def capture(self, draft: BattleReportDraft) -> BattleReportReference:
        with self.database.unit_of_work() as uow:
            reference = self.capture_in_uow(uow, draft)
            uow.commit()
            return reference

    def capture_in_uow(self, uow, draft: BattleReportDraft) -> BattleReportReference:
        """与玩法结算共用工作单元，战报失败时不会留下半份结算。"""

        existing = uow.connection.execute(
            """
            SELECT report_id, share_id, mode_id, presentation_skin_id,
                   presentation_skin_version, content_fingerprint
            FROM battle_report
            WHERE report_id = ?
            """,
            (draft.report_id,),
        ).fetchone()
        if existing is None:
            share_id = self._new_share_id(uow)
            started_at = draft.segment.started_at
            finished_at = draft.segment.finished_at
            uow.connection.execute(
                """
                INSERT INTO battle_report(
                    report_id, share_id, mode_id, presentation_skin_id,
                    presentation_skin_version, content_fingerprint,
                    summary_payload, started_at, finished_at,
                    detail_expires_at, summary_expires_at,
                    uncompressed_bytes, compressed_bytes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?)
                """,
                (
                    draft.report_id,
                    share_id,
                    draft.mode_id,
                    draft.presentation_skin_id,
                    draft.presentation_skin_version,
                    draft.content_fingerprint,
                    _encode_summary(draft.summary),
                    started_at.isoformat(),
                    finished_at.isoformat(),
                    (finished_at + DETAIL_RETENTION).isoformat(),
                    (finished_at + SUMMARY_RETENTION).isoformat(),
                    finished_at.isoformat(),
                ),
            )
        else:
            self._validate_identity(existing, draft)
            share_id = str(existing["share_id"])

        duplicate = uow.connection.execute(
            """
            SELECT 1 FROM battle_report_segment
            WHERE report_id = ? AND segment_id = ?
            """,
            (draft.report_id, draft.segment.segment_id),
        ).fetchone()
        if duplicate is not None:
            return BattleReportReference(draft.report_id, share_id)

        sequence = int(
            uow.connection.execute(
                """
                SELECT COALESCE(MAX(sequence), -1) + 1
                FROM battle_report_segment
                WHERE report_id = ?
                """,
                (draft.report_id,),
            ).fetchone()[0]
        )
        compressed, uncompressed_bytes = encode_segment(draft.segment)
        uow.connection.execute(
            """
            INSERT INTO battle_report_segment(
                report_id, sequence, segment_id, detail_payload,
                uncompressed_bytes, compressed_bytes
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                draft.report_id,
                sequence,
                draft.segment.segment_id,
                compressed,
                uncompressed_bytes,
                len(compressed),
            ),
        )
        uow.connection.execute(
            """
            UPDATE battle_report
            SET summary_payload = ?,
                started_at = MIN(started_at, ?),
                finished_at = MAX(finished_at, ?),
                detail_expires_at = MAX(detail_expires_at, ?),
                summary_expires_at = MAX(summary_expires_at, ?),
                uncompressed_bytes = uncompressed_bytes + ?,
                compressed_bytes = compressed_bytes + ?
            WHERE report_id = ?
            """,
            (
                _encode_summary(draft.summary),
                draft.segment.started_at.isoformat(),
                draft.segment.finished_at.isoformat(),
                (draft.segment.finished_at + DETAIL_RETENTION).isoformat(),
                (draft.segment.finished_at + SUMMARY_RETENTION).isoformat(),
                uncompressed_bytes,
                len(compressed),
                draft.report_id,
            ),
        )
        return BattleReportReference(draft.report_id, share_id)

    def reference(self, report_id: str) -> BattleReportReference | None:
        with self.database.unit_of_work(write=False) as uow:
            row = uow.connection.execute(
                "SELECT report_id, share_id FROM battle_report WHERE report_id = ?",
                (report_id,),
            ).fetchone()
        if row is None:
            return None
        return BattleReportReference(str(row["report_id"]), str(row["share_id"]))

    def load_public(
        self,
        share_id: str,
        *,
        logical_time: datetime,
    ) -> BattleReportView | None:
        _aware(logical_time)
        with self.database.unit_of_work(write=False) as uow:
            row = uow.connection.execute(
                """
                SELECT share_id, mode_id, presentation_skin_id,
                       presentation_skin_version, content_fingerprint,
                       summary_payload, started_at, finished_at,
                       detail_expires_at, summary_expires_at
                FROM battle_report
                WHERE share_id = ?
                """,
                (str(share_id or "").strip(),),
            ).fetchone()
            if row is None or logical_time >= datetime.fromisoformat(row["summary_expires_at"]):
                return None
            detail_available = logical_time < datetime.fromisoformat(row["detail_expires_at"])
            segments = ()
            if detail_available:
                segment_rows = uow.connection.execute(
                    """
                    SELECT detail_payload
                    FROM battle_report_segment
                    WHERE report_id = (
                        SELECT report_id FROM battle_report WHERE share_id = ?
                    )
                    ORDER BY sequence
                    """,
                    (share_id,),
                ).fetchall()
                segments = tuple(decode_segment(bytes(item[0])) for item in segment_rows)
        return BattleReportView(
            share_id=str(row["share_id"]),
            mode_id=str(row["mode_id"]),
            presentation_skin_id=str(row["presentation_skin_id"]),
            presentation_skin_version=int(row["presentation_skin_version"]),
            content_fingerprint=str(row["content_fingerprint"]),
            summary=_decode_summary(str(row["summary_payload"])),
            started_at=datetime.fromisoformat(row["started_at"]),
            finished_at=datetime.fromisoformat(row["finished_at"]),
            detail_available=detail_available,
            segments=segments,
        )

    def cleanup(self, *, logical_time: datetime) -> tuple[int, int]:
        """删除七天前的明细，并在三十天后删除整份摘要。"""

        _aware(logical_time)
        now = logical_time.isoformat()
        with self.database.unit_of_work() as uow:
            detail = uow.connection.execute(
                """
                DELETE FROM battle_report_segment
                WHERE report_id IN (
                    SELECT report_id FROM battle_report WHERE detail_expires_at <= ?
                )
                """,
                (now,),
            ).rowcount
            summaries = uow.connection.execute(
                "DELETE FROM battle_report WHERE summary_expires_at <= ?",
                (now,),
            ).rowcount
            uow.commit()
        return int(detail), int(summaries)

    @staticmethod
    def _validate_identity(row, draft: BattleReportDraft) -> None:
        expected = (
            draft.mode_id,
            draft.presentation_skin_id,
            draft.presentation_skin_version,
            draft.content_fingerprint,
        )
        actual = (
            str(row["mode_id"]),
            str(row["presentation_skin_id"]),
            int(row["presentation_skin_version"]),
            str(row["content_fingerprint"]),
        )
        if actual != expected:
            raise ValueError("同一战报身份对应了不同模式、皮肤或内容版本")

    @staticmethod
    def _new_share_id(uow) -> str:
        while True:
            value = token_urlsafe(18)
            exists = uow.connection.execute(
                "SELECT 1 FROM battle_report WHERE share_id = ?",
                (value,),
            ).fetchone()
            if exists is None:
                return value


def _encode_summary(summary: BattleReportSummary) -> str:
    return json.dumps(
        {
            "title": summary.title,
            "outcome": summary.outcome,
            "lines": summary.lines,
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
    )


def _aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("战报逻辑时间必须包含时区")


__all__ = [
    "BattleReportService",
    "DETAIL_RETENTION",
    "SUMMARY_RETENTION",
]
