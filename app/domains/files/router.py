# File: app/domains/files/router.py
# Purpose: 提供 document_files 元数据、上传授权、quota enforcement、保留期管理和受控清理接口。

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.dependencies import get_runtime, get_trace_id, require_admin_user, require_current_user
from app.domains.audit.models import ActorContext, AuditDetails
from app.services.auth.models import AuthenticatedUser
from app.core.errors import ApiError
from app.domains.files.cleanup_execution import FileRetentionCleanupRunReport, FileRetentionCleanupRunService
from app.domains.files.cleanup_history import (
    FileRetentionCleanupPlanValidationError,
    FileRetentionCleanupRunHistoryRecord,
    FileRetentionCleanupRunHistoryService,
)
from app.domains.files.cleanup_lock import (
    FileRetentionCleanupLockConflict,
    FileRetentionCleanupLockRecord,
    FileRetentionCleanupLockService,
)
from app.domains.files.library_search import (
    FileLibrarySearchPage,
    FileLibrarySearchQuery,
    FileLibrarySearchService,
    FileLibrarySort,
)
from app.domains.files.models import DocumentFileRecord
from app.domains.files.quota_policy import (
    FileQuotaPolicyDryRunReport,
    FileQuotaPolicyDryRunService,
    FileQuotaPolicyEnforcementDecision,
)
from app.domains.files.retention import DocumentFileRetentionPlan, DocumentFileRetentionPlanner
from app.domains.files.retention_policy import (
    EffectiveFileRetentionPolicy,
    FileRetentionPolicyImpactReport,
    FileRetentionPolicyRecord,
    RETENTION_POLICY_FILE_TYPES,
)
from app.domains.files.service import FileRetentionDeleteReport
from app.domains.files.storage_usage import DocumentFileStorageUsageReporter, FileStorageUsageReport
from app.domains.files.validation import validate_pdf_metadata
from app.domains.files.schemas import (
    DocumentFileResponse,
    EffectiveFileRetentionPolicyResponse,
    FileRetentionDeleteExecuteRequest,
    FileRetentionDeletePreviewRequest,
    FileRetentionDeleteResponse,
    FileRetentionPolicyCreateRequest,
    FileRetentionPolicyImpactPreviewRequest,
    FileRetentionPolicyImpactResponse,
    FileRetentionPolicyListResponse,
    FileRetentionPolicyReasonRequest,
    FileRetentionPolicyResponse,
    FileRetentionPolicyUpdateRequest,
    FileRetentionPlanResponse,
    FileLibrarySearchResponse,
    FileQuotaPolicyConfigResponse,
    FileQuotaPolicyDryRunRequest,
    FileQuotaPolicyDryRunResponse,
    FileQuotaPolicySafetyResponse,
    FileQuotaPolicyUsageResponse,
    FileRetentionCleanupLockSummaryResponse,
    FileRetentionCleanupRunExecuteRequest,
    FileRetentionCleanupRunHistoryListResponse,
    FileRetentionCleanupRunHistoryResponse,
    FileRetentionCleanupRunPreviewRequest,
    FileRetentionCleanupRunResponse,
    FileRetentionCleanupRunSafetyResponse,
    FileRetentionCleanupSchedulerDryRunRequest,
    FileRetentionCleanupSchedulerDryRunResponse,
    FileRetentionSignedCleanupPlanResponse,
    FileStorageUsageResponse,
    FileUploadResponse,
    FileUploadUrlRequest,
    FileUploadUrlResponse,
)
from app.domains.files.scheduled_cleanup import FileRetentionCleanupReadonlyReport, FileRetentionReadonlyCleanupRunner
from app.core.runtime import AppRuntime


router = APIRouter(prefix="/files", tags=["files"])


@router.post("/upload-url", response_model=FileUploadUrlResponse, status_code=status.HTTP_201_CREATED)
def create_upload_url(
    payload: FileUploadUrlRequest,
    request: Request,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
    trace_id: str = Depends(get_trace_id),
) -> FileUploadUrlResponse:
    """创建上传授权；ready quota policy 超额时阻断，Admin override 可放行。"""

    validate_pdf_metadata(
        filename=payload.filename,
        content_type=payload.mime_type,
        size_bytes=payload.size_bytes,
        max_bytes=runtime.settings.jobs_upload_max_bytes,
    )
    quota_decision = _quota_policy_service(runtime).evaluate_upload_authorization(
        size_bytes=payload.size_bytes,
        file_type=payload.file_type,
        filename=payload.filename,
        actor_role=user.role,
        override_reason=payload.quota_override_reason,
        override_confirmation=payload.quota_override_confirmation,
    )
    if quota_decision.audit_action and quota_decision.audit_reason:
        runtime.audit_service.record(
            actor=_actor_from_user(user),
            action=quota_decision.audit_action,
            target_type="file_quota_policy",
            target_id="document_files",
            reason=quota_decision.audit_reason,
            details=_build_file_quota_policy_enforcement_audit_details(quota_decision),
            trace_id=trace_id,
        )
    if quota_decision.blocked:
        raise ApiError(
            status.HTTP_409_CONFLICT,
            "conflict",
            quota_decision.message or "文件上传授权被 quota policy 阻断。",
        )
    authorization = runtime.file_upload_service.create_upload_authorization(
        user=user,
        filename=payload.filename,
        mime_type=payload.mime_type,
        size_bytes=payload.size_bytes,
        checksum_sha256=payload.checksum_sha256,
        job_id=payload.job_id,
    )
    upload_url = authorization.upload_url or str(
        request.url_for("upload_file_content", file_id=authorization.record.id)
    )
    upload_url = _externalize_url(request, upload_url)
    runtime.audit_service.record(
        actor=_actor_from_user(user),
        action="file.upload_authorize",
        target_type="document_file",
        target_id=authorization.record.id,
        trace_id=trace_id,
    )
    return FileUploadUrlResponse(
        file_id=authorization.record.id,
        upload_url=upload_url,
        method=authorization.method,
        headers=authorization.headers,
        expires_at=authorization.expires_at,
        object_key=authorization.record.object_key,
        max_bytes=runtime.settings.jobs_upload_max_bytes,
        file=_build_document_file_response(authorization.record),
    )


