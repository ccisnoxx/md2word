# File: app/domains/files/storage_usage.py
# Purpose: Build read-only document_files storage usage and reclaim-readiness summaries.

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from app.domains.files.models import DocumentFileRecord
from app.domains.files.repository import DocumentFileRepositoryProtocol
from app.domains.jobs.models import utc_now


STORAGE_USAGE_RECLAIM_SUPPORTED_PROVIDERS = {"local_file", "local_object"}
FileStorageQuotaStatus = Literal["not_configured", "ok", "warning", "exceeded"]


@dataclass(slots=True)
class FileStorageUsageGroup:
    """按 provider、file_type 或 status 聚合的 metadata-estimated 使用量。"""

    key: str
    file_count: int = 0
    size_bytes: int = 0
    expired_count: int = 0
    expired_size_bytes: int = 0
    estimated_reclaimable_count: int = 0
    estimated_reclaimable_size_bytes: int = 0

    def add_record(self, record: DocumentFileRecord, *, is_time_expired: bool, is_reclaimable: bool) -> None:
        """累加单条 document_file metadata；不读取或验证对象内容。"""

        size_bytes = max(0, record.size_bytes)
        self.file_count += 1
        self.size_bytes += size_bytes
        if is_time_expired and record.status != "deleted":
            self.expired_count += 1
            self.expired_size_bytes += size_bytes
        if is_reclaimable:
            self.estimated_reclaimable_count += 1
            self.estimated_reclaimable_size_bytes += size_bytes

    def to_dict(self) -> dict[str, Any]:
        """转换为 API schema 可验证的普通字典。"""

        return {
            "key": self.key,
            "file_count": self.file_count,
            "size_bytes": self.size_bytes,
            "expired_count": self.expired_count,
            "expired_size_bytes": self.expired_size_bytes,
            "estimated_reclaimable_count": self.estimated_reclaimable_count,
            "estimated_reclaimable_size_bytes": self.estimated_reclaimable_size_bytes,
        }


@dataclass(frozen=True, slots=True)
class FileStorageUsageReport:
    """document_files storage usage read-only 汇总。"""

    generated_at: datetime
    artifact_storage: str
    artifact_root_writable: bool | None
    artifact_disk_free_bytes: int | None
    totals: dict[str, int]
    reclaim: dict[str, int | str]
    quota: dict[str, int | float | bool | str | None]
    by_storage_provider: list[FileStorageUsageGroup]
    by_file_type: list[FileStorageUsageGroup]
    by_status: list[FileStorageUsageGroup]

    def to_dict(self) -> dict[str, Any]:
        """转换为稳定 API 响应字典，保留 metadata-only 估算语义。"""

        return {
            "generated_at": self.generated_at,
            "artifact_storage": self.artifact_storage,
            "artifact_root_writable": self.artifact_root_writable,
            "artifact_disk_free_bytes": self.artifact_disk_free_bytes,
            "totals": self.totals,
            "reclaim": self.reclaim,
            "quota": self.quota,
            "by_storage_provider": [group.to_dict() for group in self.by_storage_provider],
            "by_file_type": [group.to_dict() for group in self.by_file_type],
            "by_status": [group.to_dict() for group in self.by_status],
        }


