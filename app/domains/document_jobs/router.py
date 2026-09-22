from __future__ import annotations

# File: app/domains/document_jobs/router.py
# Purpose: 提供 document_jobs 创建、查询、批量操作和事件查询接口。

import hashlib
import hmac
from datetime import datetime
from datetime import timedelta
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import FileResponse, RedirectResponse

from app.api.dependencies import (
    get_runtime,
    get_trace_id,
    require_admin_user,
    require_current_user,
    require_current_user_or_admin_token_user,
)
from app.domains.audit.models import ActorContext
from app.domains.document_jobs.config_summary import build_document_job_config_summary
from app.domains.document_jobs.models import (
    DocumentJobEventRecord,
    DocumentJobRecord,
    DocumentJobTranslationBatchRecord,
)
from app.core.errors import ApiError
from app.domains.files.models import DocumentFileRecord
from app.domains.files.schemas import DocumentFileSummaryResponse
from app.domains.resources.models import utc_now
from app.domains.translation.modes import translation_mode_for_document_job_mode
from app.core.runtime import AppRuntime
from app.domains.document_jobs.schemas import (
    DocumentJobArchiveResponse,
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
)
from app.services.auth.models import AuthenticatedUser


router = APIRouter(prefix="/document-jobs", tags=["document-jobs"])
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
        items=[_build_document_job_response(runtime, user, job) for job in result.items],
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
    batches = runtime.document_job_service.list_translation_batches(job_id, user=user)
    generation = batches[0].generation if batches else runtime.document_job_service.get_job(job_id, user=user).retry_count
    return DocumentJobTranslationBatchListResponse(
        job_id=job_id,
        generation=generation,
        items=[_build_translation_batch_summary_response(batch) for batch in batches],
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
    return DocumentJobTranslationQaUpdateResponse(
        job_id=job.id,
        qa=_build_translation_qa_state_response(job),
        job=_build_document_job_response(runtime, user, job),
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
    expires_at = utc_now() + timedelta(seconds=runtime.settings.oss_download_presign_expires_seconds)
    if file.storage_provider == "s3":
        download_url = runtime.file_upload_service.create_presigned_download_url(
            file,
            expires_seconds=runtime.settings.oss_download_presign_expires_seconds,
        )
    else:
        token = _build_download_token(runtime, job_id=job.id, file_id=file.id, expires_at=expires_at)
        base_url = _externalize_url(str(request.url_for("download_document_job_result", job_id=job.id)), request=request)
        download_url = f"{base_url}?token={token}"
    runtime.document_job_service.record_download_authorized(
        job,
        file,
        expires_at=expires_at.isoformat(),
        trace_id=trace_id,
    )
    runtime.audit_service.record(
        actor=_actor_from_user(user),
        action="document_job.download_authorize",
        target_type="document_job",
        target_id=job.id,
        trace_id=trace_id,
    )
    return DocumentJobDownloadUrlResponse(
        job_id=job.id,
        file_id=file.id,
        download_url=download_url,
        expires_at=expires_at,
        file=_build_document_file_summary_response(file),
    )


@router.get("/{job_id}/download", name="download_document_job_result")
def download_document_job_result(
    job_id: str,
    token: str = Query(...),
    runtime: AppRuntime = Depends(get_runtime),
):
    file_id = _verify_download_token(runtime, job_id=job_id, token=token)
    _job, file = runtime.document_job_service.get_file_for_authorized_download(job_id, file_id=file_id)
    if file.storage_provider == "s3":
        download_url = runtime.file_upload_service.create_presigned_download_url(
            file,
            expires_seconds=runtime.settings.oss_download_presign_expires_seconds,
        )
        return RedirectResponse(download_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    path = runtime.file_upload_service.resolve_local_object_path(file.object_key)
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
) -> DocumentJobResponse:
    return DocumentJobResponse(
        **job.model_dump(mode="python"),
        translation_mode=translation_mode_for_document_job_mode(job.mode),
        available_actions=runtime.document_job_service.build_available_actions(job, user=user),
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
        lease_expires_at=batch.lease_expires_at,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
    )


def _build_document_file_quality_evidence(file: DocumentFileRecord) -> dict[str, Any]:
    """只把任务详情需要的质量证据白名单化输出，避免透传 raw metadata。"""

    if file.file_type not in {"generated_word", "document_ir"}:
        return {}
    metadata = file.metadata or {}
    evidence: dict[str, Any] = {}
    for key in DOCUMENT_JOB_QUALITY_METADATA_KEYS:
        value = metadata.get(key)
        if isinstance(value, str | int | float | bool):
            evidence[key] = value
    quality_flags = _read_string_list(metadata.get("quality_flags"))
    if quality_flags:
        evidence["quality_flags"] = quality_flags
    layout_quality_flags = _read_string_list(metadata.get("layout_quality_flags"))
    if layout_quality_flags:
        evidence["layout_quality_flags"] = layout_quality_flags
    review_issues = metadata.get("review_issues")
    if isinstance(review_issues, list):
        evidence["review_issues"] = [
            {key: issue[key] for key in ("code", "source_page", "block_id", "message")}
            for issue in review_issues
            if isinstance(issue, dict)
            and all(isinstance(issue.get(key), str) and issue[key].strip() for key in ("code", "block_id", "message"))
            and "source_page" in issue
            and (issue["source_page"] is None or (type(issue["source_page"]) is int and issue["source_page"] >= 1))
        ]
    docx_quality = metadata.get("docx_quality")
    if isinstance(docx_quality, dict):
        safe_docx_quality = {
            key: value
            for key in DOCUMENT_JOB_DOCX_QUALITY_KEYS
            if isinstance((value := docx_quality.get(key)), str | int | float | bool)
        }
        if safe_docx_quality:
            evidence["docx_quality"] = safe_docx_quality
    return evidence


def _build_translation_qa_state_response(job: DocumentJobRecord) -> DocumentJobTranslationQaStateResponse:
    return DocumentJobTranslationQaStateResponse(
        status=job.translation_qa_status,
        issue_type=job.translation_qa_issue_type,
        note=job.translation_qa_note,
        reviewed_by=job.translation_qa_reviewed_by,
        reviewed_at=job.translation_qa_reviewed_at,
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
