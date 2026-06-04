from __future__ import annotations

# app/domains/document_jobs/router.py: 提供 document_jobs 创建、查询和事件查询接口。

import hashlib
import hmac
from datetime import datetime
from datetime import timedelta
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import FileResponse, RedirectResponse

from app.api.dependencies import get_runtime, get_trace_id, require_current_user
from app.domains.audit.models import ActorContext
from app.domains.document_jobs.config_summary import build_document_job_config_summary
from app.domains.document_jobs.models import DocumentJobEventRecord, DocumentJobRecord
from app.core.errors import ApiError
from app.domains.files.models import DocumentFileRecord
from app.domains.files.schemas import DocumentFileResponse
from app.domains.jobs.models import utc_now
from app.core.runtime import AppRuntime
from app.domains.document_jobs.schemas import (
    DocumentJobArchiveResponse,
    DocumentJobCancelResponse,
    DocumentJobCreateRequest,
    DocumentJobCreateResponse,
    DocumentJobConfigSummaryResponse,
    DocumentJobDownloadUrlResponse,
    DocumentJobEventListResponse,
    DocumentJobEventResponse,
    DocumentJobFileListResponse,
    DocumentJobListResponse,
    DocumentJobResponse,
    DocumentJobRetryRequest,
    DocumentJobRetryResponse,
    DocumentJobTranslationQaResponse,
    DocumentJobTranslationQaStateResponse,
    DocumentJobTranslationQaUpdateRequest,
    DocumentJobTranslationQaUpdateResponse,
)
from app.services.auth.models import AuthenticatedUser


router = APIRouter(prefix="/document-jobs", tags=["document-jobs"])


@router.post("", response_model=DocumentJobCreateResponse, status_code=status.HTTP_201_CREATED)
def create_document_job(
    payload: DocumentJobCreateRequest,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
    trace_id: str = Depends(get_trace_id),
) -> DocumentJobCreateResponse:
    job = runtime.document_job_service.create_job(
        user=user,
        source_file_id=payload.source_file_id,
        mode=payload.mode,
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
        job=_build_document_job_response(job),
    )


@router.get("", response_model=DocumentJobListResponse)
def list_document_jobs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None),
    sort: str = Query(default="created_at_desc"),
    include_archived: bool = Query(default=False),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> DocumentJobListResponse:
    jobs, total, summary = runtime.document_job_service.list_jobs(
        user=user,
        page=page,
        page_size=page_size,
        status_filter=status_filter.strip() if status_filter else None,
        q=q,
        sort=sort,
        include_archived=include_archived,
        created_from=created_from,
        created_to=created_to,
    )
    return DocumentJobListResponse(
        items=[_build_document_job_response(job) for job in jobs],
        page=page,
        page_size=page_size,
        total=total,
        summary=summary,
    )


@router.get("/config-summary", response_model=DocumentJobConfigSummaryResponse)
def get_document_job_config_summary(
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> DocumentJobConfigSummaryResponse:
    return build_document_job_config_summary(runtime, user=user)


@router.get("/{job_id}", response_model=DocumentJobResponse)
def get_document_job(
    job_id: str,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> DocumentJobResponse:
    return _build_document_job_response(runtime.document_job_service.get_job(job_id, user=user))


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
        files=[_build_document_file_response(file) for file in files],
    )


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
        job=_build_document_job_response(job),
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
        job=_build_document_job_response(job),
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
        job=_build_document_job_response(job),
    )


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
        job=_build_document_job_response(job),
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
        file=_build_document_file_response(file),
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


def _build_document_job_response(job: DocumentJobRecord) -> DocumentJobResponse:
    return DocumentJobResponse(**job.model_dump(mode="python"))


def _build_document_job_event_response(event: DocumentJobEventRecord) -> DocumentJobEventResponse:
    return DocumentJobEventResponse(**event.model_dump(mode="python"))


def _build_document_file_response(file: DocumentFileRecord) -> DocumentFileResponse:
    return DocumentFileResponse(**file.model_dump(mode="python"))


def _build_translation_qa_state_response(job: DocumentJobRecord) -> DocumentJobTranslationQaStateResponse:
    return DocumentJobTranslationQaStateResponse(
        status=job.translation_qa_status,
        issue_type=job.translation_qa_issue_type,
        note=job.translation_qa_note,
        reviewed_by=job.translation_qa_reviewed_by,
        reviewed_at=job.translation_qa_reviewed_at,
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
