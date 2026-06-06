# File: app/domains/ops/provider_cancellation.py
# Purpose: Provide Admin-only fake provider cancellation preview and audit-backed execution logic.

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import status

from app.core.errors import ApiError
from app.domains.audit.models import AuditEvent
from app.domains.audit.repository import AuditEventRepositoryProtocol
from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.document_jobs.repository import DocumentJobRepositoryProtocol
from app.domains.jobs.models import JobRecord, utc_now
from app.domains.jobs.repository import JobSnapshotRepositoryProtocol
from app.domains.ops.schemas import (
    OpsProviderCancellationMode,
    OpsProviderCancellationProvider,
    OpsProviderCancellationTargetType,
)


PROVIDER_CANCELLATION_CONFIRMATION_PHRASE = "FAKE CANCEL PROVIDER OPERATION"
PROVIDER_CANCELLATION_AUDIT_ACTION = "ops.provider_cancellation_fake"
TERMINAL_LEGACY_JOB_STATUSES = {"completed", "failed", "canceled"}


@dataclass(frozen=True, slots=True)
class OpsProviderCancellationTarget:
    """provider cancellation 目标的安全摘要。"""

    target_type: OpsProviderCancellationTargetType
    target_id: str
    exists: bool
    status: str | None = None
    stage: str | None = None
    summary: dict[str, str | int | bool | None] | None = None

    def to_dict(self) -> dict[str, object]:
        """转换为 API response 字典。"""

        return {
            "target_type": self.target_type,
            "target_id": self.target_id,
            "exists": self.exists,
            "status": self.status,
            "stage": self.stage,
            "summary": self.summary or {},
        }


@dataclass(frozen=True, slots=True)
class OpsProviderOperation:
    """可安全展示的 provider operation 标识。"""

    provider: OpsProviderCancellationProvider
    operation_id: str | None
    data_id: str | None = None
    operation_type: str = "batch_extract"

    def to_dict(self) -> dict[str, str | None]:
        """转换为 API response 字典。"""

        return {
            "provider": self.provider,
            "operation_id": self.operation_id,
            "data_id": self.data_id,
            "operation_type": self.operation_type,
        }


@dataclass(frozen=True, slots=True)
class OpsProviderCancellationReport:
    """汇总一次 provider cancellation preview 或 fake execution。"""

    generated_at: datetime
    action_mode: OpsProviderCancellationMode
    provider: OpsProviderCancellationProvider
    confirmation_phrase: str
    dedupe_window_minutes: int
    target: OpsProviderCancellationTarget
    provider_operation: OpsProviderOperation
    eligible: bool
    missing_gates: list[str]
    outcome: str
    dedupe_key: str | None
    audit_event_written: bool

    def to_dict(self) -> dict[str, object]:
        """转换为 router response 的基础字典。"""

        return {
            "generated_at": self.generated_at,
            "action_mode": self.action_mode,
            "provider": self.provider,
            "confirmation_phrase": self.confirmation_phrase,
            "dedupe_window_minutes": self.dedupe_window_minutes,
            "target": self.target.to_dict(),
            "provider_operation": self.provider_operation.to_dict(),
            "eligible": self.eligible,
            "missing_gates": self.missing_gates,
            "outcome": self.outcome,
            "dedupe_key": self.dedupe_key,
            "audit_event_written": self.audit_event_written,
        }


