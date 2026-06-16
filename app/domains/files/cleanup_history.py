# File: app/domains/files/cleanup_history.py
# Purpose: Persist, sign, validate, and query file-retention cleanup run history without executing cleanup.

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from app.domains.files.cleanup_execution import FileRetentionCleanupRunReport
from app.domains.files.cleanup_lock import FileRetentionCleanupLockRecord
from app.domains.files.scheduled_cleanup import FileRetentionCleanupReadonlyReport
from app.domains.resources.models import utc_now


FileRetentionCleanupRunHistoryStatus = Literal["previewed", "executed", "failed", "dry_run"]
FileRetentionCleanupRunHistoryActionMode = Literal["cleanup_preview", "cleanup_execute", "scheduler_dry_run"]
FileRetentionCleanupPlanSignatureAlgorithm = Literal["hmac-sha256"]
SIGNED_CLEANUP_PLAN_TTL = timedelta(minutes=30)
SIGNED_CLEANUP_PLAN_KEY_NAMESPACE = "md2word.file_retention.cleanup_plan.v1"


class FileRetentionCleanupPlanValidationError(ValueError):
    """表示 cleanup plan 校验失败，router 会据此阻断执行并记录 failed history。"""

    def __init__(self, error_code: str, message: str, *, status_code: int = 409) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code


class FileRetentionSignedCleanupPlan(BaseModel):
    """保存一次 cleanup preview 生成的签名计划摘要。"""

    plan_id: str
    run_id: str
    preview_hash: str
    requested_file_ids: list[str] = Field(default_factory=list)
    max_files: int
    created_at: datetime
    expires_at: datetime
    signature: str
    signature_algorithm: FileRetentionCleanupPlanSignatureAlgorithm = "hmac-sha256"
    safety: dict[str, bool] = Field(default_factory=dict)


class FileRetentionCleanupRunHistoryRecord(BaseModel):
    """保存 cleanup run preview/execute/dry-run 的 durable history 摘要。"""

    run_id: str
    status: FileRetentionCleanupRunHistoryStatus
    action_mode: FileRetentionCleanupRunHistoryActionMode
    preview_hash: str
    requested_file_ids: list[str] = Field(default_factory=list)
    max_files: int
    reason: str | None = None
    totals: dict[str, int] = Field(default_factory=dict)
    safety: dict[str, bool] = Field(default_factory=dict)
    cleanup_plan: FileRetentionSignedCleanupPlan | None = None
    readonly_report: dict[str, Any] = Field(default_factory=dict)
    lock: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    executed_at: datetime | None = None


class FileRetentionCleanupRunHistoryRepositoryProtocol(Protocol):
    """cleanup run history metadata repository 合同。"""

    def save_run(self, record: FileRetentionCleanupRunHistoryRecord) -> FileRetentionCleanupRunHistoryRecord: ...
    def get_run(self, run_id: str) -> FileRetentionCleanupRunHistoryRecord | None: ...
    def list_runs(self) -> list[FileRetentionCleanupRunHistoryRecord]: ...