class DocumentFileStorageUsageReporter:
    """只读汇总 document_files 使用量和回收机会，不触发任何清理动作。"""

    def __init__(
        self,
        repository: DocumentFileRepositoryProtocol,
        *,
        artifact_storage: str,
        artifact_root_writable: bool | None = None,
        artifact_disk_free_bytes: int | None = None,
        quota_bytes: int | None = None,
        warning_threshold_ratio: float | None = None,
    ) -> None:
        self.repository = repository
        self.artifact_storage = artifact_storage
        self.artifact_root_writable = artifact_root_writable
        self.artifact_disk_free_bytes = artifact_disk_free_bytes
        self.quota_bytes = quota_bytes
        self.warning_threshold_ratio = warning_threshold_ratio

    def build_report(self, *, now: datetime | None = None) -> FileStorageUsageReport:
        """生成 metadata-estimated 使用量报告；不会读取文件内容或修改 metadata。"""

        generated_at = _normalize_datetime(now or utc_now())
        totals = {
            "files_seen": 0,
            "active_files": 0,
            "expired_files": 0,
            "deleted_files": 0,
            "total_size_bytes": 0,
            "active_size_bytes": 0,
            "expired_size_bytes": 0,
            "deleted_metadata_size_bytes": 0,
        }
        reclaim = {
            "estimated_reclaimable_files": 0,
            "estimated_reclaimable_size_bytes": 0,
            "unsupported_storage_files": 0,
            "unsupported_storage_size_bytes": 0,
            "blocked_missing_object_key_files": 0,
            "blocked_missing_object_key_size_bytes": 0,
            "blocked_not_expired_status_files": 0,
            "blocked_not_expired_status_size_bytes": 0,
            "deleted_metadata_files": 0,
            "deleted_metadata_size_bytes": 0,
            "estimation_basis": "metadata_only",
        }
        by_provider: dict[str, FileStorageUsageGroup] = {}
        by_file_type: dict[str, FileStorageUsageGroup] = {}
        by_status: dict[str, FileStorageUsageGroup] = {}

        for record in self.repository.list_document_files():
            size_bytes = max(0, record.size_bytes)
            is_time_expired = _is_time_expired(record, generated_at)
            is_reclaimable = _is_estimated_reclaimable(record, is_time_expired=is_time_expired)
            self._add_totals(record, totals=totals, size_bytes=size_bytes, is_time_expired=is_time_expired)
            self._add_reclaim(record, reclaim=reclaim, size_bytes=size_bytes, is_time_expired=is_time_expired)
            self._group(by_provider, record.storage_provider).add_record(
                record,
                is_time_expired=is_time_expired,
                is_reclaimable=is_reclaimable,
            )
            self._group(by_file_type, record.file_type).add_record(
                record,
                is_time_expired=is_time_expired,
                is_reclaimable=is_reclaimable,
            )
            self._group(by_status, record.status).add_record(
                record,
                is_time_expired=is_time_expired,
                is_reclaimable=is_reclaimable,
            )

        quota = self._build_quota(totals["active_size_bytes"])
        return FileStorageUsageReport(
            generated_at=generated_at,
            artifact_storage=self.artifact_storage,
            artifact_root_writable=self.artifact_root_writable,
            artifact_disk_free_bytes=self.artifact_disk_free_bytes,
            totals=totals,
            reclaim=reclaim,
            quota=quota,
            by_storage_provider=_sorted_groups(by_provider),
            by_file_type=_sorted_groups(by_file_type),
            by_status=_sorted_groups(by_status),
        )

    def _add_totals(
        self,
        record: DocumentFileRecord,
        *,
        totals: dict[str, int],
        size_bytes: int,
        is_time_expired: bool,
    ) -> None:
        """累加顶层 usage totals。"""

        totals["files_seen"] += 1
        totals["total_size_bytes"] += size_bytes
        if record.status == "deleted":
            totals["deleted_files"] += 1
            totals["deleted_metadata_size_bytes"] += size_bytes
            return
        totals["active_files"] += 1
        totals["active_size_bytes"] += size_bytes
        if is_time_expired:
            totals["expired_files"] += 1
            totals["expired_size_bytes"] += size_bytes

    def _add_reclaim(
        self,
        record: DocumentFileRecord,
        *,
        reclaim: dict[str, int | str],
        size_bytes: int,
        is_time_expired: bool,
    ) -> None:
        """按物理删除前置条件估算可回收和阻塞类别。"""

        if record.status == "deleted":
            reclaim["deleted_metadata_files"] = int(reclaim["deleted_metadata_files"]) + 1
            reclaim["deleted_metadata_size_bytes"] = int(reclaim["deleted_metadata_size_bytes"]) + size_bytes
            return
        if not is_time_expired:
            return
        if record.status != "expired":
            reclaim["blocked_not_expired_status_files"] = int(reclaim["blocked_not_expired_status_files"]) + 1
            reclaim["blocked_not_expired_status_size_bytes"] = int(reclaim["blocked_not_expired_status_size_bytes"]) + size_bytes
            return
        if record.storage_provider not in STORAGE_USAGE_RECLAIM_SUPPORTED_PROVIDERS:
            reclaim["unsupported_storage_files"] = int(reclaim["unsupported_storage_files"]) + 1
            reclaim["unsupported_storage_size_bytes"] = int(reclaim["unsupported_storage_size_bytes"]) + size_bytes
            return
        if not record.object_key:
            reclaim["blocked_missing_object_key_files"] = int(reclaim["blocked_missing_object_key_files"]) + 1
            reclaim["blocked_missing_object_key_size_bytes"] = int(reclaim["blocked_missing_object_key_size_bytes"]) + size_bytes
            return
        reclaim["estimated_reclaimable_files"] = int(reclaim["estimated_reclaimable_files"]) + 1
        reclaim["estimated_reclaimable_size_bytes"] = int(reclaim["estimated_reclaimable_size_bytes"]) + size_bytes

    def _build_quota(self, used_size_bytes: int) -> dict[str, int | float | bool | str | None]:
        """生成 advisory quota readiness；当前不参与上传授权或清理决策。"""

        if self.quota_bytes is None or self.quota_bytes <= 0:
            return {
                "configured": False,
                "quota_bytes": None,
                "warning_threshold_ratio": None,
                "used_size_bytes": used_size_bytes,
                "usage_ratio": None,
                "status": "not_configured",
            }
        usage_ratio = used_size_bytes / self.quota_bytes
        warning_threshold = self.warning_threshold_ratio if self.warning_threshold_ratio is not None else 0.8
        status: FileStorageQuotaStatus = "ok"
        if usage_ratio >= 1.0:
            status = "exceeded"
        elif usage_ratio >= warning_threshold:
            status = "warning"
        return {
            "configured": True,
            "quota_bytes": self.quota_bytes,
            "warning_threshold_ratio": warning_threshold,
            "used_size_bytes": used_size_bytes,
            "usage_ratio": usage_ratio,
            "status": status,
        }

    @staticmethod
    def _group(groups: dict[str, FileStorageUsageGroup], key: str) -> FileStorageUsageGroup:
        """获取或创建某个分组。"""

        if key not in groups:
            groups[key] = FileStorageUsageGroup(key=key)
        return groups[key]


def _is_estimated_reclaimable(record: DocumentFileRecord, *, is_time_expired: bool) -> bool:
    """判断 metadata 是否满足手动物理删除的首层可回收估算条件。"""

    return (
        record.status == "expired"
        and is_time_expired
        and record.storage_provider in STORAGE_USAGE_RECLAIM_SUPPORTED_PROVIDERS
        and bool(record.object_key)
    )


def _is_time_expired(record: DocumentFileRecord, now: datetime) -> bool:
    """判断 expires_at 是否已过期；无 expires_at 的记录不算过期。"""

    if record.expires_at is None:
        return False
    return _normalize_datetime(record.expires_at) <= now


def _normalize_datetime(value: datetime) -> datetime:
    """统一为 timezone-aware UTC-ish datetime，兼容旧 metadata 的 naive 时间。"""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _sorted_groups(groups: dict[str, FileStorageUsageGroup]) -> list[FileStorageUsageGroup]:
    """按 key 输出稳定顺序，便于 API 测试和前端渲染。"""

    return [groups[key] for key in sorted(groups)]
