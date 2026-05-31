from __future__ import annotations

# app/domains/files/retention.py: 生成 document_files 保留期清理计划并可标记过期文件。

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.domains.files.models import DocumentFileRecord
from app.domains.files.repository import DocumentFileRepositoryProtocol
from app.domains.jobs.models import utc_now


@dataclass(frozen=True, slots=True)
class DocumentFileRetentionCandidate:
    """一条已过保留期的 document_file 候选；当前不直接删除 OSS 对象。"""

    file_id: str
    job_id: str | None
    file_type: str
    storage_provider: str
    bucket: str
    object_key: str
    size_bytes: int
    status: str
    expires_at: datetime
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_id": self.file_id,
            "job_id": self.job_id,
            "file_type": self.file_type,
            "storage_provider": self.storage_provider,
            "bucket": self.bucket,
            "object_key": self.object_key,
            "size_bytes": self.size_bytes,
            "status": self.status,
            "expires_at": self.expires_at.isoformat(),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class DocumentFileRetentionPlan:
    """document_files retention dry-run 汇总。"""

    generated_at: datetime
    retention_days: int
    totals: dict[str, int]
    candidates: list[DocumentFileRetentionCandidate]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "retention_days": self.retention_days,
            "totals": self.totals,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }


class DocumentFileRetentionPlanner:
    """基于 document_files.expires_at 的保留期策略，先计划和标记，不删除二进制。"""

    def __init__(
        self,
        repository: DocumentFileRepositoryProtocol,
        *,
        retention_days: int,
    ) -> None:
        self.repository = repository
        self.retention_days = retention_days

    def build_plan(self, *, now: datetime | None = None) -> DocumentFileRetentionPlan:
        """生成过期文件候选；deleted 状态不再进入清理候选。"""

        generated_at = self._normalize_datetime(now or utc_now())
        totals = {
            "files_seen": 0,
            "files_with_expires_at": 0,
            "candidate_files": 0,
            "candidate_local_files": 0,
            "candidate_objects": 0,
            "already_deleted_files": 0,
        }
        candidates: list[DocumentFileRetentionCandidate] = []
        for record in self.repository.list_document_files():
            totals["files_seen"] += 1
            if record.status == "deleted":
                totals["already_deleted_files"] += 1
                continue
            if record.expires_at is None:
                continue
            totals["files_with_expires_at"] += 1
            expires_at = self._normalize_datetime(record.expires_at)
            if expires_at > generated_at:
                continue
            if record.storage_provider == "s3":
                totals["candidate_objects"] += 1
            else:
                totals["candidate_local_files"] += 1
            candidates.append(self._candidate_from_record(record, expires_at=expires_at))

        totals["candidate_files"] = len(candidates)
        return DocumentFileRetentionPlan(
            generated_at=generated_at,
            retention_days=self.retention_days,
            totals=totals,
            candidates=candidates,
        )

    def mark_expired(self, *, now: datetime | None = None) -> DocumentFileRetentionPlan:
        """把候选文件标记为 expired，供后续 OSS 生命周期或人工任务执行物理清理。"""

        plan = self.build_plan(now=now)
        updated_at = plan.generated_at
        for candidate in plan.candidates:
            if candidate.status == "uploaded":
                self.repository.update_document_file(
                    candidate.file_id,
                    status="expired",
                    updated_at=updated_at,
                )
        return plan

    def _candidate_from_record(
        self,
        record: DocumentFileRecord,
        *,
        expires_at: datetime,
    ) -> DocumentFileRetentionCandidate:
        return DocumentFileRetentionCandidate(
            file_id=record.id,
            job_id=record.job_id,
            file_type=record.file_type,
            storage_provider=record.storage_provider,
            bucket=record.bucket,
            object_key=record.object_key,
            size_bytes=record.size_bytes,
            status=record.status,
            expires_at=expires_at,
            reason=f"expires_at={expires_at.isoformat()} retention_days={self.retention_days}",
        )

    def _normalize_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
