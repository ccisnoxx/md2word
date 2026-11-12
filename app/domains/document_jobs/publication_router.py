"""document_jobs 发布入口：发布、发布记录与最终件下载。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse, Response

from app.api.dependencies import get_runtime, get_trace_id, require_admin_user, require_current_user
from app.core.runtime import AppRuntime
from app.domains.document_jobs.http_responses import externalize_url
from app.domains.document_jobs.quality_review_http import QualityReviewApiRoute, QUALITY_REVIEW_RESPONSES
from app.domains.document_jobs.schemas.publication import (
    DocumentPublishRequest,
    DocumentPublishResponse,
    DocumentPublicationsResponse,
    DocumentPublicationDownloadUrlResponse,
)
from app.services.auth.models import AuthenticatedUser


publication_router = APIRouter(route_class=QualityReviewApiRoute)
_PUBLICATION_WRITE_RESPONSES = {
    **QUALITY_REVIEW_RESPONSES,
    200: {**QUALITY_REVIEW_RESPONSES[200], "model": DocumentPublishResponse, "description": "同一幂等键与参数重放，返回已提交记录。"},
    201: {**QUALITY_REVIEW_RESPONSES[200], "model": DocumentPublishResponse, "description": "首次发布成功，事实、任务投影和成功审计已原子提交。"},
}


@publication_router.post("/{job_id}/publish", response_model=DocumentPublishResponse,
    status_code=201, responses=_PUBLICATION_WRITE_RESPONSES)
def publish_document(job_id: str, payload: DocumentPublishRequest, response: Response,
                     runtime: AppRuntime = Depends(get_runtime), user: AuthenticatedUser = Depends(require_admin_user),
                     trace_id: str = Depends(get_trace_id)):
    result, created = runtime.document_job_use_cases.publication.publish_document(job_id, user=user,
        request_id=payload.request_id, note=payload.note, expected_source=payload.expected_source, trace_id=trace_id)
    response.status_code = 201 if created else 200
    return result


@publication_router.get("/{job_id}/publications", response_model=DocumentPublicationsResponse,
    responses=QUALITY_REVIEW_RESPONSES)
def list_document_publications(job_id: str, runtime: AppRuntime = Depends(get_runtime),
                               user: AuthenticatedUser = Depends(require_current_user)):
    return runtime.document_job_use_cases.publication.list_document_publications(job_id, user=user)


_PUBLICATION_DOWNLOAD_RESPONSES = {
    code: {**details, "description": ("最终件下载认证失败；未知错误仅返回安全 trace。" if code == 500
        else "已授权的发布最终件或短期下载入口。" if code == 200 else details["description"])}
    for code, details in QUALITY_REVIEW_RESPONSES.items() if code != 400
}


@publication_router.get("/{job_id}/publications/{publication_id}/download-url",
    response_model=DocumentPublicationDownloadUrlResponse, responses=_PUBLICATION_DOWNLOAD_RESPONSES)
def create_document_publication_download_url(job_id: str, publication_id: str, request: Request,
    runtime: AppRuntime = Depends(get_runtime), user: AuthenticatedUser = Depends(require_current_user),
    trace_id: str = Depends(get_trace_id)):
    """签发绑定不可变记录的短期最终件入口，审计失败不交付 URL。"""
    grant = runtime.document_job_use_cases.publication.authorize_publication_download(
        job_id, publication_id, user=user, trace_id=trace_id)
    if grant.presigned_url is not None:
        download_url = grant.presigned_url
    else:
        base_url = externalize_url(str(request.url_for("download_document_publication_result",
            job_id=grant.job.id, publication_id=grant.record.id)), request=request)
        download_url = f"{base_url}?token={grant.token}"
    return DocumentPublicationDownloadUrlResponse(publication_id=grant.record.id, job_id=grant.job.id,
        result_file_id=grant.file.id, result_sha256=grant.record.result_sha256, size_bytes=grant.file.size_bytes,
        download_url=download_url, expires_at=grant.expires_at)


@publication_router.get("/{job_id}/publications/{publication_id}/download",
    name="download_document_publication_result", response_class=FileResponse, responses=_PUBLICATION_DOWNLOAD_RESPONSES)
def download_document_publication_result(job_id: str, publication_id: str, token: str = Query(...),
    runtime: AppRuntime = Depends(get_runtime)):
    """能力取件重验记录、descriptor、真实字节和安全路径，不伪造 JWT 审计。"""
    file, path = runtime.document_job_use_cases.publication.resolve_publication_download(
        job_id, publication_id, token=token)
    return FileResponse(path, media_type=file.mime_type, filename=file.original_filename,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