@router.get("/retention/plan", response_model=FileRetentionPlanResponse)
def get_file_retention_plan(
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_admin_user),
) -> FileRetentionPlanResponse:
    """返回过期文件 metadata 候选计划，不修改文件状态或删除二进制。"""

    plan = _retention_planner(runtime).build_plan()
    return _build_file_retention_plan_response(plan, action_mode="dry_run")


@router.post("/retention/mark-expired", response_model=FileRetentionPlanResponse)
def mark_file_retention_expired(
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_admin_user),
    trace_id: str = Depends(get_trace_id),
) -> FileRetentionPlanResponse:
    """把当前过期候选标记为 expired；不删除本地文件或对象存储对象。"""

    planner = _retention_planner(runtime)
    preflight_plan = planner.build_plan()
    marked_file_ids = [
        candidate.file_id
        for candidate in preflight_plan.candidates
        if candidate.status == "uploaded"
    ]
    planner.mark_expired(now=preflight_plan.generated_at)
    plan = planner.build_plan(now=preflight_plan.generated_at)
    runtime.audit_service.record(
        actor=_actor_from_user(user),
        action="file.retention_mark_expired",
        target_type="document_file_retention",
        target_id="document_files",
        reason=f"marked={len(marked_file_ids)} candidates={len(preflight_plan.candidates)}",
        trace_id=trace_id,
    )
    return _build_file_retention_plan_response(
        plan,
        action_mode="mark_expired",
        marked_file_ids=marked_file_ids,
    )


@router.get("/retention/policies", response_model=FileRetentionPolicyListResponse)
def list_file_retention_policies(
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_admin_user),
) -> FileRetentionPolicyListResponse:
    """列出 Admin-only document_files retention policies，不修改任何记录。"""

    policies = runtime.file_retention_policy_service.list_policies()
    return FileRetentionPolicyListResponse(
        generated_at=_retention_planner(runtime).build_plan().generated_at,
        fallback_retention_days=runtime.settings.oss_file_retention_days,
        effective=[
            _build_effective_policy_response(
                file_type,
                runtime.file_retention_policy_service.resolve_effective_policy(file_type),
            )
            for file_type in sorted(RETENTION_POLICY_FILE_TYPES)
        ],
        items=[
            _build_file_retention_policy_response(policy, runtime=runtime)
            for policy in policies
        ],
    )


@router.get("/storage/usage", response_model=FileStorageUsageResponse)
def get_file_storage_usage(
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_admin_user),
) -> FileStorageUsageResponse:
    """返回 document_files storage usage metadata 估算，不执行清理或删除。"""

    report = _storage_usage_reporter(runtime).build_report()
    return _build_file_storage_usage_response(report)


@router.post("/quota-policy/dry-run", response_model=FileQuotaPolicyDryRunResponse)
def dry_run_file_quota_policy(
    payload: FileQuotaPolicyDryRunRequest,
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_admin_user),
) -> FileQuotaPolicyDryRunResponse:
    """预演拟上传文件的 quota policy 结果，不创建上传授权、不阻断上传。"""

    report = _quota_policy_service(runtime).dry_run(
        size_bytes=payload.size_bytes,
        file_type=payload.file_type.strip() or "source_pdf",
        filename=_normalize_optional_text(payload.filename),
    )
    return _build_file_quota_policy_dry_run_response(report)


@router.get("/library/search", response_model=FileLibrarySearchResponse)
def search_file_library(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
    sort: FileLibrarySort = "created_at_desc",
    q: str | None = None,
    file_type: str | None = None,
    status: str | None = None,
    storage_provider: str | None = None,
    job_id: str | None = None,
    created_by: str | None = None,
    expires_from: datetime | None = None,
    expires_to: datetime | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_admin_user),
) -> FileLibrarySearchResponse:
    """只读搜索 document_files metadata，返回不含对象定位信息的安全摘要。"""

    page_result = FileLibrarySearchService(runtime.document_file_repository).search(
        FileLibrarySearchQuery(
            page=page,
            page_size=page_size,
            sort=sort,
            q=_normalize_optional_text(q),
            file_type=_normalize_optional_text(file_type),
            status=_normalize_optional_text(status),
            storage_provider=_normalize_optional_text(storage_provider),
            job_id=_normalize_optional_text(job_id),
            created_by=_normalize_optional_text(created_by),
            expires_from=expires_from,
            expires_to=expires_to,
            created_from=created_from,
            created_to=created_to,
        )
    )
    return _build_file_library_search_response(page_result)


