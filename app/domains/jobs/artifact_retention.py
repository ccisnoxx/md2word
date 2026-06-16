from __future__ import annotations

# app/domains/jobs/artifact_retention.py: 生成 artifact 保留期清理的 dry-run 计划。

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.domains.jobs.models import JobFile, JobRecord, utc_now
from app.domains.jobs.repository import JobFileRepositoryProtocol, JobSnapshotRepositoryProtocol


DEFAULT_RETENTION_DAYS_BY_STATUS = {
    "completed": 30,
    "failed": 14,
    "canceled": 7,
}


@dataclass(frozen=True, slots=True)
class ArtifactRetentionPolicy:
    """按最终 job 状态定义 artifact 的保留天数；未列出的状态不参与清理。"""

    retention_days_by_status: dict[str, int | None] = field(
        default_factory=lambda: dict(DEFAULT_RETENTION_DAYS_BY_STATUS)
    )

    def retention_days_for(self, status: str) -> int | None:
        return self.retention_days_by_status.get(status)


@dataclass(frozen=True, slots=True)
class ArtifactRetentionCandidate:
    """dry-run 中的一条待清理 artifact 候选。"""

    job_id: str
    job_status: str
    file_type: str
    storage_backend: str
    path: str
    object_key: str | None
    size_bytes: int | None
    sha256: str | None
    age_days: int
    retention_days: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "job_status": self.job_status,
            "file_type": self.file_type,
            "storage_backend": self.storage_backend,
            "path": self.path,
            "object_key": self.object_key,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "age_days": self.age_days,
            "retention_days": self.retention_days,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class ArtifactRetentionDryRun:
    """artifact retention dry-run 汇总；当前只产出计划，不执行删除。"""

    generated_at: datetime
    totals: dict[str, int]
    candidates: list[ArtifactRetentionCandidate]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "totals": self.totals,
            "candidates": [item.to_dict() for item in self.candidates],
        }


class ArtifactRetentionPlanner:
    """根据 job 状态和保留期筛选可清理的 artifact。"""

    def __init__(
        self,
        job_repository: JobSnapshotRepositoryProtocol,
        job_file_repository: JobFileRepositoryProtocol,
    ) -> None:
        self.job_repository = job_repository
        self.job_file_repository = job_file_repository

    def build_dry_run(
        self,
        policy: ArtifactRetentionPolicy | None = None,
        *,
        now: datetime | None = None,
    ) -> ArtifactRetentionDryRun:
        """生成 artifact 清理候选，不删除任何本地文件或对象。"""

        resolved_policy = policy or ArtifactRetentionPolicy()
        generated_at = self._normalize_datetime(now or utc_now())
        candidates: list[ArtifactRetentionCandidate] = []
        totals = {
            "jobs_seen": 0,
            "eligible_jobs": 0,
            "job_files_seen": 0,
            "candidate_artifacts": 0,
            "candidate_local_artifacts": 0,
            "candidate_objects": 0,
        }

        for job in sorted(self.job_repository.list_jobs(), key=lambda item: item.id):
            totals["jobs_seen"] += 1
            retention_days = resolved_policy.retention_days_for(job.status)
            if retention_days is None:
                continue

            age_days = self._age_days(job, generated_at)
            if age_days < retention_days:
                continue

            totals["eligible_jobs"] += 1
            for file in sorted(self.job_file_repository.list_files(job.id), key=lambda item: item.file_type):
                totals["job_files_seen"] += 1
                if not self._is_retention_candidate(file):
                    continue
                if file.storage_backend == "object":
                    totals["candidate_objects"] += 1
                else:
                    totals["candidate_local_artifacts"] += 1
                candidates.append(
                    ArtifactRetentionCandidate(
                        job_id=job.id,
                        job_status=job.status,
                        file_type=file.file_type,
                        storage_backend=file.storage_backend,
                        path=file.path,
                        object_key=file.object_key,
                        size_bytes=file.size_bytes,
                        sha256=file.sha256,
                        age_days=age_days,
                        retention_days=retention_days,
                        reason=f"job_status={job.status} age_days={age_days} retention_days={retention_days}",
                    )
                )

        totals["candidate_artifacts"] = len(candidates)
        return ArtifactRetentionDryRun(
            generated_at=generated_at,
            totals=totals,
            candidates=candidates,
        )

    def _age_days(self, job: JobRecord, now: datetime) -> int:
        reference_time = job.completed_at or job.updated_at or job.created_at
        delta = now - self._normalize_datetime(reference_time)
        return max(delta.days, 0)

    def _normalize_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    def _is_retention_candidate(self, file: JobFile) -> bool:
        if file.storage_backend == "object":
            return bool(file.object_key)
        return file.storage_backend == "local" and bool(file.path)
