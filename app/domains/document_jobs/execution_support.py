from __future__ import annotations

# app/domains/document_jobs/execution_support.py: 执行期任务状态推进、事件记录与无状态辅助函数的唯一 owner。

import logging
from typing import Any
from uuid import uuid4

from billiard.exceptions import SoftTimeLimitExceeded

from app.core.config import Settings
from app.domains.document_jobs import _failure_policy as failure_policy
from app.domains.document_jobs.models import (
    DocumentJobEventRecord,
    DocumentJobEventType,
    DocumentJobRecord,
    DocumentJobStage,
)
from app.domains.document_jobs.repository import (
    DocumentJobEventRepositoryProtocol,
    DocumentJobRepositoryProtocol,
)
from app.domains.files.models import DocumentFileRecord
from app.domains.files.repository import DocumentFileRepositoryProtocol
from app.domains.resources.models import utc_now
from app.domains.translation.document_ir_translator import DocumentIRTranslationError
from app.domains.translation.integrity import TranslationIntegrityError, TranslationIntegrityEvidence
from app.services.document_ir.models import DocumentIR
from app.services.document_ir.table_reference_assets import decode_table_references
from app.services.renderer.render_event_summary import build_renderer_event_summary


def document_ir_layout_metadata(document_ir: DocumentIR) -> dict[str, Any]:
    """保存私有 IR 诊断；事件出口另行投影。"""

    return {
        "schema_version": document_ir.schema_version,
        "page_count": len(document_ir.pages),
        "layout_page_count": len(document_ir.pages),
        "block_count": len(document_ir.blocks),
        "layout_block_count": sum(1 for block in document_ir.blocks if block.layout is not None),
        "quality_flags": document_ir.quality_flags,
        "mineru_validation": (document_ir.metadata.mineru_validation.model_dump(mode="json")
                              if document_ir.metadata.mineru_validation is not None else None),
        "mineru_validation_input": document_ir.metadata.mineru_validation_input,
        "table_reference_asset_count": sum(item.asset is not None for item in decode_table_references(document_ir)),
    }


def require_uploaded_file(file_repository: DocumentFileRepositoryProtocol, file_id: str) -> DocumentFileRecord:
    record = file_repository.get_document_file(file_id)
    if record is None:
        raise FileNotFoundError(f"文件不存在: {file_id}")
    if record.status != "uploaded":
        raise ValueError(f"文件尚未完成上传: {file_id}")
    return record


