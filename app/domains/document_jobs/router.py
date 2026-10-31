from __future__ import annotations

# 文件：app/domains/document_jobs/router.py
# 用途：提供 document_jobs 创建、查询、批量操作和事件查询接口。

import base64
import binascii
import json
import hashlib
import hmac
from datetime import datetime
from datetime import timedelta
from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import FileResponse, RedirectResponse, Response

from app.api.dependencies import (
    get_runtime,
    get_trace_id,
    require_admin_user,
    require_current_user,
    require_current_user_or_admin_token_user,
)
from app.domains.audit.models import ActorContext
from app.domains.document_jobs.config_summary import build_document_job_config_summary
from app.domains.document_jobs.delivery_state import translation_qa_projection
from app.domains.document_jobs.quality_review_http import QualityReviewApiRoute, QUALITY_REVIEW_RESPONSES
from app.domains.document_jobs.review import ReviewExpectedSource
from app.domains.document_jobs.models import (
    DocumentJobEventRecord,
    DocumentJobRecord,
    DocumentJobTranslationBatchRecord,
)
from app.core.errors import ApiError
from app.api.errors import api_error_response
from app.domains.document_jobs.service import NewGenerationRequestUnavailable
from app.domains.files.models import DocumentFileRecord
from app.services.renderer.evidence import build_renderer_event_summary, controlled_quality_flags
from app.domains.files.schemas import DocumentFileSummaryResponse
from app.domains.resources.models import utc_now
from app.domains.translation.modes import translation_mode_for_document_job_mode
from app.core.runtime import AppRuntime
from app.domains.document_jobs.preview import preview_download_ttl, _is_preview_storage_error
from app.domains.document_jobs.schemas import (
    DocumentJobNewGenerationRequest, DocumentJobNewGenerationResponse, DocumentJobNewGenerationErrorResponse,
    DocumentJobTableReferenceListResponse,
    DocumentJobArchiveResponse,
    DocumentJobAvailableActionResponse,
    DocumentJobBulkItemResponse,
    DocumentJobBulkJobIdsRequest,
    DocumentJobBulkResponse,
    DocumentJobBulkRetryRequest,
    DocumentJobCloneRequest,
    DocumentJobCloneResponse,
    DocumentJobCancelResponse,
    DocumentJobCallbackMessageSummaryResponse,
    DocumentJobCreateRequest,
    DocumentJobCreateResponse,
    DocumentJobConfigSummaryResponse,
    DocumentJobDeleteExecuteRequest,
    DocumentJobDeleteExecuteResponse,
    DocumentJobDeleteFileResponse,
    DocumentJobDeletePreviewResponse,
    DocumentJobDeleteSafetyResponse,
    DocumentJobDownloadUrlResponse,
    DocumentJobEventListResponse,
    DocumentJobEventResponse,
    DocumentJobFileListResponse,
    DocumentJobListResponse,
    DocumentJobResponse,
    DocumentJobRetryRequest,
    DocumentJobRetryResponse,
    DocumentJobUnarchiveResponse,
    DocumentJobTranslationQaResponse,
    DocumentJobTranslationQaStateResponse,
    DocumentJobTranslationQaUpdateRequest,
    DocumentJobTranslationQaUpdateResponse,
    DocumentJobTranslationBatchListResponse,
    DocumentJobTranslationBatchSummaryResponse,
    DocumentJobTranslationBatchExecutionResponse,
)
from app.services.auth.models import AuthenticatedUser
from app.domains.document_jobs.schemas import (
    DocumentPublishRequest, DocumentPublishResponse, DocumentPublicationsResponse,
    DocumentPublicationDownloadUrlResponse, QualityId, QualityChecksum,
    DocumentQualityResponse,
    DocumentQualityTablesResponse,
    DocumentQualityPagesResponse,
    DocumentPreviewResponse,
    DocumentCurrentReviewResponse,
    DocumentReviewHistoryResponse,
    DocumentReviewUpdateRequest,
    DocumentReviewUpdateResponse,
    DocumentReviewBlocksResponse,
    DocumentReviewBlockDetailResponse,
)


router = APIRouter(prefix="/document-jobs", tags=["document-jobs"])
_quality_review_router = APIRouter(route_class=QualityReviewApiRoute)
DOCUMENT_JOB_BULK_LIMIT = 50
DOCUMENT_JOB_STATUS_GROUP_FILTER_VALUES = ("active",)
DOCUMENT_JOB_TRANSLATION_QA_STATUS_FILTER_VALUES = ("unreviewed", "approved", "needs_fix", "blocked", "all")
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


@router.post("", response_model=DocumentJobCreateResponse, status_code=status.HTTP_201_CREATED)
def create_document_job(
    payload: DocumentJobCreateRequest,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
    trace_id: str = Depends(get_trace_id),
) -> DocumentJobCreateResponse:
    _ensure_document_job_creation_ready(runtime)
    job = runtime.document_job_service.create_job(
        user=user,
        source_file_id=payload.source_file_id,
        mode=payload.mode,
        translation_mode=payload.translation_mode,
        document_language=payload.document_language,
        template_version_id=payload.template_version_id,
        term_version_id=payload.term_version_id,
        term_rule_set_id=payload.term_rule_set_id,
        term_rule_set_version=payload.term_rule_set_version,
        translation_term_set_id=payload.translation_term_set_id,
        translation_term_version=payload.translation_term_version,
        translation_profile_id=payload.translation_profile_id,
        translation_profile_version=payload.translation_profile_version,
        debug_full_text=payload.debug_full_text,
        trace_id=trace_id,
    )
    runtime.audit_service.record(
        actor=_actor_from_user(user),
        action="document_job.create",
        target_type="document_job",
        target_id=job.id,
        trace_id=trace_id,
    )
    return DocumentJobCreateResponse(
        job_id=job.id,
        status=job.status,
        stage=job.stage,
        progress=job.progress,
        job=_build_document_job_response(runtime, user, job),
    )