@router.post("/retention/policies", response_model=FileRetentionPolicyResponse, status_code=status.HTTP_201_CREATED)
def create_file_retention_policy(
    payload: FileRetentionPolicyCreateRequest,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_admin_user),
    trace_id: str = Depends(get_trace_id),
) -> FileRetentionPolicyResponse:
    """创建 draft retention policy；发布前不影响新文件或历史文件。"""

    policy = runtime.file_retention_policy_service.create_policy(
        name=payload.name,
        scope_type=payload.scope_type,
        file_type=payload.file_type,
        retention_days=payload.retention_days,
        description=payload.description,
        actor_id=user.id,
    )
    runtime.audit_service.record(
        actor=_actor_from_user(user),
        action="file.retention_policy_create",
        target_type="file_retention_policy",
        target_id=policy.policy_id,
        reason=_build_retention_policy_audit_reason("create", policy),
        trace_id=trace_id,
    )
    return _build_file_retention_policy_response(policy, runtime=runtime)


@router.get("/retention/policies/{policy_id}", response_model=FileRetentionPolicyResponse)
def get_file_retention_policy(
    policy_id: str,
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_admin_user),
) -> FileRetentionPolicyResponse:
    """读取单个 retention policy。"""

    policy = runtime.file_retention_policy_service.get_policy(policy_id)
    return _build_file_retention_policy_response(policy, runtime=runtime)


@router.patch("/retention/policies/{policy_id}", response_model=FileRetentionPolicyResponse)
def update_file_retention_policy(
    policy_id: str,
    payload: FileRetentionPolicyUpdateRequest,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_admin_user),
    trace_id: str = Depends(get_trace_id),
) -> FileRetentionPolicyResponse:
    """更新 draft retention policy；published/disabled policy 不允许直接编辑。"""

    policy = runtime.file_retention_policy_service.update_policy(
        policy_id,
        name=payload.name,
        scope_type=payload.scope_type,
        file_type=payload.file_type,
        retention_days=payload.retention_days,
        description=payload.description,
    )
    runtime.audit_service.record(
        actor=_actor_from_user(user),
        action="file.retention_policy_update",
        target_type="file_retention_policy",
        target_id=policy.policy_id,
        reason=_build_retention_policy_audit_reason("update", policy),
        trace_id=trace_id,
    )
    return _build_file_retention_policy_response(policy, runtime=runtime)


@router.post("/retention/policies/{policy_id}/impact-preview", response_model=FileRetentionPolicyImpactResponse)
def preview_file_retention_policy_impact(
    policy_id: str,
    _payload: FileRetentionPolicyImpactPreviewRequest,
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_admin_user),
) -> FileRetentionPolicyImpactResponse:
    """预览 retention policy 对历史 document_files 的影响，不修改文件 metadata。"""

    report = runtime.file_retention_policy_service.preview_policy_impact(policy_id)
    return _build_file_retention_policy_impact_response(report, runtime=runtime)


@router.post("/retention/policies/{policy_id}/publish", response_model=FileRetentionPolicyResponse)
def publish_file_retention_policy(
    policy_id: str,
    payload: FileRetentionPolicyReasonRequest,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_admin_user),
    trace_id: str = Depends(get_trace_id),
) -> FileRetentionPolicyResponse:
    """发布 draft retention policy，使其影响后续新文件 expires_at 计算。"""

    policy = runtime.file_retention_policy_service.publish_policy(
        policy_id,
        reason=payload.reason,
        actor_id=user.id,
    )
    runtime.audit_service.record(
        actor=_actor_from_user(user),
        action="file.retention_policy_publish",
        target_type="file_retention_policy",
        target_id=policy.policy_id,
        reason=_build_retention_policy_audit_reason("publish", policy),
        trace_id=trace_id,
    )
    return _build_file_retention_policy_response(policy, runtime=runtime)


@router.post("/retention/policies/{policy_id}/set-default", response_model=FileRetentionPolicyResponse)
def set_default_file_retention_policy(
    policy_id: str,
    payload: FileRetentionPolicyReasonRequest,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_admin_user),
    trace_id: str = Depends(get_trace_id),
) -> FileRetentionPolicyResponse:
    """把已发布 retention policy 设为同 scope 默认策略。"""

    policy = runtime.file_retention_policy_service.set_default_policy(
        policy_id,
        reason=payload.reason,
        actor_id=user.id,
    )
    runtime.audit_service.record(
        actor=_actor_from_user(user),
        action="file.retention_policy_set_default",
        target_type="file_retention_policy",
        target_id=policy.policy_id,
        reason=_build_retention_policy_audit_reason("set_default", policy),
        trace_id=trace_id,
    )
    return _build_file_retention_policy_response(policy, runtime=runtime)


@router.post("/retention/policies/{policy_id}/disable", response_model=FileRetentionPolicyResponse)
def disable_file_retention_policy(
    policy_id: str,
    payload: FileRetentionPolicyReasonRequest,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_admin_user),
    trace_id: str = Depends(get_trace_id),
) -> FileRetentionPolicyResponse:
    """禁用 draft 或 published retention policy；不删除策略历史。"""

    policy = runtime.file_retention_policy_service.disable_policy(
        policy_id,
        reason=payload.reason,
        actor_id=user.id,
    )
    runtime.audit_service.record(
        actor=_actor_from_user(user),
        action="file.retention_policy_disable",
        target_type="file_retention_policy",
        target_id=policy.policy_id,
        reason=_build_retention_policy_audit_reason("disable", policy),
        trace_id=trace_id,
    )
    return _build_file_retention_policy_response(policy, runtime=runtime)


