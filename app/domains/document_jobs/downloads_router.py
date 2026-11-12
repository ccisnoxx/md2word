"""document_jobs 任务文件下载入口：签发短期下载地址与令牌取件。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import FileResponse, RedirectResponse

from app.api.dependencies import get_runtime, get_trace_id, require_current_user
from app.core.runtime import AppRuntime
from app.domains.document_jobs.http_responses import (
    actor_from_user,
    build_document_file_summary_response,
    externalize_url,
)
from app.domains.document_jobs.schemas.jobs import DocumentJobDownloadUrlResponse
from app.services.auth.models import AuthenticatedUser


downloads_router = APIRouter()


@downloads_router.get("/{job_id}/download-url", response_model=DocumentJobDownloadUrlResponse)
def create_document_job_download_url(
    job_id: str,
    request: Request,
    file_id: str | None = Query(default=None),
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
    trace_id: str = Depends(get_trace_id),
) -> DocumentJobDownloadUrlResponse:
    grant = runtime.document_job_use_cases.downloads.authorize_download(
        job_id, user=user, file_id=file_id, trace_id=trace_id,
    )
    job, file, policy = grant.job, grant.file, grant.policy
    if grant.presigned_url is not None:
        download_url = grant.presigned_url
    else:
        base_url = externalize_url(str(request.url_for("download_document_job_result", job_id=job.id)), request=request)
        download_url = f"{base_url}?token={grant.token}"
    runtime.audit_service.record(
        actor=actor_from_user(user),
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
        expires_at=grant.expires_at,
        file=build_document_file_summary_response(file),
        classification=policy.classification,
        warning_code=policy.warning_code,
        warning_message=policy.warning_message,
    )


@downloads_router.get("/{job_id}/download", name="download_document_job_result")
def download_document_job_result(
    job_id: str,
    token: str = Query(...),
    runtime: AppRuntime = Depends(get_runtime),
):
    download = runtime.document_job_use_cases.downloads.resolve_token_download(job_id, token=token)
    if download.redirect_url is not None:
        return RedirectResponse(download.redirect_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    return FileResponse(
        download.local_path,
        media_type=download.file.mime_type,
        filename=download.file.original_filename,
    )