def _ensure_document_job_creation_ready(runtime: AppRuntime) -> None:
    dependency_checks = runtime.health_service.build_dependency_checks()
    required = bool(dependency_checks.get("p0_document_jobs_required", False))
    ready = bool(dependency_checks.get("p0_document_jobs_ready", not required))
    if not required or ready:
        return
    blockers = _read_string_list(dependency_checks.get("p0_document_jobs_blockers"))
    if not blockers:
        blockers = _read_string_list(dependency_checks.get("readiness_blockers"))
    message = "P0 文档任务执行链路未就绪，暂不能创建新任务。"
    if blockers:
        message = f"{message} 阻断项: {', '.join(blockers)}"
    raise ApiError(status.HTTP_503_SERVICE_UNAVAILABLE, "document_jobs_not_ready", message)


def _read_string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item.strip()]
    if isinstance(value, str) and value.strip():
        return [value]
    return []


@router.get("", response_model=DocumentJobListResponse)
def list_document_jobs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    status_group: str | None = Query(
        default=None,
        json_schema_extra={"enum": list(DOCUMENT_JOB_STATUS_GROUP_FILTER_VALUES)},
    ),
    translation_qa_status: str | None = Query(
        default=None,
        json_schema_extra={"enum": list(DOCUMENT_JOB_TRANSLATION_QA_STATUS_FILTER_VALUES)},
    ),
    q: str | None = Query(default=None),
    sort: str = Query(default="created_at_desc"),
    include_archived: bool = Query(default=False),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> DocumentJobListResponse:
    result = runtime.document_job_service.list_jobs(
        user=user,
        page=page,
        page_size=page_size,
        status_filter=status_filter.strip() if status_filter else None,
        status_group=status_group.strip() if status_group else None,
        translation_qa_status=translation_qa_status.strip() if translation_qa_status else None,
        q=q,
        sort=sort,
        include_archived=include_archived,
        created_from=created_from,
        created_to=created_to,
    )
    return DocumentJobListResponse(
        items=[_build_document_job_response(runtime, user, job, available_actions=actions)
               for job, actions in result.items],
        page=page,
        page_size=page_size,
        total=result.total,
        summary=result.summary,
        filtered_summary=result.filtered_summary,
        translation_qa_summary=result.translation_qa_summary,
    )


@router.get("/config-summary", response_model=DocumentJobConfigSummaryResponse)
def get_document_job_config_summary(
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user_or_admin_token_user),
) -> DocumentJobConfigSummaryResponse:
    return build_document_job_config_summary(runtime, user=user)


@router.post("/bulk-retry", response_model=DocumentJobBulkResponse)
def bulk_retry_document_jobs(
    payload: DocumentJobBulkRetryRequest,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
    trace_id: str = Depends(get_trace_id),
) -> DocumentJobBulkResponse:
    """批量重试 document_jobs，逐项复用单任务重试语义。"""

    job_ids = _validate_document_job_bulk_ids(payload.job_ids)
    items: list[DocumentJobBulkItemResponse] = []
    for job_id in job_ids:
        try:
            job = runtime.document_job_service.retry_job(
                job_id,
                user=user,
                reason=payload.reason,
                use_latest_term_assets=payload.use_latest_term_assets,
                term_rule_set_id=payload.term_rule_set_id,
                term_rule_set_version=payload.term_rule_set_version,
                translation_term_set_id=payload.translation_term_set_id,
                translation_term_version=payload.translation_term_version,
                trace_id=trace_id,
            )
        except ApiError as exc:
            items.append(_build_document_job_bulk_failure(job_id, exc))
            continue
        runtime.audit_service.record(
            actor=_actor_from_user(user),
            action="document_job.retry",
            target_type="document_job",
            target_id=job.id,
            reason=payload.reason,
            trace_id=trace_id,
        )
        items.append(_build_document_job_bulk_success(runtime, user, job))
    return _build_document_job_bulk_response("retry", items)


@router.post("/bulk-archive", response_model=DocumentJobBulkResponse)
def bulk_archive_document_jobs(
    payload: DocumentJobBulkJobIdsRequest,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
    trace_id: str = Depends(get_trace_id),
) -> DocumentJobBulkResponse:
    """批量归档终态 document_jobs，不删除文件或事件。"""

    job_ids = _validate_document_job_bulk_ids(payload.job_ids)
    items: list[DocumentJobBulkItemResponse] = []
    for job_id in job_ids:
        try:
            job = runtime.document_job_service.archive_job(job_id, user=user, trace_id=trace_id)
        except ApiError as exc:
            items.append(_build_document_job_bulk_failure(job_id, exc))
            continue
        runtime.audit_service.record(
            actor=_actor_from_user(user),
            action="document_job.archive",
            target_type="document_job",
            target_id=job.id,
            trace_id=trace_id,
        )
        items.append(_build_document_job_bulk_success(runtime, user, job))
    return _build_document_job_bulk_response("archive", items)


@router.post("/bulk-cancel", response_model=DocumentJobBulkResponse)
def bulk_cancel_document_jobs(
    payload: DocumentJobBulkJobIdsRequest,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
    trace_id: str = Depends(get_trace_id),
) -> DocumentJobBulkResponse:
    """批量取消未终态 document_jobs，保留所有文件和事件。"""

    job_ids = _validate_document_job_bulk_ids(payload.job_ids)
    items: list[DocumentJobBulkItemResponse] = []
    for job_id in job_ids:
        try:
            job = runtime.document_job_service.cancel_job(job_id, user=user, trace_id=trace_id)
        except ApiError as exc:
            items.append(_build_document_job_bulk_failure(job_id, exc))
            continue
        runtime.audit_service.record(
            actor=_actor_from_user(user),
            action="document_job.cancel",
            target_type="document_job",
            target_id=job.id,
            trace_id=trace_id,
        )
        items.append(_build_document_job_bulk_success(runtime, user, job))
    return _build_document_job_bulk_response("cancel", items)


