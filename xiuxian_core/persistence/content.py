"""内容包运行指纹的数据库激活与显式切换。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json

from ..gameplay.content import ContentAssemblyReport

from .errors import ContentActivationMismatch, CorruptPersistenceData
from .sqlite import SqliteDatabase


@dataclass(frozen=True)
class ContentActivation:
    slot_id: str
    revision: int
    fingerprint: str
    profile_id: str
    packages: tuple[tuple[str, str], ...]
    activated_at: datetime


class ContentActivationStore:
    """正常启动只能验证；内容变化必须走显式条件切换。"""

    def __init__(self, database: SqliteDatabase) -> None:
        self.database = database

    def verify_or_initialize(
        self,
        report: ContentAssemblyReport,
        *,
        slot_id: str = "content.active",
        logical_time: datetime,
    ) -> ContentActivation:
        _validate_input(slot_id, logical_time)
        payload = _packages_payload(report)
        with self.database.unit_of_work() as uow:
            row = uow.load_content_activation(slot_id)
            if row is None:
                uow.insert_content_activation(
                    slot_id,
                    report.content_fingerprint,
                    report.active_combat_profile_id,
                    payload,
                    logical_time.isoformat(),
                )
                uow.commit()
                return ContentActivation(
                    slot_id,
                    0,
                    report.content_fingerprint,
                    report.active_combat_profile_id,
                    _package_pairs(report),
                    logical_time,
                )
            activation = _activation_from_row(row)
            if (
                activation.fingerprint != report.content_fingerprint
                or activation.profile_id != report.active_combat_profile_id
                or row.packages_payload != payload
            ):
                raise ContentActivationMismatch(
                    f"数据库内容激活指纹与当前运行期不一致：{slot_id}"
                )
            return activation

    def replace(
        self,
        report: ContentAssemblyReport,
        *,
        slot_id: str = "content.active",
        expected_revision: int,
        expected_fingerprint: str,
        logical_time: datetime,
    ) -> ContentActivation:
        _validate_input(slot_id, logical_time)
        if expected_revision < 0 or not expected_fingerprint.strip():
            raise ValueError("内容切换缺少有效预期 revision 或指纹")
        payload = _packages_payload(report)
        with self.database.unit_of_work() as uow:
            uow.compare_and_swap_content_activation(
                slot_id,
                expected_revision,
                expected_fingerprint,
                report.content_fingerprint,
                report.active_combat_profile_id,
                payload,
                logical_time.isoformat(),
            )
            uow.commit()
        return ContentActivation(
            slot_id,
            expected_revision + 1,
            report.content_fingerprint,
            report.active_combat_profile_id,
            _package_pairs(report),
            logical_time,
        )

    def require(self, *, slot_id: str = "content.active") -> ContentActivation:
        if not slot_id.strip():
            raise ValueError("内容激活槽 id 不能为空")
        with self.database.unit_of_work(write=False) as uow:
            row = uow.load_content_activation(slot_id)
            if row is None:
                raise ContentActivationMismatch(f"数据库尚未激活内容：{slot_id}")
            return _activation_from_row(row)


def _package_pairs(report: ContentAssemblyReport) -> tuple[tuple[str, str], ...]:
    return tuple((package.id, str(package.version)) for package in report.packages)


def _packages_payload(report: ContentAssemblyReport) -> str:
    return json.dumps(_package_pairs(report), ensure_ascii=True, separators=(",", ":"))


def _activation_from_row(row) -> ContentActivation:
    try:
        values = json.loads(row.packages_payload)
        packages = tuple((str(item[0]), str(item[1])) for item in values)
        activated_at = datetime.fromisoformat(row.activated_at)
        if activated_at.tzinfo is None or activated_at.utcoffset() is None:
            raise ValueError("missing timezone")
    except (IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise CorruptPersistenceData("内容激活记录无法还原") from exc
    return ContentActivation(
        row.slot_id,
        row.revision,
        row.fingerprint,
        row.profile_id,
        packages,
        activated_at,
    )


def _validate_input(slot_id: str, logical_time: datetime) -> None:
    if not slot_id.strip():
        raise ValueError("内容激活槽 id 不能为空")
    if logical_time.tzinfo is None or logical_time.utcoffset() is None:
        raise ValueError("内容激活时间必须包含时区")


__all__ = ["ContentActivation", "ContentActivationStore"]
