# File: app/domains/files/cleanup_execution.py
# Purpose: Build guarded file-retention cleanup run previews and executions.

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from fastapi import status

from app.core.errors import ApiError
from app.domains.files.service import (
    FileRetentionDeleteReport,
    FileUploadService,
    RETENTION_DELETE_CONFIRMATION_PHRASE,
)


CLEANUP_RUN_CONFIRMATION_PHRASE = "EXECUTE AUTOMATED RETENTION CLEANUP"


@dataclass(frozen=True, slots=True)
class FileRetentionCleanupRunReport:
    """一次 file retention cleanup run 的 preview 或 execute 汇总。"""

    run_id: str
    generated_at: datetime
    action_mode: str
    confirmation_phrase: str
    preview_hash: str
    requested_file_ids: list[str]
    max_files: int
    physical_delete: FileRetentionDeleteReport


class FileRetentionCleanupRunService:
    """用 cleanup-run 合同包装现有 selected-file physical delete safety primitive。"""

    def __init__(self, file_upload_service: FileUploadService) -> None:
        self.file_upload_service = file_upload_service

    def preview(
        self,
        *,
        file_ids: list[str],
        max_files: int,
    ) -> FileRetentionCleanupRunReport:
        """生成 cleanup run preview；不会修改 metadata、删除文件或写审计。"""

        self._validate_max_files(file_ids=file_ids, max_files=max_files)
        physical_preview = self.file_upload_service.preview_retention_physical_delete(file_ids)
        return self._build_report(
            action_mode="cleanup_preview",
            physical_delete=physical_preview,
            max_files=max_files,
        )

    def execute(
        self,
        *,
        file_ids: list[str],
        max_files: int,
        preview_hash: str,
        reason: str,
        confirmation: str,
        run_id: str | None = None,
    ) -> FileRetentionCleanupRunReport:
        """验证 preview hash 后复用 existing physical-delete execution。"""

        normalized_reason = reason.strip()
        if not normalized_reason:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "reason 不能为空。")
        if confirmation != CLEANUP_RUN_CONFIRMATION_PHRASE:
            raise ApiError(
                status.HTTP_400_BAD_REQUEST,
                "invalid_request",
                f"confirmation 必须为 {CLEANUP_RUN_CONFIRMATION_PHRASE}。",
            )
        self._validate_max_files(file_ids=file_ids, max_files=max_files)
        physical_preview = self.file_upload_service.preview_retention_physical_delete(file_ids)
        expected_hash = self._preview_hash(physical_preview)
        if preview_hash != expected_hash:
            raise ApiError(
                status.HTTP_409_CONFLICT,
                "conflict",
                "preview_hash 与当前 cleanup preview 不匹配，请重新 preview 后再执行。",
            )
        physical_execute = self.file_upload_service.execute_retention_physical_delete(
            file_ids,
            reason=normalized_reason,
            confirmation=RETENTION_DELETE_CONFIRMATION_PHRASE,
        )
        return self._build_report(
            action_mode="cleanup_execute",
            physical_delete=physical_execute,
            max_files=max_files,
            preview_hash=expected_hash,
            run_id=run_id,
        )

    def audit_reason(self, *, human_reason: str, report: FileRetentionCleanupRunReport) -> str:
        """生成 compact audit reason，不包含 object_key 或本地路径。"""

        normalized_reason = " ".join(human_reason.strip().split())
        totals = report.physical_delete.totals
        return (
            f"reason={normalized_reason} requested={len(report.requested_file_ids)} "
            f"preview_hash={report.preview_hash} deleted={totals.get('deleted', 0)} "
            f"already_missing={totals.get('already_missing', 0)} skipped={totals.get('skipped', 0)} "
            f"failed={totals.get('failed', 0)} metadata_updated={totals.get('metadata_updated', 0)}"
        )

    def _validate_max_files(self, *, file_ids: list[str], max_files: int) -> None:
        """校验 cleanup run 自身限流边界，file_id 细节仍由 physical-delete service 校验。"""

        if len(file_ids) > max_files:
            raise ApiError(
                status.HTTP_400_BAD_REQUEST,
                "invalid_request",
                f"file_ids 数量不能超过 max_files={max_files}。",
            )

    def _build_report(
        self,
        *,
        action_mode: str,
        physical_delete: FileRetentionDeleteReport,
        max_files: int,
        preview_hash: str | None = None,
        run_id: str | None = None,
    ) -> FileRetentionCleanupRunReport:
        """把 physical-delete report 包装为 cleanup run report。"""

        return FileRetentionCleanupRunReport(
            run_id=run_id or f"cleanup_run_{uuid4().hex[:12]}",
            generated_at=physical_delete.generated_at,
            action_mode=action_mode,
            confirmation_phrase=CLEANUP_RUN_CONFIRMATION_PHRASE,
            preview_hash=preview_hash or self._preview_hash(physical_delete),
            requested_file_ids=physical_delete.requested_file_ids,
            max_files=max_files,
            physical_delete=physical_delete,
        )

    def _preview_hash(self, report: FileRetentionDeleteReport) -> str:
        """根据当前 target/outcome 生成稳定 hash，避免 stale preview 执行。"""

        payload = {
            "requested_file_ids": report.requested_file_ids,
            "items": [
                {
                    "file_id": item.file_id,
                    "storage_provider": item.storage_provider,
                    "status_before": item.status_before,
                    "status_after": item.status_after,
                    "object_key": item.object_key,
                    "size_bytes": item.size_bytes,
                    "outcome": item.outcome,
                    "s3_delete_contract": item.s3_delete_contract.to_dict()
                    if item.s3_delete_contract is not None
                    else None,
                }
                for item in report.items
            ],
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"