@router.get("/{job_id}", response_model=DocumentJobResponse)
def get_document_job(
    job_id: str,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> DocumentJobResponse:
    return _build_document_job_response(runtime, user, runtime.document_job_service.get_job(job_id, user=user))


@router.get("/{job_id}/events", response_model=DocumentJobEventListResponse)
def get_document_job_events(
    job_id: str,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> DocumentJobEventListResponse:
    events = runtime.document_job_service.list_events(job_id, user=user)
    return DocumentJobEventListResponse(
        job_id=job_id,
        items=[_build_document_job_event_response(event) for event in events],
    )


@router.get("/{job_id}/files", response_model=DocumentJobFileListResponse)
def get_document_job_files(
    job_id: str,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> DocumentJobFileListResponse:
    files = runtime.document_job_service.list_files(job_id, user=user)
    return DocumentJobFileListResponse(
        job_id=job_id,
        files=[_build_document_file_summary_response(file) for file in files],
    )


@router.get("/{job_id}/translation-batches", response_model=DocumentJobTranslationBatchListResponse)
def get_document_job_translation_batches(
    job_id: str,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> DocumentJobTranslationBatchListResponse:
    job, batches = runtime.document_job_service.get_translation_batch_snapshot(job_id, user=user)
    generation = job.retry_count
    execution = runtime.document_job_execution_service.summarize_translation_generation(job, batches)
    row_dispositions = {
        row.batch_id: row for row in execution.rows
    } if execution is not None else {}
    return DocumentJobTranslationBatchListResponse(
        job_id=job_id,
        generation=generation,
        items=[
            _build_translation_batch_summary_response(
                batch,
                disposition=row_dispositions.get(batch.id),
            )
            for batch in batches
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


@router.get("/{job_id}/callback-messages/summary", response_model=DocumentJobCallbackMessageSummaryResponse)
def get_document_job_callback_message_summary(
    job_id: str,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> DocumentJobCallbackMessageSummaryResponse:
    """返回任务级 callback message 观测摘要，不暴露 callback payload。"""

    runtime.document_job_service.get_job(job_id, user=user)
    observation = runtime.document_job_recovery_service.build_callback_observation(job_id)
    return DocumentJobCallbackMessageSummaryResponse(**observation.to_summary())


@router.get("/{job_id}/translation-qa", response_model=DocumentJobTranslationQaResponse)
def get_document_job_translation_qa(
    job_id: str,
    limit: int = Query(default=200, ge=1, le=500),
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> DocumentJobTranslationQaResponse:
    return runtime.document_job_service.get_translation_qa(job_id, user=user, limit=limit)


@router.patch("/{job_id}/translation-qa", response_model=DocumentJobTranslationQaUpdateResponse)
def update_document_job_translation_qa(
    job_id: str,
    payload: DocumentJobTranslationQaUpdateRequest,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
    trace_id: str = Depends(get_trace_id),
) -> DocumentJobTranslationQaUpdateResponse:
    job = runtime.document_job_service.update_translation_qa(
        job_id,
        user=user,
        qa_status=payload.status,
        issue_type=payload.issue_type,
        note=payload.note,
        trace_id=trace_id,
    )
    job, actions = runtime.document_job_service.build_job_read_view(job, user=user)
    return DocumentJobTranslationQaUpdateResponse(
        job_id=job.id,
        qa=_build_translation_qa_state_response(job),
        job=_build_document_job_response(runtime, user, job, available_actions=actions),
    )


@router.post("/{job_id}/retry", response_model=DocumentJobRetryResponse)
def retry_document_job(
    job_id: str,
    payload: DocumentJobRetryRequest | None = None,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
    trace_id: str = Depends(get_trace_id),
) -> DocumentJobRetryResponse:
    reason = payload.reason if payload is not None else None
    job = runtime.document_job_service.retry_job(
        job_id,
        user=user,
        reason=reason,
        use_latest_term_assets=payload.use_latest_term_assets if payload is not None else False,
        term_rule_set_id=payload.term_rule_set_id if payload is not None else None,
        term_rule_set_version=payload.term_rule_set_version if payload is not None else None,
        translation_term_set_id=payload.translation_term_set_id if payload is not None else None,
        translation_term_version=payload.translation_term_version if payload is not None else None,
        trace_id=trace_id,
    )
    runtime.audit_service.record(
        actor=_actor_from_user(user),
        action="document_job.retry",
        target_type="document_job",
        target_id=job.id,
        reason=reason,
        trace_id=trace_id,
    )
    return DocumentJobRetryResponse(
        job_id=job.id,
        status=job.status,
        stage=job.stage,
        progress=job.progress,
        retry_count=job.retry_count,
        job=_build_document_job_response(runtime, user, job),
    )


@router.post("/{job_id}/clone", response_model=DocumentJobCloneResponse, status_code=status.HTTP_201_CREATED)
def clone_document_job(
    job_id: str,
    payload: DocumentJobCloneRequest | None = None,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
    trace_id: str = Depends(get_trace_id),
) -> DocumentJobCloneResponse:
    request_payload = payload or DocumentJobCloneRequest()
    job = runtime.document_job_service.clone_job(
        job_id,
        user=user,
        reason=request_payload.reason,
        config_strategy=request_payload.config_strategy,
        document_language=request_payload.document_language,
        template_version_id=request_payload.template_version_id,
        term_version_id=request_payload.term_version_id,
        term_rule_set_id=request_payload.term_rule_set_id,
        term_rule_set_version=request_payload.term_rule_set_version,
        translation_term_set_id=request_payload.translation_term_set_id,
        translation_term_version=request_payload.translation_term_version,
        translation_profile_id=request_payload.translation_profile_id,
        translation_profile_version=request_payload.translation_profile_version,
        debug_full_text=request_payload.debug_full_text,
        trace_id=trace_id,
    )
    runtime.audit_service.record(
        actor=_actor_from_user(user),
        action="document_job.clone",
        target_type="document_job",
        target_id=job.id,
        reason=request_payload.reason,
        details={
            "source_job_id": job_id,
            "config_strategy": request_payload.config_strategy,
        },
        trace_id=trace_id,
    )
    return DocumentJobCloneResponse(
        source_job_id=job_id,
        job_id=job.id,
        status=job.status,
        stage=job.stage,
        progress=job.progress,
        job=_build_document_job_response(runtime, user, job),
    )


@router.post("/{job_id}/cancel", response_model=DocumentJobCancelResponse)
def cancel_document_job(
    job_id: str,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
    trace_id: str = Depends(get_trace_id),
) -> DocumentJobCancelResponse:
    job = runtime.document_job_service.cancel_job(job_id, user=user, trace_id=trace_id)
    runtime.audit_service.record(
        actor=_actor_from_user(user),
        action="document_job.cancel",
        target_type="document_job",
        target_id=job.id,
        trace_id=trace_id,
    )
    return DocumentJobCancelResponse(
        job_id=job.id,
        status=job.status,
        stage=job.stage,
        canceled_at=job.canceled_at,
        job=_build_document_job_response(runtime, user, job),
    )


@router.post("/{job_id}/delete-preview", response_model=DocumentJobDeletePreviewResponse)
def preview_delete_document_job(
    job_id: str,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_admin_user),
) -> DocumentJobDeletePreviewResponse:
    plan = runtime.document_job_service.preview_delete_job(job_id, user=user)
    return _build_document_job_delete_preview_response(plan)


@router.post("/{job_id}/delete", response_model=DocumentJobDeleteExecuteResponse)
def delete_document_job(
    job_id: str,
    payload: DocumentJobDeleteExecuteRequest,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_admin_user),
    trace_id: str = Depends(get_trace_id),
) -> DocumentJobDeleteExecuteResponse:
    plan = runtime.document_job_service.delete_job(
        job_id,
        user=user,
        reason=payload.reason,
        confirmation=payload.confirmation,
        preview_hash=payload.preview_hash,
        trace_id=trace_id,
    )
    runtime.audit_service.record(
        actor=_actor_from_user(user),
        action="document_job.delete",
        target_type="document_job",
        target_id=plan.job.id,
        reason=plan.job.delete_reason,
        details={
            "preview_hash": payload.preview_hash,
            "totals": plan.totals,
            "safety": plan.safety,
        },
        trace_id=trace_id,
    )
    return _build_document_job_delete_execute_response(runtime, user, plan)


@router.delete("/{job_id}", response_model=DocumentJobArchiveResponse)
def archive_document_job(
    job_id: str,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
    trace_id: str = Depends(get_trace_id),
) -> DocumentJobArchiveResponse:
    job = runtime.document_job_service.archive_job(job_id, user=user, trace_id=trace_id)
    runtime.audit_service.record(
        actor=_actor_from_user(user),
        action="document_job.archive",
        target_type="document_job",
        target_id=job.id,
        trace_id=trace_id,
    )
    return DocumentJobArchiveResponse(
        job_id=job.id,
        archived_at=job.archived_at,
        job=_build_document_job_response(runtime, user, job),
    )


@router.post("/{job_id}/unarchive", response_model=DocumentJobUnarchiveResponse)
def unarchive_document_job(
    job_id: str,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
    trace_id: str = Depends(get_trace_id),
) -> DocumentJobUnarchiveResponse:
    restored_at = utc_now()
    job = runtime.document_job_service.unarchive_job(job_id, user=user, trace_id=trace_id)
    runtime.audit_service.record(
        actor=_actor_from_user(user),
        action="document_job.unarchive",
        target_type="document_job",
        target_id=job.id,
        trace_id=trace_id,
    )
    return DocumentJobUnarchiveResponse(
        job_id=job.id,
        restored_at=restored_at,
        job=_build_document_job_response(runtime, user, job),
    )


@router.get("/{job_id}/table-references", response_model=DocumentJobTableReferenceListResponse,
            responses={401: {"description": "缺少有效认证"}, 403: {"description": "无任务访问权限"},
                       404: {"description": "任务或 IR 不存在"}, 409: {"description": "快照或引用校验冲突"},
                       503: {"description": "资产存储不可用"}})
def list_document_job_table_references(
    job_id: str,
    response: Response,
    block_id: str | None = Query(default=None),
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
    trace_id: str = Depends(get_trace_id),
) -> DocumentJobTableReferenceListResponse:
    """列出当前权威 IR 的表格参考图，不公开内部存储定位。"""
    result = runtime.document_job_service.list_table_references(job_id, user=user, block_id=block_id)
    response.headers["Cache-Control"] = "private, no-store"
    runtime.audit_service.record(
        actor=_actor_from_user(user), action="document_job.table_reference_list", target_type="document_job",
        target_id=job_id, trace_id=trace_id,
        details={"job_id": job_id, "generation": result.generation, "ir_file_id": result.ir_file_id,
                 "item_count": len(result.items), "outcome": "succeeded"},
    )
    return result


@router.get("/{job_id}/table-references/{asset_id}/content", response_class=Response,
            responses={200: {"description": "受认证代理的原始栅格字节", "content": {
                "image/png": {"schema": {"type": "string", "format": "binary"}},
                "image/jpeg": {"schema": {"type": "string", "format": "binary"}},
                "image/gif": {"schema": {"type": "string", "format": "binary"}},
                "image/webp": {"schema": {"type": "string", "format": "binary"}},
                "image/bmp": {"schema": {"type": "string", "format": "binary"}},
                "image/tiff": {"schema": {"type": "string", "format": "binary"}},
            }}, 401: {"description": "缺少有效认证"}, 403: {"description": "无任务或文件访问权限"},
                404: {"description": "当前引用或内容不存在"}, 409: {"description": "快照、状态或完整性冲突"},
                503: {"description": "资产存储不可用"}})
def read_document_job_table_reference(
    job_id: str,
    asset_id: str,
    generation: int = Query(..., ge=0),
    ir_file_id: str = Query(..., min_length=1),
    disposition: Literal["inline", "attachment"] = Query(default="inline"),
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
    trace_id: str = Depends(get_trace_id),
) -> Response:
    """逐次鉴权并代理 local/S3 内容，不签发匿名 URL 或重定向。"""
    result = runtime.document_job_service.read_table_reference_content(
        job_id, asset_id, user=user, generation=generation, ir_file_id=ir_file_id, disposition=disposition)
    runtime.audit_service.record(
        actor=_actor_from_user(user), action="document_job.table_reference_read", target_type="document_job",
        target_id=job_id, trace_id=trace_id,
        details={"job_id": job_id, "asset_id": asset_id, "file_id": result.file_id, "ir_file_id": result.ir_file_id,
                 "generation": result.generation, "disposition": disposition, "outcome": "succeeded"},
    )
    return Response(result.content, media_type=result.mime_type, headers={
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
        "Content-Disposition": f'{disposition}; filename="{result.filename}"',
    })


@router.get("/{job_id}/download-url", response_model=DocumentJobDownloadUrlResponse)
def create_document_job_download_url(
    job_id: str,
    request: Request,
    file_id: str | None = Query(default=None),
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
    trace_id: str = Depends(get_trace_id),
) -> DocumentJobDownloadUrlResponse:
    job, file = runtime.document_job_service.get_file_for_download(job_id, user=user, file_id=file_id)
    policy = runtime.document_job_service.build_download_policy(job, file)
    expires_seconds = runtime.settings.oss_download_presign_expires_seconds
    if file.file_type.startswith("word_preview_"):
        expires_seconds = preview_download_ttl(
            job, file, runtime.document_file_repository, runtime.file_upload_service, expires_seconds=expires_seconds)
    expires_at = utc_now() + timedelta(seconds=expires_seconds)
    if file.storage_provider == "s3":
        download_url = runtime.file_upload_service.create_presigned_download_url(
            file,
            expires_seconds=expires_seconds,
        )
    else:
        token = _build_download_token(runtime, job_id=job.id, file_id=file.id, expires_at=expires_at)
        base_url = _externalize_url(str(request.url_for("download_document_job_result", job_id=job.id)), request=request)
        download_url = f"{base_url}?token={token}"
    runtime.document_job_service.record_download_authorized(
        job,
        file,
        policy=policy,
        expires_at=expires_at.isoformat(),
        trace_id=trace_id,
    )
    runtime.audit_service.record(
        actor=_actor_from_user(user),
        action="document_job.download_authorize",
        target_type="document_job",
        target_id=job.id,
        trace_id=trace_id,
        details={
            "generation": job.retry_count,
            "file_id": file.id,
            "classification": policy.classification,
            "warning_code": policy.warning_code,
        },
    )
    return DocumentJobDownloadUrlResponse(
        job_id=job.id,
        file_id=file.id,
        download_url=download_url,
        expires_at=expires_at,
        file=_build_document_file_summary_response(file),
        classification=policy.classification,
        warning_code=policy.warning_code,
        warning_message=policy.warning_message,
    )


@router.get("/{job_id}/download", name="download_document_job_result")
def download_document_job_result(
    job_id: str,
    token: str = Query(...),
    runtime: AppRuntime = Depends(get_runtime),
):
    file_id = _verify_download_token(runtime, job_id=job_id, token=token)
    job, file = runtime.document_job_service.get_file_for_authorized_download(job_id, file_id=file_id)
    if file.storage_provider == "s3":
        expires_seconds = runtime.settings.oss_download_presign_expires_seconds
        if file.file_type.startswith("word_preview_"):
            expires_seconds = preview_download_ttl(
                job, file, runtime.document_file_repository, runtime.file_upload_service, expires_seconds=expires_seconds)
        download_url = runtime.file_upload_service.create_presigned_download_url(
            file,
            expires_seconds=expires_seconds,
        )
        return RedirectResponse(download_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    path = runtime.file_upload_service.resolve_file_object_path(file)
    if not path.exists():
        raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", f"文件不存在: {file.id}")
    return FileResponse(
        path,
        media_type=file.mime_type,
        filename=file.original_filename,
    )


def _build_document_job_response(
    runtime: AppRuntime,
    user: AuthenticatedUser,
    job: DocumentJobRecord,
    *,
    available_actions: dict[str, DocumentJobAvailableActionResponse] | None = None,
) -> DocumentJobResponse:
    if available_actions is None:
        job, available_actions = runtime.document_job_service.build_job_read_view(job, user=user)
    return DocumentJobResponse(
        **{**job.model_dump(mode="python"), **translation_qa_projection(job)},
        translation_mode=translation_mode_for_document_job_mode(job.mode),
        available_actions=available_actions,
    )


def _build_document_job_delete_preview_response(plan: Any) -> DocumentJobDeletePreviewResponse:
    return DocumentJobDeletePreviewResponse(
        job_id=plan.job.id,
        action_mode="delete_preview",
        confirmation_phrase=plan.confirmation_phrase,
        preview_hash=plan.preview_hash,
        totals=plan.totals,
        files=[DocumentJobDeleteFileResponse(**item.to_response_dict()) for item in plan.files],
        safety=DocumentJobDeleteSafetyResponse(**plan.safety),
    )


def _build_document_job_delete_execute_response(
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
        job=_build_document_job_response(runtime, user, plan.job),
    )


def _build_document_job_event_response(event: DocumentJobEventRecord) -> DocumentJobEventResponse:
    return DocumentJobEventResponse(**event.model_dump(mode="python"))


def _build_document_file_summary_response(file: DocumentFileRecord) -> DocumentFileSummaryResponse:
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
        quality_evidence=_build_document_file_quality_evidence(file),
    )


def _build_translation_batch_summary_response(
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


def _build_document_file_quality_evidence(file: DocumentFileRecord) -> dict[str, Any]:
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


def _build_translation_qa_state_response(job: DocumentJobRecord) -> DocumentJobTranslationQaStateResponse:
    return DocumentJobTranslationQaStateResponse(
        **{key.removeprefix("translation_qa_"): value for key, value in translation_qa_projection(job).items()}
    )


def _validate_document_job_bulk_ids(job_ids: list[str]) -> list[str]:
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


def _build_document_job_bulk_success(
    runtime: AppRuntime,
    user: AuthenticatedUser,
    job: DocumentJobRecord,
) -> DocumentJobBulkItemResponse:
    """构造批量操作中单个成功任务的响应项。"""

    return DocumentJobBulkItemResponse(
        job_id=job.id,
        ok=True,
        status_code=status.HTTP_200_OK,
        job=_build_document_job_response(runtime, user, job),
    )


def _build_document_job_bulk_failure(job_id: str, exc: ApiError) -> DocumentJobBulkItemResponse:
    """构造批量操作中单个失败任务的响应项。"""

    return DocumentJobBulkItemResponse(
        job_id=job_id,
        ok=False,
        status_code=exc.status_code,
        error_code=exc.code,
        detail=exc.message,
    )


def _build_document_job_bulk_response(
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


def _actor_from_user(user: AuthenticatedUser) -> ActorContext:
    return ActorContext(actor_id=user.id, actor_role=user.role, source="jwt")


def _build_download_token(
    runtime: AppRuntime,
    *,
    job_id: str,
    file_id: str,
    expires_at,
) -> str:
    secret = _download_token_secret(runtime)
    expires_ts = int(expires_at.timestamp())
    message = f"{job_id}:{file_id}:{expires_ts}"
    signature = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{file_id}.{expires_ts}.{signature}"


def _verify_download_token(runtime: AppRuntime, *, job_id: str, token: str) -> str:
    parts = token.split(".")
    if len(parts) != 3:
        raise ApiError(status.HTTP_403_FORBIDDEN, "forbidden", "下载链接无效。")
    file_id, raw_expires_ts, signature = parts
    try:
        expires_ts = int(raw_expires_ts)
    except ValueError as exc:
        raise ApiError(status.HTTP_403_FORBIDDEN, "forbidden", "下载链接无效。") from exc
    if expires_ts < int(utc_now().timestamp()):
        raise ApiError(status.HTTP_403_FORBIDDEN, "forbidden", "下载链接已过期。")
    message = f"{job_id}:{file_id}:{expires_ts}"
    expected = hmac.new(
        _download_token_secret(runtime).encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise ApiError(status.HTTP_403_FORBIDDEN, "forbidden", "下载链接无效。")
    return file_id


def _externalize_url(url: str, *, request: Request) -> str:
    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",", 1)[0].strip().lower()
    if not forwarded_proto:
        return url
    parsed = urlsplit(url)
    if parsed.scheme == forwarded_proto:
        return url
    return urlunsplit((forwarded_proto, parsed.netloc, parsed.path, parsed.query, parsed.fragment))


def _download_token_secret(runtime: AppRuntime) -> str:
    secret = runtime.settings.auth_jwt_secret_key.strip()
    if not secret:
        raise ApiError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "service_unavailable",
            "AUTH_JWT_SECRET_KEY 未配置，无法生成临时下载链接。",
        )
    return secret


# 专用子路由拥有九项操作；旧 QA、下载和全局异常处理保持原入口。
@_quality_review_router.get("/{job_id}/quality", response_model=DocumentQualityResponse,
                           responses=QUALITY_REVIEW_RESPONSES)
def get_document_job_quality(
    job_id: str,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> DocumentQualityResponse:
    """读取后端权威质量摘要、有效复核与可用动作。"""
    return runtime.document_job_service.get_document_quality(job_id, user=user)


@_quality_review_router.get("/{job_id}/quality/tables", response_model=DocumentQualityTablesResponse,
                           responses=QUALITY_REVIEW_RESPONSES)
def get_document_job_quality_tables(
    job_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> DocumentQualityTablesResponse:
    """分页读取严格认证后、经过白名单投影的表格证据。"""
    return runtime.document_job_service.get_document_quality_tables(job_id, user=user, limit=limit, cursor=cursor)


@_quality_review_router.get("/{job_id}/quality/pages", response_model=DocumentQualityPagesResponse,
                           responses=QUALITY_REVIEW_RESPONSES)
def get_document_job_quality_pages(
    job_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> DocumentQualityPagesResponse:
    """读取已有页级报告，保留未检查、不完整与低置信来源。"""
    return runtime.document_job_service.get_document_quality_pages(job_id, user=user, limit=limit, cursor=cursor)


@_quality_review_router.get("/{job_id}/preview", response_model=DocumentPreviewResponse,
                           responses=QUALITY_REVIEW_RESPONSES)
def get_document_job_preview_metadata(
    job_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> DocumentPreviewResponse:
    """只返回当前预览的已验证元数据和文件 ID，不生产或签发下载链接。"""
    return runtime.document_job_service.get_document_preview(job_id, user=user, limit=limit, cursor=cursor)


@_quality_review_router.get("/{job_id}/review", response_model=DocumentCurrentReviewResponse,
                           responses=QUALITY_REVIEW_RESPONSES)
def get_document_job_review(
    job_id: str,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> DocumentCurrentReviewResponse:
    """读取同一次主件观察对应的有效复核与后端动作。"""
    return runtime.document_job_service.get_document_review(job_id, user=user)


@_quality_review_router.get("/{job_id}/review/history", response_model=DocumentReviewHistoryResponse,
                           responses=QUALITY_REVIEW_RESPONSES)
def list_document_job_review_history(
    job_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> DocumentReviewHistoryResponse:
    """按固定序号高水位窗口读取追加历史。"""
    return runtime.document_job_service.get_document_review_history(job_id, user=user, limit=limit, cursor=cursor)


@_quality_review_router.patch("/{job_id}/review", response_model=DocumentReviewUpdateResponse,
                             responses=QUALITY_REVIEW_RESPONSES)
def update_document_job_review(
    job_id: str,
    payload: DocumentReviewUpdateRequest,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
    trace_id: str = Depends(get_trace_id),
) -> DocumentReviewUpdateResponse:
    """按客户端观察来源提交一次复核；异常响应不代表记录必然未提交。"""
    return runtime.document_job_service.submit_document_review_with_source(
        job_id,
        user=user,
        review_status=payload.status,
        issue_type=payload.issue_type,
        note=payload.note,
        expected_source=ReviewExpectedSource.model_validate(payload.expected_source.model_dump()),
        trace_id=trace_id,
    )


@_quality_review_router.get("/{job_id}/review/blocks", response_model=DocumentReviewBlocksResponse,
                           responses=QUALITY_REVIEW_RESPONSES)
def list_document_job_review_blocks(
    job_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    source_page_index: int | None = Query(default=None, ge=0),
    block_type: Literal["heading", "paragraph", "table", "image", "list", "formula"] | None = None,
    problem: Literal["all", "flagged"] = "all",
    severity: Literal["all", "blocker", "warning", "info"] = "all",
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
    trace_id: str = Depends(get_trace_id),
) -> DocumentReviewBlocksResponse:
    """有限读取当前 IR 的内容导航；筛选不把页级候选当块级缺陷。"""
    result = runtime.document_job_service.list_document_review_blocks(job_id, user=user, limit=limit,
        cursor=cursor, source_page_index=source_page_index, block_type=block_type, problem=problem, severity=severity)
    runtime.audit_service.record(actor=_actor_from_user(user), action="document_job.review_blocks",
        target_type="document_job", target_id=job_id, trace_id=trace_id,
        details={"generation": result.source.generation, "item_count": len(result.items), "outcome": result.availability})
    return result


@_quality_review_router.get("/{job_id}/review/blocks/{block_id}", response_model=DocumentReviewBlockDetailResponse,
                           responses=QUALITY_REVIEW_RESPONSES)
def get_document_job_review_block(
    job_id: str,
    block_id: str,
    snapshot_id: str = Query(pattern=r"^[0-9a-f]{64}$"),
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = Query(default=None),
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
    trace_id: str = Depends(get_trace_id),
) -> DocumentReviewBlockDetailResponse:
    """读取已选来源中的内容分片、术语及批次摘要，不触发任何生产者。"""
    result = runtime.document_job_service.get_document_review_block(job_id, block_id, user=user,
        snapshot_id=snapshot_id, limit=limit, cursor=cursor)
    runtime.audit_service.record(actor=_actor_from_user(user), action="document_job.review_block",
        target_type="document_job", target_id=job_id, trace_id=trace_id,
        details={"generation": result.source.generation, "item_count": len(result.items), "outcome": "succeeded"})
    return result


router.include_router(_quality_review_router)


_new_generation_router = APIRouter(route_class=QualityReviewApiRoute)
_NEW_GENERATION_RESPONSES = {
    **{code: value for code, value in QUALITY_REVIEW_RESPONSES.items() if code != 400},
    200: {**QUALITY_REVIEW_RESPONSES[200], "model": DocumentJobNewGenerationResponse,
        "description": "已接受请求的只读事实和当前任务观察；不会重新投递。"},
    202: {**QUALITY_REVIEW_RESPONSES[200], "model": DocumentJobNewGenerationResponse,
        "description": "新代命令已接受；不代表生成已经成功。"},
    503: {**QUALITY_REVIEW_RESPONSES[503], "model": DocumentJobNewGenerationErrorResponse,
        "description": "接受结果未知或已接受后投递异常；保留原 UUID 并通过 GET 对账，禁止自动换 key。"},
    404: {**QUALITY_REVIEW_RESPONSES[404], "description": "可见任务、原源 PDF 实物或指定接受记录不存在。"},
    409: {**QUALITY_REVIEW_RESPONSES[409], "description": "来源、预算、任务状态或原 UUID 的身份与参数冲突。"},
    500: {**QUALITY_REVIEW_RESPONSES[500],
        "description": "服务内部错误；接受可能已提交，请保留原 UUID，使用 GET generation-requests/{request_id} 对账。"},
}


def _new_generation_unavailable_response(request: Request, error: NewGenerationRequestUnavailable):
    response = api_error_response(request, error.status_code, error.code, error.message, reason_code=error.reason_code)
    content = json.loads(response.body)
    content["error"]["generation_request_id"] = error.generation_request_id
    if error.accepted_generation is not None:
        content["error"].update(accepted=True, accepted_generation=error.accepted_generation)
    from fastapi.responses import JSONResponse
    return JSONResponse(content, status_code=error.status_code)


@_new_generation_router.post("/{job_id}/new-generation", response_model=DocumentJobNewGenerationResponse,
    status_code=202, responses=_NEW_GENERATION_RESPONSES)
def request_document_job_new_generation(job_id: str, payload: DocumentJobNewGenerationRequest,
    request: Request, response: Response, runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_admin_user), trace_id: str = Depends(get_trace_id),
):
    """仅内部 Admin JWT 可显式开始同任务的新代；重放只返回接受事实。"""
    try:
        result, created = runtime.document_job_service.request_new_generation(job_id, user=user,
            request_id=payload.request_id, note=payload.note,
            expected_source=ReviewExpectedSource.model_validate(payload.expected_source.model_dump()), trace_id=trace_id)
    except NewGenerationRequestUnavailable as error:
        return _new_generation_unavailable_response(request, error)
    response.status_code = 202 if created else 200
    return result


@_new_generation_router.get("/{job_id}/generation-requests/{request_id}", response_model=DocumentJobNewGenerationResponse,
    responses={code: value for code, value in _NEW_GENERATION_RESPONSES.items() if code != 202})
def get_document_job_generation_request(job_id: str, request_id: UUID, request: Request,
    runtime: AppRuntime = Depends(get_runtime), user: AuthenticatedUser = Depends(require_current_user),
):
    """主库同任务串行读取原 Admin 的接受事实，不补投或补写。"""
    try:
        return runtime.document_job_service.get_generation_request(job_id, request_id=str(request_id), user=user)
    except NewGenerationRequestUnavailable as error:
        return _new_generation_unavailable_response(request, error)


router.include_router(_new_generation_router)


_publication_router = APIRouter(route_class=QualityReviewApiRoute)
_PUBLICATION_WRITE_RESPONSES = {
    **QUALITY_REVIEW_RESPONSES,
    200: {**QUALITY_REVIEW_RESPONSES[200], "model": DocumentPublishResponse, "description": "同一幂等键与参数重放，返回已提交记录。"},
    201: {**QUALITY_REVIEW_RESPONSES[200], "model": DocumentPublishResponse, "description": "首次发布成功，事实、任务投影和成功审计已原子提交。"},
}


@_publication_router.post("/{job_id}/publish", response_model=DocumentPublishResponse,
    status_code=201, responses=_PUBLICATION_WRITE_RESPONSES)
def publish_document(job_id: str, payload: DocumentPublishRequest, response: Response,
                     runtime: AppRuntime = Depends(get_runtime), user: AuthenticatedUser = Depends(require_admin_user),
                     trace_id: str = Depends(get_trace_id)):
    result, created = runtime.document_job_service.publish_document(job_id, user=user,
        request_id=payload.request_id, note=payload.note, expected_source=payload.expected_source, trace_id=trace_id)
    response.status_code = 201 if created else 200
    return result


@_publication_router.get("/{job_id}/publications", response_model=DocumentPublicationsResponse,
    responses=QUALITY_REVIEW_RESPONSES)
def list_document_publications(job_id: str, runtime: AppRuntime = Depends(get_runtime),
                               user: AuthenticatedUser = Depends(require_current_user)):
    return runtime.document_job_service.list_document_publications(job_id, user=user)


_PUBLICATION_DOWNLOAD_RESPONSES = {
    code: {**details, "description": ("最终件下载认证失败；未知错误仅返回安全 trace。" if code == 500
        else "已授权的发布最终件或短期下载入口。" if code == 200 else details["description"])}
    for code, details in QUALITY_REVIEW_RESPONSES.items() if code != 400
}


class _PublicationDownloadClaims(BaseModel):
    """用途与版本参与签名；字段严格限制，不能复用内部草稿 token。"""
    model_config = ConfigDict(extra="forbid", strict=True)
    purpose: Literal["publication_download/v1"] = "publication_download/v1"
    job_id: QualityId
    publication_id: QualityId
    result_file_id: QualityId
    result_sha256: QualityChecksum
    expires_ts: StrictInt = Field(gt=0)


def _build_publication_download_token(runtime, claims: _PublicationDownloadClaims) -> str:
    message = json.dumps(claims.model_dump(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    encoded = base64.urlsafe_b64encode(message).decode("ascii").rstrip("=")
    signature = hmac.new(_download_token_secret(runtime).encode("utf-8"), message, hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def _verify_publication_download_token(runtime, *, job_id, publication_id, token):
    invalid = ApiError(403, "forbidden", "最终件下载链接无效。", reason_code="publication_download_token_invalid")
    if len(token) > 2048:
        raise invalid
    try:
        encoded, signature = token.split(".")
        message = base64.b64decode(encoded + "=" * (-len(encoded) % 4), altchars=b"-_", validate=True)
        expected = hmac.new(_download_token_secret(runtime).encode("utf-8"), message, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise invalid
        claims = _PublicationDownloadClaims.model_validate_json(message)
        if claims.job_id != job_id or claims.publication_id != publication_id:
            raise invalid
        canonical = _build_publication_download_token(runtime, claims)
        if not hmac.compare_digest(token, canonical):
            raise invalid
    except (ValueError, TypeError, UnicodeError, binascii.Error):
        raise invalid from None
    if claims.expires_ts <= utc_now().timestamp():
        raise ApiError(403, "forbidden", "最终件下载链接已过期。", reason_code="publication_download_token_expired")
    return claims


@_publication_router.get("/{job_id}/publications/{publication_id}/download-url",
    response_model=DocumentPublicationDownloadUrlResponse, responses=_PUBLICATION_DOWNLOAD_RESPONSES)
def create_document_publication_download_url(job_id: str, publication_id: str, request: Request,
    runtime: AppRuntime = Depends(get_runtime), user: AuthenticatedUser = Depends(require_current_user),
    trace_id: str = Depends(get_trace_id)):
    """签发绑定不可变记录的短期最终件入口，审计失败不交付 URL。"""
    job, record, file = runtime.document_job_service.get_publication_file_for_download(
        job_id, publication_id, user=user, trace_id=trace_id)
    try:
        expires_seconds = runtime.settings.oss_download_presign_expires_seconds
        if expires_seconds <= 0:
            raise ApiError(503, "service_unavailable", "最终件下载有效期配置不可用。", reason_code="publication_storage_unavailable")
        expires_at = (utc_now() + timedelta(seconds=expires_seconds)).replace(microsecond=0)
        if file.storage_provider == "s3":
            download_url = runtime.file_upload_service.create_presigned_download_url(file, expires_seconds=expires_seconds)
        else:
            token = _build_publication_download_token(runtime, _PublicationDownloadClaims(job_id=job.id,
                publication_id=record.id, result_file_id=file.id, result_sha256=record.result_sha256,
                expires_ts=int(expires_at.timestamp())))
            base_url = _externalize_url(str(request.url_for("download_document_publication_result",
                job_id=job.id, publication_id=record.id)), request=request)
            download_url = f"{base_url}?token={token}"
        runtime.document_job_service.check_publication_download_current(job, record, file)
    except ApiError as error:
        runtime.document_job_service.record_publication_download_audit(job, user=user, trace_id=trace_id,
            reason_code=error.reason_code)
        raise
    except Exception as error:
        if not _is_preview_storage_error(error):
            raise
        runtime.document_job_service.record_publication_download_audit(job, user=user, trace_id=trace_id,
            reason_code="publication_storage_unavailable")
        raise ApiError(503, "service_unavailable", "发布存储暂不可用。", reason_code="publication_storage_unavailable") from None
    runtime.document_job_service.record_publication_download_audit(job, user=user, trace_id=trace_id, record=record)
    if expires_at <= utc_now():
        raise ApiError(403, "forbidden", "最终件下载链接已过期，请重新申请。", reason_code="publication_download_token_expired")
    return DocumentPublicationDownloadUrlResponse(publication_id=record.id, job_id=job.id,
        result_file_id=file.id, result_sha256=record.result_sha256, size_bytes=file.size_bytes,
        download_url=download_url, expires_at=expires_at)


@_publication_router.get("/{job_id}/publications/{publication_id}/download",
    name="download_document_publication_result", response_class=FileResponse, responses=_PUBLICATION_DOWNLOAD_RESPONSES)
def download_document_publication_result(job_id: str, publication_id: str, token: str = Query(...),
    runtime: AppRuntime = Depends(get_runtime)):
    """能力取件重验记录、descriptor、真实字节和安全路径，不伪造 JWT 审计。"""
    claims = _verify_publication_download_token(runtime, job_id=job_id, publication_id=publication_id, token=token)
    record, file = runtime.document_job_service.get_publication_file_for_authorized_download(job_id, publication_id,
        result_file_id=claims.result_file_id, result_sha256=claims.result_sha256)
    if file.storage_provider == "s3":
        raise ApiError(409, "conflict", "发布结果存储身份已变化。", reason_code="publication_download_source_changed")
    path = runtime.file_upload_service.resolve_file_object_path(file)
    return FileResponse(path, media_type=file.mime_type, filename=file.original_filename,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


router.include_router(_publication_router)
