"""document_jobs 主路由：任务创建、查询、批量与生命周期操作、事件、文件、翻译批次、翻译 QA 与表格引用。

下载、质量与复核、发布入口在各自子路由模块，由本模块按原顺序挂载。
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response

from app.api.dependencies import (
    get_runtime,
    get_trace_id,
    require_admin_user,
    require_current_user,
    require_current_user_or_admin_token_user,
)
from app.core.errors import ApiError
from app.core.runtime import AppRuntime
from app.domains.document_jobs.config_summary import build_document_job_config_summary
from app.domains.document_jobs.downloads_router import downloads_router
from app.domains.document_jobs.failure_diagnostic import project_failure_diagnostic
from app.domains.document_jobs.http_responses import (
    actor_from_user,
    build_document_job_response,
    build_document_job_bulk_failure,
    build_document_job_bulk_response,
    build_document_job_bulk_success,
    build_document_job_delete_execute_response,
    build_document_job_delete_preview_response,
    build_document_job_event_response,
    build_document_file_summary_response,
    build_translation_batch_list_response,
    build_translation_qa_state_response,
    validate_document_job_bulk_ids,
)
from app.domains.document_jobs.publication_router import publication_router
from app.domains.document_jobs.quality_review_router import quality_review_router
from app.domains.document_jobs.schemas.config import DocumentJobConfigSummaryResponse
from app.domains.document_jobs.schemas.jobs import (
    DocumentJobArchiveResponse,
    DocumentJobBulkItemResponse,
    DocumentJobBulkJobIdsRequest,
    DocumentJobBulkResponse,
    DocumentJobBulkRetryRequest,
    DocumentJobCloneRequest,
    DocumentJobCloneResponse,
    DocumentJobCancelResponse,
    DocumentJobCreateRequest,
    DocumentJobCreateResponse,
    DocumentJobDeleteExecuteRequest,
    DocumentJobDeleteExecuteResponse,
    DocumentJobDeletePreviewResponse,
    DocumentJobEventListResponse,
    DocumentJobFileListResponse,
    DocumentJobListResponse,
    DocumentJobResponse,
    DocumentJobRetryRequest,
    DocumentJobRetryResponse,
    DocumentJobUnarchiveResponse,
)
from app.domains.document_jobs.schemas.translation import (
    DocumentJobTableReferenceListResponse,
    DocumentJobCallbackMessageSummaryResponse,
    DocumentJobTranslationQaResponse,
    DocumentJobTranslationQaUpdateRequest,
    DocumentJobTranslationQaUpdateResponse,
    DocumentJobTranslationBatchListResponse,
)
from app.domains.resources.models import utc_now
from app.services.auth.models import AuthenticatedUser


router = APIRouter(prefix="/document-jobs", tags=["document-jobs"])
DOCUMENT_JOB_STATUS_GROUP_FILTER_VALUES = ("active",)
DOCUMENT_JOB_TRANSLATION_QA_STATUS_FILTER_VALUES = ("unreviewed", "approved", "needs_fix", "blocked", "all")


@router.post("", response_model=DocumentJobCreateResponse, status_code=status.HTTP_201_CREATED)
def create_document_job(
    payload: DocumentJobCreateRequest,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
    trace_id: str = Depends(get_trace_id),
) -> DocumentJobCreateResponse:
    _ensure_document_job_creation_ready(runtime)
    job = runtime.document_job_use_cases.submission.create_job(
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
        actor=actor_from_user(user),
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
        job=build_document_job_response(runtime, user, job),
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
    result = runtime.document_job_use_cases.queries.list_jobs(
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
        items=[build_document_job_response(runtime, user, job, available_actions=actions)
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

    job_ids = validate_document_job_bulk_ids(payload.job_ids)
    items: list[DocumentJobBulkItemResponse] = []
    for job_id in job_ids:
        try:
            job = runtime.document_job_use_cases.submission.retry_job(
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
            items.append(build_document_job_bulk_failure(job_id, exc))
            continue
        runtime.audit_service.record(
            actor=actor_from_user(user),
            action="document_job.retry",
            target_type="document_job",
            target_id=job.id,
            reason=payload.reason,
            trace_id=trace_id,
        )
        items.append(build_document_job_bulk_success(runtime, user, job))
    return build_document_job_bulk_response("retry", items)


@router.post("/bulk-archive", response_model=DocumentJobBulkResponse)
def bulk_archive_document_jobs(
    payload: DocumentJobBulkJobIdsRequest,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
    trace_id: str = Depends(get_trace_id),
) -> DocumentJobBulkResponse:
    """批量归档终态 document_jobs，不删除文件或事件。"""

    job_ids = validate_document_job_bulk_ids(payload.job_ids)
    items: list[DocumentJobBulkItemResponse] = []
    for job_id in job_ids:
        try:
            job = runtime.document_job_use_cases.lifecycle_commands.archive_job(job_id, user=user, trace_id=trace_id)
        except ApiError as exc:
            items.append(build_document_job_bulk_failure(job_id, exc))
            continue
        runtime.audit_service.record(
            actor=actor_from_user(user),
            action="document_job.archive",
            target_type="document_job",
            target_id=job.id,
            trace_id=trace_id,
        )
        items.append(build_document_job_bulk_success(runtime, user, job))
    return build_document_job_bulk_response("archive", items)


@router.post("/bulk-cancel", response_model=DocumentJobBulkResponse)
def bulk_cancel_document_jobs(
    payload: DocumentJobBulkJobIdsRequest,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
    trace_id: str = Depends(get_trace_id),
) -> DocumentJobBulkResponse:
    """批量取消未终态 document_jobs，保留所有文件和事件。"""

    job_ids = validate_document_job_bulk_ids(payload.job_ids)
    items: list[DocumentJobBulkItemResponse] = []
    for job_id in job_ids:
        try:
            job = runtime.document_job_use_cases.lifecycle_commands.cancel_job(job_id, user=user, trace_id=trace_id)
        except ApiError as exc:
            items.append(build_document_job_bulk_failure(job_id, exc))
            continue
        runtime.audit_service.record(
            actor=actor_from_user(user),
            action="document_job.cancel",
            target_type="document_job",
            target_id=job.id,
            trace_id=trace_id,
        )
        items.append(build_document_job_bulk_success(runtime, user, job))
    return build_document_job_bulk_response("cancel", items)


@router.get("/{job_id}", response_model=DocumentJobResponse)
def get_document_job(
    job_id: str,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> DocumentJobResponse:
    use_cases = runtime.document_job_use_cases
    job = use_cases.access.get_job(job_id, user=user)
    response = build_document_job_response(runtime, user, job)
    if job.status == "failed":
        # 仅详情读取事件；列表不做逐行事件查询。
        response.failure_diagnostic = project_failure_diagnostic(job, use_cases.queries.list_events(job_id, user=user))
    return response


@router.get("/{job_id}/events", response_model=DocumentJobEventListResponse)
def get_document_job_events(
    job_id: str,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> DocumentJobEventListResponse:
    events = runtime.document_job_use_cases.queries.list_events(job_id, user=user)
    return DocumentJobEventListResponse(
        job_id=job_id,
        items=[build_document_job_event_response(event) for event in events],
    )


@router.get("/{job_id}/files", response_model=DocumentJobFileListResponse)
def get_document_job_files(
    job_id: str,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> DocumentJobFileListResponse:
    files = runtime.document_job_use_cases.queries.list_files(job_id, user=user)
    return DocumentJobFileListResponse(
        job_id=job_id,
        files=[build_document_file_summary_response(file) for file in files],
    )


@router.get("/{job_id}/translation-batches", response_model=DocumentJobTranslationBatchListResponse)
def get_document_job_translation_batches(
    job_id: str,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> DocumentJobTranslationBatchListResponse:
    view = runtime.document_job_use_cases.queries.get_translation_batch_view(job_id, user=user)
    return build_translation_batch_list_response(job_id, view)


@router.get("/{job_id}/callback-messages/summary", response_model=DocumentJobCallbackMessageSummaryResponse)
def get_document_job_callback_message_summary(
    job_id: str,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> DocumentJobCallbackMessageSummaryResponse:
    """返回任务级 callback message 观测摘要，不暴露 callback payload。"""

    runtime.document_job_use_cases.access.get_job(job_id, user=user)
    observation = runtime.document_job_recovery_service.build_callback_observation(job_id)
    return DocumentJobCallbackMessageSummaryResponse(**observation.to_summary())


@router.get("/{job_id}/translation-qa", response_model=DocumentJobTranslationQaResponse)
def get_document_job_translation_qa(
    job_id: str,
    limit: int = Query(default=200, ge=1, le=500),
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> DocumentJobTranslationQaResponse:
    return runtime.document_job_use_cases.translation_qa.get_translation_qa(job_id, user=user, limit=limit)


@router.patch("/{job_id}/translation-qa", response_model=DocumentJobTranslationQaUpdateResponse)
def update_document_job_translation_qa(
    job_id: str,
    payload: DocumentJobTranslationQaUpdateRequest,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
    trace_id: str = Depends(get_trace_id),
) -> DocumentJobTranslationQaUpdateResponse:
    job = runtime.document_job_use_cases.translation_qa.update_translation_qa(
        job_id,
        user=user,
        qa_status=payload.status,
        issue_type=payload.issue_type,
        note=payload.note,
        trace_id=trace_id,
    )
    job, actions = runtime.document_job_use_cases.read_model.build_job_read_view(job, user=user)
    return DocumentJobTranslationQaUpdateResponse(
        job_id=job.id,
        qa=build_translation_qa_state_response(job),
        job=build_document_job_response(runtime, user, job, available_actions=actions),
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
    job = runtime.document_job_use_cases.submission.retry_job(
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
        actor=actor_from_user(user),
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
        job=build_document_job_response(runtime, user, job),
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
    job = runtime.document_job_use_cases.submission.clone_job(
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
        actor=actor_from_user(user),
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
        job=build_document_job_response(runtime, user, job),
    )


@router.post("/{job_id}/cancel", response_model=DocumentJobCancelResponse)
def cancel_document_job(
    job_id: str,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
    trace_id: str = Depends(get_trace_id),
) -> DocumentJobCancelResponse:
    job = runtime.document_job_use_cases.lifecycle_commands.cancel_job(job_id, user=user, trace_id=trace_id)
    runtime.audit_service.record(
        actor=actor_from_user(user),
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
        job=build_document_job_response(runtime, user, job),
    )


@router.post("/{job_id}/delete-preview", response_model=DocumentJobDeletePreviewResponse)
def preview_delete_document_job(
    job_id: str,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_admin_user),
) -> DocumentJobDeletePreviewResponse:
    plan = runtime.document_job_use_cases.lifecycle_commands.preview_delete_job(job_id, user=user)
    return build_document_job_delete_preview_response(plan)


@router.post("/{job_id}/delete", response_model=DocumentJobDeleteExecuteResponse)
def delete_document_job(
    job_id: str,
    payload: DocumentJobDeleteExecuteRequest,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_admin_user),
    trace_id: str = Depends(get_trace_id),
) -> DocumentJobDeleteExecuteResponse:
    plan = runtime.document_job_use_cases.lifecycle_commands.delete_job(
        job_id,
        user=user,
        reason=payload.reason,
        confirmation=payload.confirmation,
        preview_hash=payload.preview_hash,
        trace_id=trace_id,
    )
    runtime.audit_service.record(
        actor=actor_from_user(user),
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
    return build_document_job_delete_execute_response(runtime, user, plan)


@router.delete("/{job_id}", response_model=DocumentJobArchiveResponse)
def archive_document_job(
    job_id: str,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
    trace_id: str = Depends(get_trace_id),
) -> DocumentJobArchiveResponse:
    job = runtime.document_job_use_cases.lifecycle_commands.archive_job(job_id, user=user, trace_id=trace_id)
    runtime.audit_service.record(
        actor=actor_from_user(user),
        action="document_job.archive",
        target_type="document_job",
        target_id=job.id,
        trace_id=trace_id,
    )
    return DocumentJobArchiveResponse(
        job_id=job.id,
        archived_at=job.archived_at,
        job=build_document_job_response(runtime, user, job),
    )


@router.post("/{job_id}/unarchive", response_model=DocumentJobUnarchiveResponse)
def unarchive_document_job(
    job_id: str,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
    trace_id: str = Depends(get_trace_id),
) -> DocumentJobUnarchiveResponse:
    restored_at = utc_now()
    job = runtime.document_job_use_cases.lifecycle_commands.unarchive_job(job_id, user=user, trace_id=trace_id)
    runtime.audit_service.record(
        actor=actor_from_user(user),
        action="document_job.unarchive",
        target_type="document_job",
        target_id=job.id,
        trace_id=trace_id,
    )
    return DocumentJobUnarchiveResponse(
        job_id=job.id,
        restored_at=restored_at,
        job=build_document_job_response(runtime, user, job),
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
    result = runtime.document_job_use_cases.table_references.list_table_references(job_id, user=user, block_id=block_id)
    response.headers["Cache-Control"] = "private, no-store"
    runtime.audit_service.record(
        actor=actor_from_user(user), action="document_job.table_reference_list", target_type="document_job",
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
    result = runtime.document_job_use_cases.table_references.read_table_reference_content(
        job_id, asset_id, user=user, generation=generation, ir_file_id=ir_file_id, disposition=disposition)
    runtime.audit_service.record(
        actor=actor_from_user(user), action="document_job.table_reference_read", target_type="document_job",
        target_id=job_id, trace_id=trace_id,
        details={"job_id": job_id, "asset_id": asset_id, "file_id": result.file_id, "ir_file_id": result.ir_file_id,
                 "generation": result.generation, "disposition": disposition, "outcome": "succeeded"},
    )
    return Response(result.content, media_type=result.mime_type, headers={
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
        "Content-Disposition": f'{disposition}; filename="{result.filename}"',
    })


# 子路由按拆分前的注册顺序挂载：下载 → 质量与复核（含新代请求）→ 发布。
router.include_router(downloads_router)
router.include_router(quality_review_router)
router.include_router(publication_router)