class FileRetentionCleanupRunHistoryService:
    """管理 cleanup run history 记录，保持记录不包含对象路径或文件内容。"""

    def __init__(self, repository: FileRetentionCleanupRunHistoryRepositoryProtocol) -> None:
        self.repository = repository

    def record_preview(
        self,
        report: FileRetentionCleanupRunReport,
        *,
        signing_secret: str,
    ) -> FileRetentionCleanupRunHistoryRecord:
        """记录 cleanup run preview 并生成 signed plan；不会删除文件或写额外审计。"""

        now = _normalize_datetime(report.generated_at)
        existing = self.repository.get_run(report.run_id)
        cleanup_plan = build_signed_cleanup_plan(report, signing_secret=signing_secret)
        record = FileRetentionCleanupRunHistoryRecord(
            run_id=report.run_id,
            status="previewed",
            action_mode="cleanup_preview",
            preview_hash=report.preview_hash,
            requested_file_ids=list(report.requested_file_ids),
            max_files=report.max_files,
            totals=dict(report.physical_delete.totals),
            safety=_build_safety(
                physical_delete_executed=False,
                audit_events_written=False,
                history_recorded=True,
                signed_plan_created=True,
                signed_plan_verified=False,
            ),
            cleanup_plan=cleanup_plan,
            created_at=existing.created_at if existing is not None else now,
            updated_at=now,
        )
        return self.repository.save_run(record)

    def record_execute(
        self,
        report: FileRetentionCleanupRunReport,
        *,
        reason: str,
        audit_events_written: bool,
        signing_secret: str,
        signed_plan_verified: bool = False,
    ) -> FileRetentionCleanupRunHistoryRecord:
        """记录 cleanup run execute 结果；复用已有 run 的 created_at 和 cleanup plan。"""

        now = _normalize_datetime(report.generated_at)
        existing = self.repository.get_run(report.run_id)
        cleanup_plan = (
            existing.cleanup_plan
            if existing is not None and existing.cleanup_plan is not None
            else build_signed_cleanup_plan(report, signing_secret=signing_secret)
        )
        record = FileRetentionCleanupRunHistoryRecord(
            run_id=report.run_id,
            status="executed",
            action_mode="cleanup_execute",
            preview_hash=report.preview_hash,
            requested_file_ids=list(report.requested_file_ids),
            max_files=report.max_files,
            reason=_compact_reason(reason),
            totals=dict(report.physical_delete.totals),
            safety=_build_safety(
                physical_delete_executed=True,
                audit_events_written=audit_events_written,
                history_recorded=True,
                signed_plan_created=cleanup_plan is not None,
                signed_plan_verified=signed_plan_verified,
            ),
            cleanup_plan=cleanup_plan,
            created_at=existing.created_at if existing is not None else now,
            updated_at=now,
            executed_at=now,
        )
        return self.repository.save_run(record)

    def record_failed_execute(
        self,
        *,
        run_id: str,
        file_ids: list[str],
        max_files: int,
        preview_hash: str,
        reason: str | None,
        error_code: str,
        error_message: str,
        now: datetime | None = None,
    ) -> FileRetentionCleanupRunHistoryRecord:
        """记录 execute 前置校验失败；不绕过现有 cleanup validation。"""

        generated_at = _normalize_datetime(now or utc_now())
        existing = self.repository.get_run(run_id)
        record = FileRetentionCleanupRunHistoryRecord(
            run_id=run_id,
            status="failed",
            action_mode="cleanup_execute",
            preview_hash=preview_hash,
            requested_file_ids=list(file_ids),
            max_files=max_files,
            reason=_compact_reason(reason or "") or None,
            totals={
                "requested": len(file_ids),
                "deleted": 0,
                "failed": len(file_ids),
                "skipped": 0,
            },
            safety=_build_safety(
                physical_delete_executed=False,
                audit_events_written=False,
                history_recorded=True,
                signed_plan_created=existing is not None and existing.cleanup_plan is not None,
                signed_plan_verified=False,
            ),
            cleanup_plan=existing.cleanup_plan if existing is not None else None,
            error_code=error_code,
            error_message=error_message,
            created_at=existing.created_at if existing is not None else generated_at,
            updated_at=generated_at,
            executed_at=generated_at,
        )
        return self.repository.save_run(record)

    def record_scheduler_dry_run(
        self,
        report: FileRetentionCleanupReadonlyReport,
        *,
        lock: FileRetentionCleanupLockRecord,
        lock_released: bool,
    ) -> FileRetentionCleanupRunHistoryRecord:
        """记录一次手动 scheduler dry-run；只保存安全报告和 lock 证据。"""

        now = _normalize_datetime(report.generated_at)
        existing = self.repository.get_run(report.run_id)
        report_dict = report.to_dict()
        requested_file_ids = _readonly_candidate_file_ids(report_dict)
        record = FileRetentionCleanupRunHistoryRecord(
            run_id=report.run_id,
            status="dry_run",
            action_mode="scheduler_dry_run",
            preview_hash=_readonly_report_hash(report_dict),
            requested_file_ids=requested_file_ids,
            max_files=len(requested_file_ids),
            totals=dict(report.retention.get("totals") or {}),
            safety=_build_scheduler_dry_run_safety(lock_released=lock_released),
            cleanup_plan=None,
            readonly_report=report_dict,
            lock=_cleanup_lock_summary(lock, lock_released=lock_released),
            created_at=existing.created_at if existing is not None else now,
            updated_at=now,
            executed_at=None,
        )
        return self.repository.save_run(record)

    def validate_execute_plan(
        self,
        *,
        run_id: str,
        file_ids: list[str],
        max_files: int,
        preview_hash: str,
        plan_id: str | None,
        plan_signature: str | None,
        now: datetime | None = None,
    ) -> FileRetentionSignedCleanupPlan | None:
        """校验 execute 请求携带的 cleanup plan；未携带 plan 时保持旧客户端兼容。"""

        if not plan_id and not plan_signature:
            return None
        if not plan_id or not plan_signature:
            raise FileRetentionCleanupPlanValidationError(
                "cleanup_run_plan_incomplete",
                "plan_id 和 plan_signature 必须同时提供。",
                status_code=400,
            )
        existing = self.repository.get_run(run_id)
        if existing is None:
            raise FileRetentionCleanupPlanValidationError(
                "cleanup_run_preview_not_found",
                "cleanup run history 不存在，请重新 preview 后再执行。",
            )
        plan = existing.cleanup_plan
        if plan is None:
            raise FileRetentionCleanupPlanValidationError(
                "cleanup_run_plan_not_found",
                "cleanup run signed plan 不存在，请重新 preview 后再执行。",
            )
        self._validate_plan_matches_request(
            plan,
            run_id=run_id,
            file_ids=file_ids,
            max_files=max_files,
            preview_hash=preview_hash,
            plan_id=plan_id,
            plan_signature=plan_signature,
            now=now or utc_now(),
        )
        return plan

    def get_run(self, run_id: str) -> FileRetentionCleanupRunHistoryRecord | None:
        """按 run_id 读取 cleanup run history。"""

        return self.repository.get_run(run_id)

    def list_runs(self, *, page: int, page_size: int) -> tuple[list[FileRetentionCleanupRunHistoryRecord], int]:
        """分页读取 cleanup run history，按 updated_at 倒序。"""

        runs = sorted(
            self.repository.list_runs(),
            key=lambda record: (record.updated_at, record.run_id),
            reverse=True,
        )
        start = (page - 1) * page_size
        end = start + page_size
        return runs[start:end], len(runs)

    def _validate_plan_matches_request(
        self,
        plan: FileRetentionSignedCleanupPlan,
        *,
        run_id: str,
        file_ids: list[str],
        max_files: int,
        preview_hash: str,
        plan_id: str,
        plan_signature: str,
        now: datetime,
    ) -> None:
        """逐项校验 signed cleanup plan 与 execute 请求完全一致。"""

        normalized_now = _normalize_datetime(now)
        if normalized_now > _normalize_datetime(plan.expires_at):
            raise FileRetentionCleanupPlanValidationError(
                "cleanup_run_plan_expired",
                "cleanup run signed plan 已过期，请重新 preview 后再执行。",
            )
        if plan.run_id != run_id:
            raise _plan_mismatch("run_id")
        if plan.plan_id != plan_id:
            raise _plan_mismatch("plan_id")
        if not hmac.compare_digest(plan.signature, plan_signature):
            raise FileRetentionCleanupPlanValidationError(
                "cleanup_run_plan_signature_mismatch",
                "cleanup run signed plan signature 不匹配，请重新 preview。",
            )
        if plan.preview_hash != preview_hash:
            raise _plan_mismatch("preview_hash")
        if plan.requested_file_ids != list(file_ids):
            raise _plan_mismatch("file_ids")
        if plan.max_files != max_files:
            raise _plan_mismatch("max_files")