class DocumentJobLifecycle:
    """执行宿主与各阶段协作者共用的任务状态推进入口；所有写入都按代数与阶段做 CAS。"""

    def __init__(
        self,
        settings: Settings,
        job_repository: DocumentJobRepositoryProtocol,
        event_repository: DocumentJobEventRepositoryProtocol,
        logger: logging.Logger,
    ) -> None:
        self.settings = settings
        self.job_repository = job_repository
        self.event_repository = event_repository
        self.logger = logger

    def record_event(
        self,
        job: DocumentJobRecord,
        *,
        event_type: DocumentJobEventType,
        stage: DocumentJobStage,
        message: str,
        payload: dict,
        trace_id: str | None,
        level: str = "info",
        duration_ms: int | None = None,
    ) -> None:
        # renderer 事件只允许固定外层身份与安全摘要；未知新字段不能借嵌套值透传。
        if (payload.get("file_type") == "generated_word"
                or any(key in payload for key in ("renderer_content_contract_version", "formula_source_coverage",
                    "render_plan", "block_render_evidence", "block_anchor_evidence", "page_mapping"))):
            outer_keys = {"file_id", "file_type", "document_ir_file_id", "result_file_id", "template_version_id",
                "error_code", "error_message", "prepared_result_file_id"}
            payload = {**{key: value for key, value in payload.items() if key in outer_keys},
                **build_renderer_event_summary(payload)}
        if payload.get("schema_version") in {"document-ir/v1", "document-ir/v2"}:
            outer_keys = {
                "file_id", "file_type", "document_ir_file_id", "source_document_ir_file_id",
                "image_asset_file_ids", "image_assets_archive_file_id", "image_asset_count",
                "translation", "translation_batch_count", "translation_item_count",
            }
            payload = {
                **{key: value for key, value in payload.items() if key in outer_keys},
                **build_renderer_event_summary(payload),
            }
        if payload.get("mineru_validation") is not None or payload.get("failure_context") is not None:
            payload = {**payload, "retry_count": job.retry_count}
        event = DocumentJobEventRecord(
            id=f"event_{uuid4().hex[:12]}",
            tenant_id=job.tenant_id,
            company_id=job.company_id,
            job_id=job.id,
            created_by=job.created_by,
            stage=stage,
            level=level,
            event_type=event_type,
            message=message,
            payload={"retry_count": job.retry_count, "generation": job.retry_count, **payload},
            duration_ms=duration_ms,
            trace_id=trace_id,
        )
        self.event_repository.append_document_job_event(job.id, event)

    def mark_succeeded(self, job: DocumentJobRecord, *, trace_id: str | None) -> DocumentJobRecord:
        # legacy 明确主件可下载，但无 receipt 不能生成或伪造与当前来源绑定的预览。
        preview_contribution = None
        if "word_preview" in job.request_snapshot:
            from app.services.preview.models import PreviewPolicy
            policy = PreviewPolicy.model_validate(job.request_snapshot["word_preview"])
            preview_contribution = {"quality_status": "blocked" if policy.required else "pending",
                "status": "unavailable", "error_code": "preview_provider_unavailable",
                "source_generation": job.retry_count, "source_result_file_id": job.result_file_id,
                "profile_id": policy.profile_id, "profile_sha256": policy.profile_sha256,
                "manifest_file_id": None}
        completed = self.job_repository.update_document_job_if_current(
            job.id,
            allowed_statuses={"running"},
            allowed_stages={"uploading"},
            expected_retry_count=job.retry_count,
            expected_document_ir_file_id=job.document_ir_file_id, require_no_prepared_result=True,
            preview_contribution=preview_contribution,
            status="succeeded",
            stage="completed",
            progress=100,
            completed_at=job.completed_at or utc_now(),
            updated_at=utc_now(),
        )
        if completed is None:
            return self.job_repository.get_document_job(job.id) or job
        self.record_event(
            completed,
            event_type="stage_succeeded",
            stage="completed",
            message="文档任务已确认完成。",
            payload={"result_file_id": completed.result_file_id},
            trace_id=trace_id,
        )
        return completed

    def mark_timed_out_if_needed(
        self,
        job: DocumentJobRecord,
        *,
        trace_id: str | None,
    ) -> DocumentJobRecord | None:
        if job.status in {"succeeded", "failed", "canceled"} or job.timeout_at is None or utc_now() < job.timeout_at:
            return None
        return self.mark_timed_out(job, trace_id=trace_id)

    def mark_timed_out(self, job: DocumentJobRecord, *, trace_id: str | None) -> DocumentJobRecord:
        return self.mark_failed(
            job,
            failed_stage=failure_policy.failed_stage_for_current_stage(job.stage),
            error_code="document_job_timeout",
            allow_prepared_result=True,
            error_message=f"P0 文档任务超过 {self.settings.p0_document_job_timeout_seconds} 秒超时限制。",
            trace_id=trace_id,
        )

    def fail_stage_attempt(
        self, job: DocumentJobRecord, error: Exception, *, trace_id: str | None,
    ) -> DocumentJobRecord:
        """只使用本调用已接收的阶段快照归类失败，持久化仍核对代数、IR 和结果空槽。"""

        if isinstance(error, SoftTimeLimitExceeded):
            self.logger.error(
                "[trace_id=%s job_id=%s generation=%s stage=%s status=failure_observed error_code=document_job_timeout]",
                trace_id, job.id, job.retry_count, job.stage,
            )
            return self.mark_timed_out(job, trace_id=trace_id)
        failed_stage, error_code, error_message = failure_policy.stage_attempt_failure(error, job.stage)
        # CAS 落败也保留原调用的安全诊断；外端异常正文和异常链不进入普通日志。
        self.logger.error(
            "[trace_id=%s job_id=%s generation=%s stage=%s status=failure_observed error_code=%s error_type=%s]",
            trace_id, job.id, job.retry_count, failed_stage, error_code, type(error).__name__,
        )
        return self.mark_failed(
            job, failed_stage=failed_stage, error_code=error_code,
            error_message=error_message, trace_id=trace_id,
            integrity=error.evidence if isinstance(error, (DocumentIRTranslationError, TranslationIntegrityError)) else None,
            formula_protection=error.formula_protection if isinstance(error, DocumentIRTranslationError) else None,
            failure_evidence=failure_policy.worker_failure_evidence(error),
        )

    def mark_failed(
        self,
        job: DocumentJobRecord,
        *,
        failed_stage: DocumentJobStage,
        error_code: str,
        error_message: str,
        trace_id: str | None,
        integrity: TranslationIntegrityEvidence | None = None,
        formula_protection: dict[str, str | int] | None = None,
        duration_ms: int | None = None,
        expected_prepared_result_file_id: str | None = None,
        allow_prepared_result: bool = False,
        failure_evidence: dict[str, Any] | None = None,
    ) -> DocumentJobRecord:
        now = utc_now()
        # 同代另一执行可能已经提交目标 IR；失败 CAS 不能跨过其原子 rendering 推进。
        failed = self.job_repository.update_document_job_if_current(
            job.id,
            allowed_statuses={"pending", "queued", "running"},
            allowed_stages={job.stage},
            expected_retry_count=job.retry_count,
            expected_document_ir_file_id=job.document_ir_file_id,
            require_no_prepared_result=not allow_prepared_result and expected_prepared_result_file_id is None,
            expected_prepared_result_file_id=expected_prepared_result_file_id,
            status="failed",
            stage="failed",
            failed_stage=failed_stage,
            error_code=error_code,
            error_message=error_message,
            completed_at=now,
            updated_at=now,
        )
        if failed is None:
            return self.job_repository.get_document_job(job.id) or job
        payload = {
            "error_code": error_code,
            "error_message": error_message,
            **build_renderer_event_summary(failure_evidence or {}),
            **({"prepared_result_file_id": failed.prepared_result.file.id} if failed.prepared_result else {}),
        }
        if integrity is not None:
            payload["integrity"] = integrity.to_dict()
        if formula_protection is not None:
            payload["formula_protection"] = formula_protection
        self.record_event(
            failed,
            event_type="stage_failed",
            stage=failed_stage,
            message="document_jobs Worker 执行失败。",
            payload=payload,
            trace_id=trace_id,
            level="error",
            duration_ms=duration_ms,
        )
        self.logger.error(
            "[trace_id=%s job_id=%s stage=%s status=failed] %s",
            trace_id,
            job.id,
            failed_stage,
            error_message,
        )
        return failed
