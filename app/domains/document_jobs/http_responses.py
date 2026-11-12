"""document_jobs HTTP 响应构造：把用例结果映射为响应模型，并提供路由共用的 HTTP 辅助。"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit, urlunsplit

from fastapi import Request, status

from app.core.errors import ApiError
from app.core.runtime import AppRuntime
from app.domains.audit.models import ActorContext
from app.domains.document_jobs.delivery_state import translation_qa_projection
from app.domains.document_jobs.models import (
    DocumentJobEventRecord,
    DocumentJobRecord,
    DocumentJobTranslationBatchRecord,
)
from app.domains.document_jobs.schemas.jobs import (
    DocumentJobAvailableActionResponse,
    DocumentJobBulkItemResponse,
    DocumentJobBulkResponse,
    DocumentJobDeleteExecuteResponse,
    DocumentJobDeleteFileResponse,
    DocumentJobDeletePreviewResponse,
    DocumentJobDeleteSafetyResponse,
    DocumentJobEventResponse,
    DocumentJobResponse,
)
from app.domains.document_jobs.schemas.translation import (
    DocumentJobTranslationQaStateResponse,
    DocumentJobTranslationBatchListResponse,
    DocumentJobTranslationBatchSummaryResponse,
    DocumentJobTranslationBatchExecutionResponse,
)
from app.domains.document_jobs.use_cases.queries import TranslationBatchListView
from app.domains.files.models import DocumentFileRecord
from app.domains.files.schemas import DocumentFileSummaryResponse
from app.domains.translation.modes import translation_mode_for_document_job_mode
from app.services.auth.models import AuthenticatedUser
from app.services.renderer.render_event_summary import build_renderer_event_summary, controlled_quality_flags

DOCUMENT_JOB_BULK_LIMIT = 50
DOCUMENT_JOB_QUALITY_METADATA_KEYS = (
    "schema_version",
    "renderer_mode",
    "layout_page_count",
    "layout_block_count",
    "template_version_id",
)
DOCUMENT_JOB_DOCX_QUALITY_KEYS = (
    "editable_content_available",
    "image_only_suspected",
    "heading_paragraphs",
    "heading_like_unstyled_paragraphs",
    "numbering_paragraphs",
    "manual_list_marker_paragraphs",
    "toc_tab_leader_paragraphs",
    "plain_toc_entry_paragraphs",
    "table_count",
    "wide_table_count",
    "table_header_rows",
    "table_no_split_rows",
    "latex_residue_count",
)


def build_document_job_response(
    runtime: AppRuntime,
    user: AuthenticatedUser,
    job: DocumentJobRecord,
    *,
    available_actions: dict[str, DocumentJobAvailableActionResponse] | None = None,
) -> DocumentJobResponse:
    if available_actions is None:
        job, available_actions = runtime.document_job_use_cases.read_model.build_job_read_view(job, user=user)
    return DocumentJobResponse(
        **{**job.model_dump(mode="python"), **translation_qa_projection(job)},
        translation_mode=translation_mode_for_document_job_mode(job.mode),
        available_actions=available_actions,
    )


def build_document_job_delete_preview_response(plan: Any) -> DocumentJobDeletePreviewResponse:
    return DocumentJobDeletePreviewResponse(
        job_id=plan.job.id,
        action_mode="delete_preview",
        confirmation_phrase=plan.confirmation_phrase,
        preview_hash=plan.preview_hash,
        totals=plan.totals,
        files=[DocumentJobDeleteFileResponse(**item.to_response_dict()) for item in plan.files],
        safety=DocumentJobDeleteSafetyResponse(**plan.safety),
    )


def build_document_job_delete_execute_response(
    runtime: AppRuntime,
    user: AuthenticatedUser,
    plan: Any,
) -> DocumentJobDeleteExecuteResponse:
    return DocumentJobDeleteExecuteResponse(
        job_id=plan.job.id,
        action_mode="delete_execute",
        confirmation_phrase=plan.confirmation_phrase,
        preview_hash=plan.preview_hash,
        totals=plan.totals,
        files=[DocumentJobDeleteFileResponse(**item.to_response_dict()) for item in plan.files],
        safety=DocumentJobDeleteSafetyResponse(**plan.safety),
        job=build_document_job_response(runtime, user, plan.job),
    )


def build_document_job_event_response(event: DocumentJobEventRecord) -> DocumentJobEventResponse:
    return DocumentJobEventResponse(**event.model_dump(mode="python"))


def build_document_file_summary_response(file: DocumentFileRecord) -> DocumentFileSummaryResponse:
    return DocumentFileSummaryResponse(
        id=file.id,
        tenant_id=file.tenant_id,
        company_id=file.company_id,
        job_id=file.job_id,
        file_type=file.file_type,
        storage_provider=file.storage_provider,
        original_filename=file.original_filename,
        mime_type=file.mime_type,
        size_bytes=file.size_bytes,
        status=file.status,
        expires_at=file.expires_at,
        created_by=file.created_by,
        created_at=file.created_at,
        updated_at=file.updated_at,
        quality_evidence=build_document_file_quality_evidence(file),
    )


def build_translation_batch_summary_response(
    batch: DocumentJobTranslationBatchRecord,
    *,
    disposition: Any | None = None,
) -> DocumentJobTranslationBatchSummaryResponse:
    return DocumentJobTranslationBatchSummaryResponse(
        batch_id=batch.id,
        job_id=batch.job_id,
        generation=batch.generation,
        root_batch_id=batch.root_batch_id,
        parent_batch_id=batch.parent_batch_id,
        status=batch.status,
        page_start=batch.page_start,
        page_end=batch.page_end,
        item_count=batch.item_count,
        char_count=batch.char_count,
        split_level=batch.split_level,
        attempt_count=batch.attempt_count,
        max_attempts=batch.max_attempts,
        deterministic_batch_count=batch.deterministic_batch_count,
        provider_call_budget=batch.provider_call_budget,
        source_document_ir_file_id=batch.source_document_ir_file_id,
        result_file_id=batch.result_file_id,
        ai_call_log_file_ids=batch.ai_call_log_file_ids,
        debug_archive_file_ids=batch.debug_archive_file_ids,
        finish_reason=batch.finish_reason,
        usage=batch.usage,
        response_id=batch.response_id,
        error_code=batch.error_code,
        error_message=batch.error_message,
        retryable=batch.retryable,
        truncation_retry=batch.truncation_retry,
        is_effective_leaf=(disposition.is_effective_leaf if disposition is not None else batch.status != "split"),
        failure_disposition=(disposition.failure_disposition if disposition is not None else "none"),
        lease_expires_at=batch.lease_expires_at,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
    )


def build_document_file_quality_evidence(file: DocumentFileRecord) -> dict[str, Any]:
    """只把任务详情需要的质量证据白名单化输出，避免透传 raw metadata。"""

    if file.file_type not in {"generated_word", "document_ir"}:
        return {}
    metadata = file.metadata or {}
    if file.file_type == "generated_word" and (
            "renderer_content_contract_version" in metadata or "formula_source_coverage" in metadata):
        metadata = build_renderer_event_summary(metadata)
    evidence: dict[str, Any] = {}
    for key in DOCUMENT_JOB_QUALITY_METADATA_KEYS:
        value = metadata.get(key)
        if isinstance(value, str | int | float | bool):
            evidence[key] = value
    quality_flags = controlled_quality_flags(metadata.get("quality_flags"))
    if quality_flags:
        evidence["quality_flags"] = quality_flags
    layout_quality_flags = controlled_quality_flags(metadata.get("layout_quality_flags"))
    if layout_quality_flags:
        evidence["layout_quality_flags"] = layout_quality_flags
    docx_quality = build_renderer_event_summary(metadata).get("docx_quality")
    if isinstance(docx_quality, dict):
        safe_docx_quality = {
            key: value
            for key in DOCUMENT_JOB_DOCX_QUALITY_KEYS
            if type(value := docx_quality.get(key)) in {int, bool}
        }
        if safe_docx_quality:
            evidence["docx_quality"] = safe_docx_quality
    return evidence


def build_translation_qa_state_response(job: DocumentJobRecord) -> DocumentJobTranslationQaStateResponse:
    return DocumentJobTranslationQaStateResponse(
        **{key.removeprefix("translation_qa_"): value for key, value in translation_qa_projection(job).items()}
    )


def validate_document_job_bulk_ids(job_ids: list[str]) -> list[str]:
    """校验批量请求的 job_id 列表，并返回去除首尾空白后的值。"""

    normalized = [job_id.strip() for job_id in job_ids]
    if not normalized:
        raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "job_ids 不能为空。")
    if len(normalized) > DOCUMENT_JOB_BULK_LIMIT:
        raise ApiError(
            status.HTTP_400_BAD_REQUEST,
            "invalid_request",
            f"job_ids 最多支持 {DOCUMENT_JOB_BULK_LIMIT} 个。",
        )
    if any(not job_id for job_id in normalized):
        raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "job_ids 不能包含空值。")
    if len(set(normalized)) != len(normalized):
        raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "job_ids 不能重复。")
    return normalized


def build_document_job_bulk_success(
    runtime: AppRuntime,
    user: AuthenticatedUser,
    job: DocumentJobRecord,
) -> DocumentJobBulkItemResponse:
    """构造批量操作中单个成功任务的响应项。"""

    return DocumentJobBulkItemResponse(
        job_id=job.id,
        ok=True,
        status_code=status.HTTP_200_OK,
        job=build_document_job_response(runtime, user, job),
    )


def build_document_job_bulk_failure(job_id: str, exc: ApiError) -> DocumentJobBulkItemResponse:
    """构造批量操作中单个失败任务的响应项。"""

    return DocumentJobBulkItemResponse(
        job_id=job_id,
        ok=False,
        status_code=exc.status_code,
        error_code=exc.code,
        detail=exc.message,
    )


def build_document_job_bulk_response(
    action: str,
    items: list[DocumentJobBulkItemResponse],
) -> DocumentJobBulkResponse:
    """汇总批量操作的成功和失败数量。"""

    succeeded = sum(1 for item in items if item.ok)
    return DocumentJobBulkResponse(
        action=action,
        total=len(items),
        succeeded=succeeded,
        failed=len(items) - succeeded,
        items=items,
    )


def actor_from_user(user: AuthenticatedUser) -> ActorContext:
    return ActorContext(actor_id=user.id, actor_role=user.role, source="jwt")


def externalize_url(url: str, *, request: Request) -> str:
    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",", 1)[0].strip().lower()
    if not forwarded_proto:
        return url
    parsed = urlsplit(url)
    if parsed.scheme == forwarded_proto:
        return url
    return urlunsplit((forwarded_proto, parsed.netloc, parsed.path, parsed.query, parsed.fragment))


def build_translation_batch_list_response(
    job_id: str,
    view: TranslationBatchListView,
) -> DocumentJobTranslationBatchListResponse:
    execution = view.summary
    row_dispositions = {
        row.batch_id: row for row in execution.rows
    } if execution is not None else {}
    return DocumentJobTranslationBatchListResponse(
        job_id=job_id,
        generation=view.job.retry_count,
        items=[
            build_translation_batch_summary_response(
                batch,
                disposition=row_dispositions.get(batch.id),
            )
            for batch in view.batches
        ],
        execution=(
            DocumentJobTranslationBatchExecutionResponse(
                outcome=execution.outcome,
                leaf_count=execution.leaf_count,
                succeeded_leaf_count=execution.succeeded_leaf_count,
                active_leaf_count=execution.active_leaf_count,
                retryable_failed_leaf_count=execution.retryable_failed_leaf_count,
                terminal_failed_leaf_count=execution.terminal_failed_leaf_count,
                failure_batch_id=execution.failure_batch_id,
                reason_code=execution.reason_code,
                reason_message=execution.reason_message,
                partial_artifacts_debug_only=execution.partial_artifacts_debug_only,
            )
            if execution is not None else None
        ),
    )
