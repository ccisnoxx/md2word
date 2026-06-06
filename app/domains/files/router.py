# File: app/domains/files/router.py
# Purpose: 提供 document_files 元数据、上传授权、本地代理上传、保留期管理和物理删除接口。

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Depends, Request, status

from app.api.dependencies import get_runtime, get_trace_id, require_admin_user, require_current_user
from app.domains.audit.models import ActorContext
from app.services.auth.models import AuthenticatedUser
from app.core.errors import ApiError
from app.domains.files.models import DocumentFileRecord
from app.domains.files.retention import DocumentFileRetentionPlan, DocumentFileRetentionPlanner
from app.domains.files.service import FileRetentionDeleteReport
from app.domains.files.schemas import (
    DocumentFileResponse,
    FileRetentionDeleteExecuteRequest,
    FileRetentionDeletePreviewRequest,
    FileRetentionDeleteResponse,
    FileRetentionPlanResponse,
    FileUploadResponse,
    FileUploadUrlRequest,
    FileUploadUrlResponse,
)
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


def _build_retention_delete_audit_reason(reason: str, report: FileRetentionDeleteReport) -> str:
    """生成 compact audit reason，避免把对象路径或文件内容写入审计。"""

    normalized_reason = " ".join(reason.strip().split())
    totals = report.totals
    return (
        f"reason={normalized_reason} requested={totals.get('requested', 0)} "
        f"deleted={totals.get('deleted', 0)} already_missing={totals.get('already_missing', 0)} "
        f"skipped={totals.get('skipped', 0)} failed={totals.get('failed', 0)}"
    )


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
