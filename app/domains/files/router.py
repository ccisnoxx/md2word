from __future__ import annotations

# app/domains/files/router.py: 提供 document_files 元数据、上传授权和本地代理上传接口。

from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Depends, Request, status

from app.api.dependencies import get_runtime, get_trace_id, require_current_user
from app.domains.audit.models import ActorContext
from app.services.auth.models import AuthenticatedUser
from app.core.errors import ApiError
from app.domains.files.models import DocumentFileRecord
from app.domains.files.schemas import (
    DocumentFileResponse,
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