@router.post("/retention/delete-preview", response_model=FileRetentionDeleteResponse)
def preview_file_retention_physical_delete(
    payload: FileRetentionDeletePreviewRequest,
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_admin_user),
) -> FileRetentionDeleteResponse:
    """预览 selected expired 文件物理删除结果，不修改 metadata 或二进制。"""

    report = runtime.file_upload_service.preview_retention_physical_delete(payload.file_ids)
    return _build_file_retention_delete_response(report)


@router.post("/retention/delete-expired", response_model=FileRetentionDeleteResponse)
def execute_file_retention_physical_delete(
    payload: FileRetentionDeleteExecuteRequest,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_admin_user),
    trace_id: str = Depends(get_trace_id),
) -> FileRetentionDeleteResponse:
    """执行 selected expired 文件物理删除，并保留 metadata 追溯信息。"""

    report = runtime.file_upload_service.execute_retention_physical_delete(
        payload.file_ids,
        reason=payload.reason,
        confirmation=payload.confirmation,
    )
    runtime.audit_service.record(
        actor=_actor_from_user(user),
        action="file.retention_physical_delete",
        target_type="document_file_retention",
        target_id="document_files",
        reason=_build_retention_delete_audit_reason(payload.reason, report),
        trace_id=trace_id,
    )
    return _build_file_retention_delete_response(report)


@router.post("/retention/cleanup-runs/preview", response_model=FileRetentionCleanupRunResponse)
def preview_file_retention_cleanup_run(
    payload: FileRetentionCleanupRunPreviewRequest,
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_admin_user),
) -> FileRetentionCleanupRunResponse:
    """预览精确 file_ids 的 cleanup run，不删除、不标记、不写审计。"""

    report = _cleanup_run_service(runtime).preview(
        file_ids=payload.file_ids,
        max_files=payload.max_files,
    )
    history_record = _cleanup_run_history_service(runtime).record_preview(
        report,
        signing_secret=_cleanup_plan_signing_secret(runtime),
    )
    return _build_cleanup_run_response(
        report,
        audit_events_written=False,
        history_recorded=True,
        signed_plan_verified=False,
        cleanup_plan=history_record.cleanup_plan,
    )


@router.post("/retention/cleanup-runs/execute", response_model=FileRetentionCleanupRunResponse)
def execute_file_retention_cleanup_run(
    payload: FileRetentionCleanupRunExecuteRequest,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_admin_user),
    trace_id: str = Depends(get_trace_id),
) -> FileRetentionCleanupRunResponse:
    """执行受控 cleanup run，内部复用 existing physical-delete safety contract。"""

    service = _cleanup_run_service(runtime)
    history_service = _cleanup_run_history_service(runtime)
    if (payload.plan_id or payload.plan_signature) and not payload.run_id:
        message = "plan_id/plan_signature 需要同时携带 run_id。"
        raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", message)
    if payload.run_id and history_service.get_run(payload.run_id) is None:
        message = "cleanup run history 不存在，请重新 preview 后再执行。"
        history_service.record_failed_execute(
            run_id=payload.run_id,
            file_ids=payload.file_ids,
            max_files=payload.max_files,
            preview_hash=payload.preview_hash,
            reason=payload.reason,
            error_code="cleanup_run_preview_not_found",
            error_message=message,
        )
        raise ApiError(status.HTTP_409_CONFLICT, "conflict", message)
    signed_plan_verified = False
    if payload.run_id:
        try:
            signed_plan_verified = history_service.validate_execute_plan(
                run_id=payload.run_id,
                file_ids=payload.file_ids,
                max_files=payload.max_files,
                preview_hash=payload.preview_hash,
                plan_id=payload.plan_id,
                plan_signature=payload.plan_signature,
            ) is not None
        except FileRetentionCleanupPlanValidationError as exc:
            history_service.record_failed_execute(
                run_id=payload.run_id,
                file_ids=payload.file_ids,
                max_files=payload.max_files,
                preview_hash=payload.preview_hash,
                reason=payload.reason,
                error_code=exc.error_code,
                error_message=exc.message,
            )
            raise ApiError(exc.status_code, exc.error_code if exc.status_code == 400 else "conflict", exc.message) from exc
    try:
        report = service.execute(
            file_ids=payload.file_ids,
            max_files=payload.max_files,
            preview_hash=payload.preview_hash,
            reason=payload.reason,
            confirmation=payload.confirmation,
            run_id=payload.run_id,
        )
    except ApiError as exc:
        if payload.run_id:
            history_service.record_failed_execute(
                run_id=payload.run_id,
                file_ids=payload.file_ids,
                max_files=payload.max_files,
                preview_hash=payload.preview_hash,
                reason=payload.reason,
                error_code=exc.code,
                error_message=exc.message,
            )
        raise
    runtime.audit_service.record(
        actor=_actor_from_user(user),
        action="file.retention_automated_cleanup_execute",
        target_type="document_file_retention_cleanup_run",
        target_id=report.run_id,
        reason=service.audit_reason(human_reason=payload.reason, report=report),
        trace_id=trace_id,
    )
    history_record = history_service.record_execute(
        report,
        reason=payload.reason,
        audit_events_written=True,
        signing_secret=_cleanup_plan_signing_secret(runtime),
        signed_plan_verified=signed_plan_verified,
    )
    return _build_cleanup_run_response(
        report,
        audit_events_written=True,
        history_recorded=True,
        signed_plan_verified=signed_plan_verified,
        cleanup_plan=history_record.cleanup_plan,
    )