def _build_safety(
    *,
    physical_delete_executed: bool,
    audit_events_written: bool,
    history_recorded: bool,
    signed_plan_created: bool,
    signed_plan_verified: bool,
) -> dict[str, bool]:
    """生成 history 内保存的 cleanup safety flags。"""

    return {
        "scheduler_loop_executed": False,
        "provider_calls_executed": False,
        "s3_delete_executed": False,
        "physical_delete_executed": physical_delete_executed,
        "physical_delete_contract_reused": True,
        "audit_events_written": audit_events_written,
        "history_recorded": history_recorded,
        "signed_plan_created": signed_plan_created,
        "signed_plan_verified": signed_plan_verified,
    }


def _build_scheduler_dry_run_safety(*, lock_released: bool) -> dict[str, bool]:
    """生成手动 scheduler dry-run 的安全边界 flags。"""

    return {
        "scheduler_loop_executed": False,
        "scheduler_manual_dry_run_executed": True,
        "metadata_mutated": False,
        "objects_deleted": False,
        "mark_expired_executed": False,
        "physical_delete_executed": False,
        "physical_delete_contract_reused": False,
        "audit_events_written": False,
        "provider_calls_executed": False,
        "s3_delete_executed": False,
        "cleanup_lock_acquired": True,
        "cleanup_lock_released": lock_released,
        "history_recorded": True,
        "signed_plan_created": False,
        "signed_plan_verified": False,
    }


def _readonly_report_hash(report_dict: dict[str, Any]) -> str:
    """为 readonly scheduler dry-run 报告生成稳定摘要，便于 history 对账。"""

    encoded_payload = json.dumps(report_dict, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded_payload).hexdigest()}"


