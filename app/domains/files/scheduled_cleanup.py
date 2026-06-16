# File: app/domains/files/scheduled_cleanup.py
# Purpose: Build read-only scheduled cleanup reports for document_files retention.

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Literal
from uuid import uuid4

from app.domains.files.retention import DocumentFileRetentionCandidate, DocumentFileRetentionPlanner
from app.domains.files.storage_usage import DocumentFileStorageUsageReporter


FileRetentionCleanupMode = Literal["readonly_plan"]


@dataclass(frozen=True, slots=True)
class FileRetentionCleanupReadonlyReport:
    """一次 document_files 清理 runner 的只读计划报告。"""

    run_id: str
    generated_at: datetime
    mode: FileRetentionCleanupMode
    retention: dict[str, Any]
    storage_usage: dict[str, Any]
    next_steps: list[str] = field(default_factory=list)
    safety: dict[str, bool | str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为可 JSON 序列化的报告字典。"""

        return {
            "run_id": self.run_id,
            "generated_at": self.generated_at.isoformat(),
            "mode": self.mode,
            "retention": self.retention,
            "storage_usage": _json_safe(self.storage_usage),
            "next_steps": self.next_steps,
            "safety": self.safety,
        }


class FileRetentionReadonlyCleanupRunner:
    """组合 retention plan 和 storage usage，生成无副作用 cleanup 计划。"""

    def __init__(
        self,
        retention_planner: DocumentFileRetentionPlanner,
        storage_usage_reporter: DocumentFileStorageUsageReporter,
        *,
        run_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.retention_planner = retention_planner
        self.storage_usage_reporter = storage_usage_reporter
        self.run_id_factory = run_id_factory or _new_run_id

    def build_report(self) -> FileRetentionCleanupReadonlyReport:
        """生成只读计划；不会 mark-expired、预览删除或执行删除。"""

        retention_plan = self.retention_planner.build_plan()
        storage_usage = self.storage_usage_reporter.build_report(now=retention_plan.generated_at)
        return FileRetentionCleanupReadonlyReport(
            run_id=self.run_id_factory(),
            generated_at=retention_plan.generated_at,
            mode="readonly_plan",
            retention={
                "generated_at": retention_plan.generated_at.isoformat(),
                "retention_days": retention_plan.retention_days,
                "totals": retention_plan.totals,
                "candidates": [
                    _candidate_summary(candidate)
                    for candidate in retention_plan.candidates
                ],
            },
            storage_usage=storage_usage.to_dict(),
            next_steps=[
                "Review metadata-estimated candidates before any cleanup action.",
                "Use /api/v1/files/retention/delete-preview with exact selected file_ids before physical deletion.",
                "Do not treat this readonly runner report as deletion authorization.",
            ],
            safety={
                "metadata_mutated": False,
                "objects_deleted": False,
                "mark_expired_executed": False,
                "physical_delete_executed": False,
                "s3_delete_executed": False,
                "report_basis": "metadata_only",
            },
        )


def _candidate_summary(candidate: DocumentFileRetentionCandidate) -> dict[str, Any]:
    """输出候选摘要，刻意省略 object_key/bucket/path 等对象定位信息。"""

    return {
        "file_id": candidate.file_id,
        "job_id": candidate.job_id,
        "file_type": candidate.file_type,
        "storage_provider": candidate.storage_provider,
        "size_bytes": candidate.size_bytes,
        "status": candidate.status,
        "expires_at": candidate.expires_at.isoformat(),
        "reason": candidate.reason,
    }


def _new_run_id() -> str:
    """生成 cleanup runner 报告 ID。"""

    return f"cleanup_{uuid4().hex[:12]}"


def _json_safe(value: Any) -> Any:
    """递归转换 datetime，便于 CLI 直接 JSON 输出。"""

    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    return value