@router.post("/retention/cleanup-runs/scheduler-dry-run", response_model=FileRetentionCleanupSchedulerDryRunResponse)
def run_file_retention_cleanup_scheduler_dry_run(
    payload: FileRetentionCleanupSchedulerDryRunRequest,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_admin_user),
    trace_id: str = Depends(get_trace_id),
) -> FileRetentionCleanupSchedulerDryRunResponse:
    """手动运行 scheduler dry-run；只获取 lock、生成只读报告、释放 lock 并记录 history。"""

    lock_service = _cleanup_lock_service(runtime)
    owner_id = _scheduler_dry_run_owner(payload.owner_id, user)
    try:
        lock = lock_service.acquire(
            owner_id=owner_id,
            ttl_seconds=payload.lock_ttl_seconds,
            metadata={
                "trigger": "manual_scheduler_dry_run",
                "trace_id": trace_id,
            },
        )
    except FileRetentionCleanupLockConflict as exc:
        raise ApiError(status.HTTP_409_CONFLICT, "conflict", exc.message) from exc

    lock_released = False
    try:
        report = _readonly_cleanup_runner(runtime).build_report()
        released_lock = lock_service.release(
            owner_id=lock.owner_id,
            fencing_token=lock.fencing_token,
            now=report.generated_at,
        )
        lock_released = True
        history_record = _cleanup_run_history_service(runtime).record_scheduler_dry_run(
            report,
            lock=released_lock,
            lock_released=lock_released,
        )
        return _build_cleanup_scheduler_dry_run_response(report, history_record)
    except FileRetentionCleanupLockConflict as exc:
        raise ApiError(status.HTTP_409_CONFLICT, "conflict", exc.message) from exc
    finally:
        if not lock_released:
            _release_cleanup_lock_quietly(lock_service, lock)


@router.get("/retention/cleanup-runs/history", response_model=FileRetentionCleanupRunHistoryListResponse)
def list_file_retention_cleanup_run_history(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_admin_user),
) -> FileRetentionCleanupRunHistoryListResponse:
    """列出 cleanup run durable history，不执行任何清理动作。"""

    items, total = _cleanup_run_history_service(runtime).list_runs(page=page, page_size=page_size)
    return FileRetentionCleanupRunHistoryListResponse(
        page=page,
        page_size=page_size,
        total=total,
        items=[_build_cleanup_run_history_response(item) for item in items],
    )


@router.get("/retention/cleanup-runs/history/{run_id}", response_model=FileRetentionCleanupRunHistoryResponse)
def get_file_retention_cleanup_run_history(
    run_id: str,
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_admin_user),
) -> FileRetentionCleanupRunHistoryResponse:
    """读取单条 cleanup run durable history，不返回对象路径或文件内容。"""

    record = _cleanup_run_history_service(runtime).get_run(run_id)
    if record is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", f"cleanup run history 不存在: {run_id}")
    return _build_cleanup_run_history_response(record)


@router.put(
    "/{file_id}/content",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
    name="upload_file_content",
)
async def upload_file_content(
    file_id: str,
    request: Request,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
    trace_id: str = Depends(get_trace_id),
) -> FileUploadResponse:
    content = await _read_body_with_limit(request, runtime.settings.jobs_upload_max_bytes)
    record = runtime.file_upload_service.upload_authorized_content(
        file_id=file_id,
        user=user,
        content=content,
        content_type=request.headers.get("content-type"),
    )
    runtime.audit_service.record(
        actor=_actor_from_user(user),
        action="file.upload_content",
        target_type="document_file",
        target_id=record.id,
        trace_id=trace_id,
    )
    return FileUploadResponse(file=_build_document_file_response(record))