def _readonly_candidate_file_ids(report_dict: dict[str, Any]) -> list[str]:
    """从 readonly report 的安全 candidate 摘要里提取 file_id。"""

    retention = report_dict.get("retention")
    if not isinstance(retention, dict):
        return []
    candidates = retention.get("candidates")
    if not isinstance(candidates, list):
        return []
    file_ids: list[str] = []
    for candidate in candidates:
        if isinstance(candidate, dict) and isinstance(candidate.get("file_id"), str):
            file_ids.append(candidate["file_id"])
    return file_ids


def _cleanup_lock_summary(lock: FileRetentionCleanupLockRecord, *, lock_released: bool) -> dict[str, Any]:
    """把 cleanup lock 记录压缩成可返回的 safety evidence。"""

    return {
        "lock_name": lock.lock_name,
        "owner_id": lock.owner_id,
        "fencing_token": lock.fencing_token,
        "status": lock.status,
        "acquired_at": _normalize_datetime(lock.acquired_at).isoformat(),
        "expires_at": _normalize_datetime(lock.expires_at).isoformat(),
        "released_at": _normalize_datetime(lock.released_at).isoformat() if lock.released_at is not None else None,
        "released": lock_released,
    }


def build_signed_cleanup_plan(
    report: FileRetentionCleanupRunReport,
    *,
    signing_secret: str,
) -> FileRetentionSignedCleanupPlan:
    """基于 cleanup preview/report 生成 deterministic HMAC signed plan。"""

    secret = signing_secret.strip()
    if not secret:
        raise ValueError("cleanup plan signing secret 不能为空。")
    created_at = _normalize_datetime(report.generated_at)
    expires_at = created_at + SIGNED_CLEANUP_PLAN_TTL
    signature = _sign_cleanup_plan_payload(
        signing_secret=secret,
        run_id=report.run_id,
        preview_hash=report.preview_hash,
        requested_file_ids=list(report.requested_file_ids),
        max_files=report.max_files,
        created_at=created_at,
        expires_at=expires_at,
    )
    signature_hex = signature.split(":", 1)[-1]
    return FileRetentionSignedCleanupPlan(
        plan_id=f"cleanup_plan_{signature_hex[:16]}",
        run_id=report.run_id,
        preview_hash=report.preview_hash,
        requested_file_ids=list(report.requested_file_ids),
        max_files=report.max_files,
        created_at=created_at,
        expires_at=expires_at,
        signature=signature,
        signature_algorithm="hmac-sha256",
        safety={
            "scheduler_loop_executed": False,
            "provider_calls_executed": False,
            "s3_delete_executed": False,
            "physical_delete_executed": False,
            "physical_delete_contract_reused": True,
            "signed_plan_created": True,
        },
    )


def _sign_cleanup_plan_payload(
    *,
    signing_secret: str,
    run_id: str,
    preview_hash: str,
    requested_file_ids: list[str],
    max_files: int,
    created_at: datetime,
    expires_at: datetime,
) -> str:
    """对 cleanup plan 的安全关键字段生成 HMAC-SHA256 签名。"""

    payload = {
        "namespace": SIGNED_CLEANUP_PLAN_KEY_NAMESPACE,
        "run_id": run_id,
        "preview_hash": preview_hash,
        "requested_file_ids": requested_file_ids,
        "max_files": max_files,
        "created_at": _normalize_datetime(created_at).isoformat(),
        "expires_at": _normalize_datetime(expires_at).isoformat(),
    }
    encoded_payload = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    key = f"{SIGNED_CLEANUP_PLAN_KEY_NAMESPACE}:{signing_secret}".encode("utf-8")
    digest = hmac.new(key, encoded_payload, hashlib.sha256).hexdigest()
    return f"hmac-sha256:{digest}"


def _plan_mismatch(field_name: str) -> FileRetentionCleanupPlanValidationError:
    """生成 plan/request 字段不一致的标准错误。"""

    return FileRetentionCleanupPlanValidationError(
        "cleanup_run_plan_mismatch",
        f"cleanup run signed plan 与请求字段不匹配: {field_name}，请重新 preview。",
    )


def _compact_reason(reason: str) -> str:
    """把人工 reason 压缩为空白规范形式，避免写入大 payload。"""

    return " ".join(reason.strip().split())


def _normalize_datetime(value: datetime) -> datetime:
    """统一为 timezone-aware UTC-ish datetime，兼容旧 metadata 的 naive 时间。"""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