class OpsProviderCancellationService:
    """为 provider cancellation 提供 metadata-only preview 和 fake execution。"""

    def __init__(
        self,
        *,
        document_job_repository: DocumentJobRepositoryProtocol,
        job_repository: JobSnapshotRepositoryProtocol,
        audit_event_repository: AuditEventRepositoryProtocol,
    ) -> None:
        self.document_job_repository = document_job_repository
        self.job_repository = job_repository
        self.audit_event_repository = audit_event_repository

    def preview(
        self,
        *,
        target_type: OpsProviderCancellationTargetType,
        target_id: str,
        provider: OpsProviderCancellationProvider,
        dedupe_window_minutes: int,
    ) -> OpsProviderCancellationReport:
        """预览 provider cancellation eligibility，不写审计、不调用 provider。"""

        generated_at = utc_now()
        target, operation, missing_gates = self._build_target_context(
            target_type=target_type,
            target_id=target_id,
            provider=provider,
        )
        eligible = target.exists and not missing_gates
        return self._build_report(
            generated_at=generated_at,
            action_mode="dry_run",
            provider=provider,
            dedupe_window_minutes=dedupe_window_minutes,
            target=target,
            provider_operation=operation,
            missing_gates=missing_gates,
            outcome="cancelable" if eligible else "ineligible",
            audit_event_written=False,
        )

    def fake_cancel(
        self,
        *,
        target_type: OpsProviderCancellationTargetType,
        target_id: str,
        provider: OpsProviderCancellationProvider,
        reason: str,
        confirmation: str,
        dedupe_window_minutes: int,
    ) -> OpsProviderCancellationReport:
        """执行 fake provider cancellation，只写审计，不调用真实 provider。"""

        normalized_reason = reason.strip()
        if not normalized_reason:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "reason 不能为空。")
        if confirmation != PROVIDER_CANCELLATION_CONFIRMATION_PHRASE:
            raise ApiError(
                status.HTTP_400_BAD_REQUEST,
                "invalid_request",
                f"confirmation 必须为 {PROVIDER_CANCELLATION_CONFIRMATION_PHRASE}。",
            )
        generated_at = utc_now()
        target, operation, missing_gates = self._build_target_context(
            target_type=target_type,
            target_id=target_id,
            provider=provider,
        )
        if missing_gates:
            raise ApiError(
                status.HTTP_409_CONFLICT,
                "conflict",
                f"provider cancellation fake 目标不满足 gate: {', '.join(missing_gates)}",
            )
        dedupe_key = self._dedupe_key(target=target, operation=operation)
        recent_dedupe_keys = self._recent_dedupe_keys(
            generated_at=generated_at,
            dedupe_window_minutes=dedupe_window_minutes,
        )
        audit_event_written = dedupe_key not in recent_dedupe_keys
        return self._build_report(
            generated_at=generated_at,
            action_mode="fake_cancel",
            provider=provider,
            dedupe_window_minutes=dedupe_window_minutes,
            target=target,
            provider_operation=operation,
            missing_gates=[],
            outcome="fake_canceled" if audit_event_written else "deduped",
            audit_event_written=audit_event_written,
        )

    def audit_reason(self, *, human_reason: str, report: OpsProviderCancellationReport) -> str:
        """生成 compact audit reason，不包含 provider secret 或 callback seed。"""

        normalized_reason = " ".join(human_reason.strip().split())
        return (
            f"reason={normalized_reason} provider={report.provider} "
            f"target_type={report.target.target_type} target_id={report.target.target_id} "
            f"operation_id={report.provider_operation.operation_id or ''} "
            f"data_id={report.provider_operation.data_id or ''} "
            f"dedupe_key={report.dedupe_key or ''} outcome={report.outcome}"
        )

    def _build_target_context(
        self,
        *,
        target_type: OpsProviderCancellationTargetType,
        target_id: str,
        provider: OpsProviderCancellationProvider,
    ) -> tuple[OpsProviderCancellationTarget, OpsProviderOperation, list[str]]:
        """按目标类型读取 metadata 并计算 missing gates。"""

        if provider != "mineru":
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", f"不支持 provider={provider}。")
        normalized_target_id = target_id.strip()
        if not normalized_target_id:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "target_id 不能为空。")
        if target_type == "document_job":
            return self._build_document_job_context(normalized_target_id, provider=provider)
        return self._build_legacy_job_context(normalized_target_id, provider=provider)

    def _build_document_job_context(
        self,
        target_id: str,
        *,
        provider: OpsProviderCancellationProvider,
    ) -> tuple[OpsProviderCancellationTarget, OpsProviderOperation, list[str]]:
        """读取 document_job provider operation 摘要并计算 gate。"""

        job = self.document_job_repository.get_document_job(target_id)
        if job is None:
            return (
                OpsProviderCancellationTarget(target_type="document_job", target_id=target_id, exists=False),
                OpsProviderOperation(provider=provider, operation_id=None),
                ["target_not_found"],
            )
        target = self._document_job_target(job)
        operation = OpsProviderOperation(
            provider=provider,
            operation_id=job.mineru_batch_id,
            data_id=job.mineru_data_id,
        )
        missing_gates: list[str] = []
        if job.archived_at is not None:
            missing_gates.append("target_archived")
        if job.status not in {"queued", "running"}:
            missing_gates.append("status_not_provider_cancelable")
        if not job.mineru_batch_id:
            missing_gates.append("provider_operation_id_missing")
        return target, operation, missing_gates

    def _build_legacy_job_context(
        self,
        target_id: str,
        *,
        provider: OpsProviderCancellationProvider,
    ) -> tuple[OpsProviderCancellationTarget, OpsProviderOperation, list[str]]:
        """读取 legacy source_pdf job provider operation 摘要并计算 gate。"""

        job = self.job_repository.get_job(target_id)
        if job is None:
            return (
                OpsProviderCancellationTarget(target_type="legacy_job", target_id=target_id, exists=False),
                OpsProviderOperation(provider=provider, operation_id=None),
                ["target_not_found"],
            )
        target = self._legacy_job_target(job)
        operation = OpsProviderOperation(
            provider=provider,
            operation_id=job.read_mineru_batch_id(),
            data_id=job.read_mineru_data_id(),
        )
        missing_gates: list[str] = []
        if job.source_kind != "source_pdf":
            missing_gates.append("source_kind_not_source_pdf")
        if job.projected_status() in TERMINAL_LEGACY_JOB_STATUSES:
            missing_gates.append("status_terminal")
        if not job.read_mineru_batch_id():
            missing_gates.append("provider_operation_id_missing")
        return target, operation, missing_gates

    def _document_job_target(self, job: DocumentJobRecord) -> OpsProviderCancellationTarget:
        """生成 document_job 安全摘要，不暴露 callback seed。"""

        return OpsProviderCancellationTarget(
            target_type="document_job",
            target_id=job.id,
            exists=True,
            status=job.status,
            stage=job.stage,
            summary={
                "archived": job.archived_at is not None,
                "created_by": job.created_by,
                "updated_at": job.updated_at.isoformat(),
                "has_mineru_batch_id": bool(job.mineru_batch_id),
                "has_mineru_data_id": bool(job.mineru_data_id),
            },
        )

    def _legacy_job_target(self, job: JobRecord) -> OpsProviderCancellationTarget:
        """生成 legacy job 安全摘要，不暴露路径、object key 或 callback seed。"""

        return OpsProviderCancellationTarget(
            target_type="legacy_job",
            target_id=job.id,
            exists=True,
            status=job.projected_status(),
            stage=job.resolved_execution_status(),
            summary={
                "source_kind": job.source_kind,
                "lifecycle_status": job.resolved_lifecycle_status(),
                "execution_status": job.resolved_execution_status(),
                "has_mineru_batch_id": bool(job.read_mineru_batch_id()),
                "has_mineru_data_id": bool(job.read_mineru_data_id()),
                "updated_at": job.updated_at.isoformat(),
            },
        )

    def _build_report(
        self,
        *,
        generated_at: datetime,
        action_mode: OpsProviderCancellationMode,
        provider: OpsProviderCancellationProvider,
        dedupe_window_minutes: int,
        target: OpsProviderCancellationTarget,
        provider_operation: OpsProviderOperation,
        missing_gates: list[str],
        outcome: str,
        audit_event_written: bool,
    ) -> OpsProviderCancellationReport:
        """组装 provider cancellation 统一响应对象。"""

        eligible = target.exists and not missing_gates
        return OpsProviderCancellationReport(
            generated_at=generated_at,
            action_mode=action_mode,
            provider=provider,
            confirmation_phrase=PROVIDER_CANCELLATION_CONFIRMATION_PHRASE,
            dedupe_window_minutes=dedupe_window_minutes,
            target=target,
            provider_operation=provider_operation,
            eligible=eligible,
            missing_gates=missing_gates,
            outcome=outcome,
            dedupe_key=self._dedupe_key(target=target, operation=provider_operation) if eligible else None,
            audit_event_written=audit_event_written,
        )

    def _recent_dedupe_keys(
        self,
        *,
        generated_at: datetime,
        dedupe_window_minutes: int,
    ) -> set[str]:
        """从近期 audit event reason 中提取 provider cancellation dedupe key。"""

        since = generated_at - timedelta(minutes=dedupe_window_minutes)
        keys: set[str] = set()
        for event in self.audit_event_repository.list_audit_events():
            if event.action != PROVIDER_CANCELLATION_AUDIT_ACTION or event.created_at < since:
                continue
            key = self._extract_dedupe_key(event)
            if key:
                keys.add(key)
        return keys

    def _extract_dedupe_key(self, event: AuditEvent) -> str | None:
        """从 compact audit reason 解析 dedupe_key 字段。"""

        reason = event.reason or ""
        for part in reason.split():
            if part.startswith("dedupe_key="):
                return part.removeprefix("dedupe_key=") or None
        return None

    def _dedupe_key(
        self,
        *,
        target: OpsProviderCancellationTarget,
        operation: OpsProviderOperation,
    ) -> str:
        """生成 fake provider cancellation 的稳定幂等 key。"""

        return f"{operation.provider}:{target.target_type}:{target.target_id}:{operation.operation_id or 'missing'}"