@router.get("/{file_id}", response_model=DocumentFileResponse)
def get_document_file(
    file_id: str,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> DocumentFileResponse:
    return _build_document_file_response(runtime.file_upload_service.get_document_file(file_id, user=user))


async def _read_body_with_limit(request: Request, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        if not chunk:
            continue
        total += len(chunk)
        if total > max_bytes:
            raise ApiError(
                status.HTTP_413_CONTENT_TOO_LARGE,
                "file_too_large",
                f"上传文件超过大小限制 {max_bytes} bytes。",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _build_document_file_response(record: DocumentFileRecord) -> DocumentFileResponse:
    return DocumentFileResponse(**record.model_dump(mode="python"))


def _retention_planner(runtime: AppRuntime) -> DocumentFileRetentionPlanner:
    """按当前配置创建 document_files retention planner。"""

    return DocumentFileRetentionPlanner(
        runtime.document_file_repository,
        retention_days=runtime.settings.oss_file_retention_days,
    )


def _storage_usage_reporter(runtime: AppRuntime) -> DocumentFileStorageUsageReporter:
    """按当前运行态 readiness 构建只读 storage usage reporter。"""

    dependency_checks = runtime.health_service.build_dependency_checks()
    artifact_disk_free = dependency_checks.get("artifact_disk_free_bytes")
    return DocumentFileStorageUsageReporter(
        runtime.document_file_repository,
        artifact_storage=str(dependency_checks.get("artifact_storage") or runtime.settings.jobs_artifact_storage_backend),
        artifact_root_writable=_optional_bool(dependency_checks.get("artifact_root_writable")),
        artifact_disk_free_bytes=artifact_disk_free if isinstance(artifact_disk_free, int) else None,
        quota_bytes=runtime.settings.files_quota_bytes if runtime.settings.files_quota_bytes > 0 else None,
        warning_threshold_ratio=runtime.settings.files_quota_warning_threshold_ratio,
    )


def _quota_policy_service(runtime: AppRuntime) -> FileQuotaPolicyDryRunService:
    """按 runtime 构建 quota policy dry-run 和 enforcement service。"""

    return FileQuotaPolicyDryRunService(runtime.settings, runtime.document_file_repository)


def _cleanup_run_service(runtime: AppRuntime) -> FileRetentionCleanupRunService:
    """按 runtime 构建 cleanup run service，并只注入现有 file upload service。"""

    return FileRetentionCleanupRunService(runtime.file_upload_service)


def _cleanup_run_history_service(runtime: AppRuntime) -> FileRetentionCleanupRunHistoryService:
    """按 runtime 构建 cleanup run history service。"""

    return FileRetentionCleanupRunHistoryService(runtime.file_retention_cleanup_run_history_repository)


def _cleanup_lock_service(runtime: AppRuntime) -> FileRetentionCleanupLockService:
    """按 runtime 构建 cleanup lock service。"""

    return FileRetentionCleanupLockService(runtime.file_retention_cleanup_lock_repository)


def _readonly_cleanup_runner(runtime: AppRuntime) -> FileRetentionReadonlyCleanupRunner:
    """按 runtime 构建无副作用的 cleanup scheduler dry-run runner。"""

    return FileRetentionReadonlyCleanupRunner(
        _retention_planner(runtime),
        _storage_usage_reporter(runtime),
    )


def _scheduler_dry_run_owner(owner_id: str | None, user: AuthenticatedUser) -> str:
    """规范手动 scheduler dry-run 的 lock owner，缺省绑定当前 admin user。"""

    if owner_id is None:
        return f"manual:{user.id}"
    normalized_owner = owner_id.strip()
    return normalized_owner or f"manual:{user.id}"


def _release_cleanup_lock_quietly(
    lock_service: FileRetentionCleanupLockService,
    lock: FileRetentionCleanupLockRecord,
) -> None:
    """异常路径尽力释放 cleanup lock，释放失败时保留原始异常语义。"""

    try:
        lock_service.release(owner_id=lock.owner_id, fencing_token=lock.fencing_token)
    except FileRetentionCleanupLockConflict:
        return


def _cleanup_plan_signing_secret(runtime: AppRuntime) -> str:
    """读取 cleanup plan 签名 secret；缺失时拒绝生成弱签名。"""

    secret = runtime.settings.auth_jwt_secret_key.strip()
    if not secret:
        raise ApiError(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "cleanup_plan_signing_not_configured",
            "AUTH_JWT_SECRET_KEY 未配置，无法生成 cleanup run signed plan。",
        )
    return secret


def _build_file_storage_usage_response(report: FileStorageUsageReport) -> FileStorageUsageResponse:
    """把 storage usage report 映射为 API 响应。"""

    return FileStorageUsageResponse(**report.to_dict())


def _build_file_quota_policy_dry_run_response(report: FileQuotaPolicyDryRunReport) -> FileQuotaPolicyDryRunResponse:
    """把 quota dry-run report 映射为稳定 API 响应。"""

    return FileQuotaPolicyDryRunResponse(
        generated_at=report.generated_at,
        action_mode=report.action_mode,
        file_type=report.file_type,
        filename=report.filename,
        policy=FileQuotaPolicyConfigResponse(
            enabled=report.policy.enabled,
            dry_run=report.policy.dry_run,
            configured=report.policy.configured,
            quota_bytes=report.policy.quota_bytes,
            warning_threshold_ratio=report.policy.warning_threshold_ratio,
            block_threshold_ratio=report.policy.block_threshold_ratio,
            warning_threshold_bytes=report.policy.warning_threshold_bytes,
            block_threshold_bytes=report.policy.block_threshold_bytes,
            upload_max_bytes=report.policy.upload_max_bytes,
            status=report.policy.status,
            config_errors=report.policy.config_errors,
        ),
        usage=FileQuotaPolicyUsageResponse(
            current_used_size_bytes=report.usage.current_used_size_bytes,
            proposed_upload_size_bytes=report.usage.proposed_upload_size_bytes,
            projected_used_size_bytes=report.usage.projected_used_size_bytes,
            current_usage_ratio=report.usage.current_usage_ratio,
            projected_usage_ratio=report.usage.projected_usage_ratio,
        ),
        would_warn=report.would_warn,
        would_block=report.would_block,
        reasons=report.reasons,
        safety=FileQuotaPolicySafetyResponse(
            read_only=report.safety.read_only,
            upload_authorization_created=report.safety.upload_authorization_created,
            upload_content_written=report.safety.upload_content_written,
            upload_blocking_executed=report.safety.upload_blocking_executed,
            metadata_mutated=report.safety.metadata_mutated,
            audit_events_written=report.safety.audit_events_written,
            provider_calls_executed=report.safety.provider_calls_executed,
            delete_executed=report.safety.delete_executed,
            conversion_workflow_executed=report.safety.conversion_workflow_executed,
        ),
    )


def _build_file_quota_policy_enforcement_audit_details(
    decision: FileQuotaPolicyEnforcementDecision,
) -> AuditDetails:
    """生成 quota 阻断或 override 的结构化审计证据，不包含对象定位或文件内容。"""

    report = decision.report
    return {
        "generated_at": report.generated_at.isoformat(),
        "action_mode": "quota_policy_enforcement",
        "outcome": decision.audit_outcome(),
        "file_type": report.file_type,
        "filename": report.filename,
        "policy": {
            "enabled": report.policy.enabled,
            "dry_run": report.policy.dry_run,
            "configured": report.policy.configured,
            "quota_bytes": report.policy.quota_bytes,
            "warning_threshold_ratio": report.policy.warning_threshold_ratio,
            "block_threshold_ratio": report.policy.block_threshold_ratio,
            "warning_threshold_bytes": report.policy.warning_threshold_bytes,
            "block_threshold_bytes": report.policy.block_threshold_bytes,
            "status": report.policy.status,
            "config_errors": list(report.policy.config_errors),
        },
        "usage": {
            "current_used_size_bytes": report.usage.current_used_size_bytes,
            "proposed_upload_size_bytes": report.usage.proposed_upload_size_bytes,
            "projected_used_size_bytes": report.usage.projected_used_size_bytes,
            "current_usage_ratio": report.usage.current_usage_ratio,
            "projected_usage_ratio": report.usage.projected_usage_ratio,
        },
        "would_warn": report.would_warn,
        "would_block": report.would_block,
        "reasons": list(decision.reasons),
        "override": {
            "requested": decision.override_requested,
            "allowed": decision.override_allowed,
            "applied": decision.override_applied,
            "actor_role": decision.actor_role,
        },
        "safety": {
            "upload_blocking_executed": decision.blocked,
            "upload_authorization_created_by_quota_policy": False,
            "metadata_mutated_by_quota_policy": False,
            "upload_content_written": False,
            "audit_events_written": True,
            "provider_calls_executed": False,
            "delete_executed": False,
            "conversion_workflow_executed": False,
        },
    }


def _build_file_library_search_response(page: FileLibrarySearchPage) -> FileLibrarySearchResponse:
    """把文件库搜索 page 映射为不含对象定位信息的 API 响应。"""

    return FileLibrarySearchResponse(
        generated_at=page.generated_at,
        page=page.page,
        page_size=page.page_size,
        total=page.total,
        sort=page.sort,
        filters=page.filters,
        items=[item.to_dict() for item in page.items],
    )


def _build_file_retention_plan_response(
    plan: DocumentFileRetentionPlan,
    *,
    action_mode: str,
    marked_file_ids: list[str] | None = None,
) -> FileRetentionPlanResponse:
    """把 retention planner 输出映射为稳定的 API 响应。"""

    return FileRetentionPlanResponse(
        generated_at=plan.generated_at,
        retention_days=plan.retention_days,
        deletion_supported=False,
        action_mode=action_mode,
        totals=plan.totals,
        candidates=[
            candidate.to_dict()
            for candidate in plan.candidates
        ],
        marked_file_ids=marked_file_ids or [],
    )


def _build_file_retention_delete_response(report: FileRetentionDeleteReport) -> FileRetentionDeleteResponse:
    """把物理删除 report 映射为 API 响应。"""

    return FileRetentionDeleteResponse(
        generated_at=report.generated_at,
        action_mode=report.action_mode,
        requested_file_ids=report.requested_file_ids,
        confirmation_phrase=report.confirmation_phrase,
        totals=report.totals,
        items=[item.to_dict() for item in report.items],
    )


def _build_cleanup_run_response(
    report: FileRetentionCleanupRunReport,
    *,
    audit_events_written: bool,
    history_recorded: bool,
    signed_plan_verified: bool,
    cleanup_plan: object | None,
) -> FileRetentionCleanupRunResponse:
    """把 cleanup run report 映射为 API 响应。"""

    return FileRetentionCleanupRunResponse(
        run_id=report.run_id,
        generated_at=report.generated_at,
        action_mode=report.action_mode,
        confirmation_phrase=report.confirmation_phrase,
        preview_hash=report.preview_hash,
        requested_file_ids=report.requested_file_ids,
        max_files=report.max_files,
        physical_delete=_build_file_retention_delete_response(report.physical_delete),
        cleanup_plan=_build_signed_cleanup_plan_response(cleanup_plan),
        safety=FileRetentionCleanupRunSafetyResponse(
            physical_delete_executed=report.action_mode == "cleanup_execute",
            audit_events_written=audit_events_written,
            history_recorded=history_recorded,
            signed_plan_created=cleanup_plan is not None,
            signed_plan_verified=signed_plan_verified,
        ),
    )


def _build_cleanup_run_history_response(
    record: FileRetentionCleanupRunHistoryRecord,
) -> FileRetentionCleanupRunHistoryResponse:
    """把 cleanup run history record 映射为 API 响应。"""

    return FileRetentionCleanupRunHistoryResponse(**record.model_dump(mode="python"))


def _build_cleanup_scheduler_dry_run_response(
    report: FileRetentionCleanupReadonlyReport,
    history_record: FileRetentionCleanupRunHistoryRecord,
) -> FileRetentionCleanupSchedulerDryRunResponse:
    """把手动 scheduler dry-run history 映射为 API 响应。"""

    return FileRetentionCleanupSchedulerDryRunResponse(
        run_id=report.run_id,
        generated_at=report.generated_at,
        action_mode="scheduler_dry_run",
        readonly_report=history_record.readonly_report,
        lock=FileRetentionCleanupLockSummaryResponse(**history_record.lock),
        safety=history_record.safety,
    )


def _build_signed_cleanup_plan_response(cleanup_plan: object | None) -> FileRetentionSignedCleanupPlanResponse | None:
    """把 signed cleanup plan 模型映射为 API 响应。"""

    if cleanup_plan is None:
        return None
    if hasattr(cleanup_plan, "model_dump"):
        return FileRetentionSignedCleanupPlanResponse(**cleanup_plan.model_dump(mode="python"))
    return FileRetentionSignedCleanupPlanResponse.model_validate(cleanup_plan)


def _build_retention_delete_audit_reason(reason: str, report: FileRetentionDeleteReport) -> str:
    """生成 compact audit reason，避免把对象路径或文件内容写入审计。"""

    normalized_reason = " ".join(reason.strip().split())
    totals = report.totals
    return (
        f"reason={normalized_reason} requested={totals.get('requested', 0)} "
        f"deleted={totals.get('deleted', 0)} already_missing={totals.get('already_missing', 0)} "
        f"skipped={totals.get('skipped', 0)} failed={totals.get('failed', 0)}"
    )


def _build_file_retention_policy_response(
    policy: FileRetentionPolicyRecord,
    *,
    runtime: AppRuntime,
) -> FileRetentionPolicyResponse:
    """把 retention policy record 映射为 API 响应，并补充生效和匹配数量。"""

    matching_file_count = sum(
        1
        for record in runtime.document_file_repository.list_document_files()
        if policy.scope_type == "global" or record.file_type == policy.file_type
    )
    return FileRetentionPolicyResponse(
        **policy.model_dump(mode="python"),
        is_effective=policy.status == "published" and policy.is_default,
        effective_reason="published default policy" if policy.status == "published" and policy.is_default else None,
        matching_file_count=matching_file_count,
    )


def _build_effective_policy_response(
    requested_file_type: str,
    effective: EffectiveFileRetentionPolicy,
) -> EffectiveFileRetentionPolicyResponse:
    """映射某个 file_type 的有效策略摘要。"""

    return EffectiveFileRetentionPolicyResponse(
        retention_days=effective.retention_days,
        source=effective.source,
        policy_id=effective.policy_id,
        scope_type=effective.scope_type,
        file_type=effective.file_type or requested_file_type,
        reason=effective.reason,
    )


def _build_file_retention_policy_impact_response(
    report: FileRetentionPolicyImpactReport,
    *,
    runtime: AppRuntime,
) -> FileRetentionPolicyImpactResponse:
    """把 retention policy impact report 映射为 API 响应。"""

    return FileRetentionPolicyImpactResponse(
        generated_at=report.generated_at,
        policy=_build_file_retention_policy_response(report.policy, runtime=runtime),
        totals=report.totals,
        items=[
            {
                "file_id": item.file_id,
                "job_id": item.job_id,
                "file_type": item.file_type,
                "status": item.status,
                "storage_provider": item.storage_provider,
                "current_expires_at": item.current_expires_at,
                "projected_expires_at": item.projected_expires_at,
                "currently_expired": item.currently_expired,
                "would_be_expired": item.would_be_expired,
                "would_change_expires_at": item.would_change_expires_at,
            }
            for item in report.items
        ],
    )


def _optional_bool(value: object) -> bool | None:
    """只接受真实 bool readiness 值，避免把字符串误当状态。"""

    return value if isinstance(value, bool) else None


def _normalize_optional_text(value: str | None) -> str | None:
    """清理可选查询文本，空字符串视为未传。"""

    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _build_retention_policy_audit_reason(action: str, policy: FileRetentionPolicyRecord) -> str:
    """生成 compact policy audit reason，避免写入大 payload。"""

    parts = [
        f"action={action}",
        f"policy_id={policy.policy_id}",
        f"status={policy.status}",
        f"scope={policy.scope_type}",
        f"retention_days={policy.retention_days}",
    ]
    if policy.file_type:
        parts.append(f"file_type={policy.file_type}")
    if policy.reason:
        parts.append(f"reason={policy.reason}")
    return " ".join(parts)


def _actor_from_user(user: AuthenticatedUser) -> ActorContext:
    return ActorContext(actor_id=user.id, actor_role=user.role, source="jwt")


def _externalize_url(request: Request, url: str) -> str:
    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",", 1)[0].strip().lower()
    if not forwarded_proto:
        return url
    parsed = urlsplit(url)
    if parsed.scheme == forwarded_proto:
        return url
    return urlunsplit((forwarded_proto, parsed.netloc, parsed.path, parsed.query, parsed.fragment))
