from __future__ import annotations

# app/domains/jobs/query_router.py: 提供 jobs 查询、文件列表、事件列表和 artifact 下载接口。

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, RedirectResponse, Response, StreamingResponse

from app.api.dependencies import get_runtime, get_trace_id, require_jobs_access, require_jobs_actor
from app.api.errors import artifact_download_http_exception
from app.domains.jobs.presenters import (
    build_job_detail_response,
    build_job_event_response,
    build_job_file_response,
    build_job_summary_response,
)
from app.domains.jobs.paths import build_job_paths
from app.domains.audit.models import ActorContext
from app.core.runtime import AppRuntime
from app.domains.jobs.schemas import JobDetailResponse, JobEventListResponse, JobFileListResponse, JobFileResponse, JobListResponse


router = APIRouter()


def _attachment_content_disposition(filename: str) -> str:
    """为流式下载响应补齐 attachment 文件名语义。"""

    quoted_filename = quote(filename)
    if quoted_filename != filename:
        return f"attachment; filename*=utf-8''{quoted_filename}"
    return f'attachment; filename="{filename}"'


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


@router.get("", response_model=JobListResponse, dependencies=[Depends(require_jobs_access)])
def list_jobs(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None),
    sort: str = Query(default="created_at_desc"),
    runtime: AppRuntime = Depends(get_runtime),
) -> JobListResponse:
    jobs, total, summary = runtime.query_service.list_jobs(
        page=page,
        page_size=page_size,
        status_filter=_normalize_optional_text(status_filter),
        query_text=_normalize_optional_text(q),
        sort=sort,
    )
    items = [
        build_job_summary_response(
            runtime,
            request,
            job,
            runtime.artifact_service.sort_files(runtime.query_service.list_files(job.id)),
        )
        for job in jobs
    ]
    return JobListResponse(items=items, page=page, page_size=page_size, total=total, summary=summary)


@router.get("/{job_id}", response_model=JobDetailResponse)
def get_job_detail(
    job_id: str,
    request: Request,
    actor: ActorContext = Depends(require_jobs_actor),
    runtime: AppRuntime = Depends(get_runtime),
) -> JobDetailResponse:
    job, files, events = runtime.query_service.get_job_detail(job_id)
    return build_job_detail_response(
        runtime,
        request,
        job,
        files,
        events,
        include_sensitive_fields=actor.actor_role == "admin",
    )


@router.get("/{job_id}/files", response_model=JobFileListResponse, dependencies=[Depends(require_jobs_access)])
def get_job_files(
    job_id: str,
    request: Request,
    runtime: AppRuntime = Depends(get_runtime),
) -> JobFileListResponse:
    runtime.query_service.get_job(job_id)
    files = runtime.artifact_service.sort_files(runtime.query_service.list_files(job_id))
    return JobFileListResponse(
        job_id=job_id,
        files=[build_job_file_response(runtime, request, job_id, item) for item in files],
    )


@router.get("/{job_id}/events", response_model=JobEventListResponse, dependencies=[Depends(require_jobs_access)])
def get_job_events(
    job_id: str,
    runtime: AppRuntime = Depends(get_runtime),
) -> JobEventListResponse:
    runtime.query_service.get_job(job_id)
    events = runtime.query_service.list_events(job_id)
    return JobEventListResponse(job_id=job_id, items=[build_job_event_response(item) for item in events])


@router.get("/{job_id}/result", response_model=JobFileResponse, dependencies=[Depends(require_jobs_access)])
def get_job_result(
    job_id: str,
    request: Request,
    runtime: AppRuntime = Depends(get_runtime),
) -> JobFileResponse:
    job = runtime.query_service.get_job(job_id)
    result_file = runtime.query_service.get_file_by_type(job_id, "result_docx")
    if result_file is None or job.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="任务尚未完成，result.docx 还不可用。",
        )
    return build_job_file_response(runtime, request, job_id, result_file)


@router.get(
    "/{job_id}/download/{artifact_alias}",
    name="download_artifact",
)
def download_artifact(
    job_id: str,
    artifact_alias: str,
    actor: ActorContext = Depends(require_jobs_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> Response:
    """按 artifact storage 下载结果合同生成 HTTP 响应，保持下载 URL 稳定。"""

    try:
        file_type = runtime.artifact_service.spec_for_alias(artifact_alias).file_type
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="不支持的产物类型。")

    job = runtime.query_service.get_job(job_id)
    file = runtime.query_service.get_file_by_type(job_id, file_type)
    if file is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="产物不存在。")

    job_paths = build_job_paths(runtime.settings.data_path, job_id)
    try:
        download = runtime.artifact_storage.resolve_download(job_paths, file)
    except (FileNotFoundError, ValueError) as exc:
        raise artifact_download_http_exception(exc) from exc

    media_type = runtime.artifact_service.media_type_for_file(file)
    filename = runtime.artifact_service.build_download_filename(job, file)
    if download.kind == "local_path":
        if download.path is None or not download.path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="本地产物文件不存在。")
        runtime.audit_service.record(
            actor=actor,
            action="artifact.download",
            target_type="artifact",
            target_id=f"{job_id}:{artifact_alias}",
            trace_id=trace_id,
        )
        return FileResponse(download.path, media_type=media_type, filename=filename)

    if download.kind == "stream":
        if download.content is None:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="产物流不可用。")
        runtime.audit_service.record(
            actor=actor,
            action="artifact.download",
            target_type="artifact",
            target_id=f"{job_id}:{artifact_alias}",
            trace_id=trace_id,
        )
        return StreamingResponse(
            download.content,
            media_type=media_type,
            headers={"Content-Disposition": _attachment_content_disposition(filename)},
        )

    if download.redirect_url is None:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="产物重定向地址不可用。")
    runtime.audit_service.record(
        actor=actor,
        action="artifact.download",
        target_type="artifact",
        target_id=f"{job_id}:{artifact_alias}",
        trace_id=trace_id,
    )
    return RedirectResponse(download.redirect_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
