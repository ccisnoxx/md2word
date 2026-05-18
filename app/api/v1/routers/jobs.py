from __future__ import annotations

import shutil
import zipfile
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse

from app.api.dependencies import get_runtime, get_trace_id, require_job_ops_access, require_jobs_access
from app.core.job_models import ConversionOptions, JobEvent, JobFile, JobRecord
from app.core.job_paths import build_job_paths
from app.core.runtime import AppRuntime
from app.schemas.api_v1 import (
    JobAcceptedResponse,
    JobCleanupLocalFilesResponse,
    JobDetailResponse,
    JobEventListResponse,
    JobEventResponse,
    JobFileListResponse,
    JobFileResponse,
    JobListResponse,
    JobOperationAcceptedResponse,
    JobSummaryResponse,
)


router = APIRouter(prefix="/jobs", tags=["jobs"])


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _build_conversion_options(
    template_id: str | None,
    translation_mode: str | None,
    document_language: str | None,
    use_mineru_header_footer: bool,
    runtime: AppRuntime,
) -> ConversionOptions:
    normalized_translation_mode = (_normalize_optional_text(translation_mode) or runtime.settings.default_translation_mode).lower()
    normalized_document_language = (_normalize_optional_text(document_language) or "auto").lower()
    normalized_template_id = _normalize_optional_text(template_id)

    if normalized_translation_mode not in {"direct", "en2zh"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="translation_mode 仅支持 direct 或 en2zh。",
        )
    if normalized_document_language not in {"auto", "zh", "en"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="document_language 仅支持 auto、zh、en。",
        )
    if normalized_template_id not in {None, runtime.settings.default_template_id}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"当前只支持默认模板 `{runtime.settings.default_template_id}`。",
        )

    return ConversionOptions(
        template_id=normalized_template_id,
        translation_mode=normalized_translation_mode,
        document_language=normalized_document_language,
        use_mineru_header_footer=use_mineru_header_footer,
    )


async def _save_upload_to_temp(upload: UploadFile, runtime: AppRuntime) -> Path:
    filename = _normalize_optional_text(upload.filename)
    if filename is None or not filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="上传文件必须是 .zip 格式的 MinerU 输出包。",
        )

    runtime.settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = runtime.settings.tmp_dir / f"upload_{uuid4().hex}.zip"
    total_size = 0

    with temp_path.open("wb") as output:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > runtime.settings.jobs_upload_max_bytes:
                output.close()
                temp_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"上传文件超过大小限制 {runtime.settings.jobs_upload_max_bytes} bytes。",
                )
            output.write(chunk)
    await upload.close()

    if not zipfile.is_zipfile(temp_path):
        temp_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="上传文件不是合法 zip 包。",
        )
    return temp_path


async def _save_pdf_upload_to_temp(upload: UploadFile, runtime: AppRuntime) -> Path:
    filename = _normalize_optional_text(upload.filename)
    if filename is None or not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="上传文件必须是 .pdf 格式。",
        )
    if upload.content_type and upload.content_type.lower() not in {"application/pdf", "application/x-pdf"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的 PDF content-type: {upload.content_type}",
        )

    runtime.settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = runtime.settings.tmp_dir / f"upload_{uuid4().hex}.pdf"
    total_size = 0
    file_header = b""

    with temp_path.open("wb") as output:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            if not file_header:
                file_header = chunk[:8]
            total_size += len(chunk)
            if total_size > runtime.settings.jobs_upload_max_bytes:
                output.close()
                temp_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"上传文件超过大小限制 {runtime.settings.jobs_upload_max_bytes} bytes。",
                )
            output.write(chunk)
    await upload.close()

    if not file_header.startswith(b"%PDF-"):
        temp_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="上传文件不是合法 PDF。",
        )
    return temp_path


def _file_response_from_record(runtime: AppRuntime, request: Request, job_id: str, file: JobFile) -> JobFileResponse:
    return JobFileResponse(
        file_type=file.file_type,
        path=file.path,
        storage_backend=file.storage_backend,
        object_key=file.object_key,
        public_url=file.public_url,
        download_url=runtime.artifact_service.build_download_url(
            job_id=job_id,
            file=file,
            url_for=request.url_for,
        ),
        created_at=file.created_at,
    )


def _event_response_from_record(event: JobEvent) -> JobEventResponse:
    return JobEventResponse(
        stage=event.stage,
        message=event.message,
        status=event.status,
        error_code=event.error_code,
        details=event.details,
        trace_id=event.trace_id,
        created_at=event.created_at,
    )


def _summary_response_from_record(runtime: AppRuntime, request: Request, job: JobRecord, files: list[JobFile]) -> JobSummaryResponse:
    result_file = next((item for item in files if item.file_type == "result_docx"), None)
    return JobSummaryResponse(
        id=job.id,
        source_filename=job.source_filename,
        status=job.status,
        progress=job.progress,
        translation_mode=job.translation_mode,
        result_ready=result_file is not None and job.status == "completed",
        result_download_url=(
            runtime.artifact_service.build_download_url(
                job_id=job.id,
                file=result_file,
                url_for=request.url_for,
            )
            if result_file
            else None
        ),
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _detail_response_from_record(
    runtime: AppRuntime,
    request: Request,
    job: JobRecord,
    files: list[JobFile],
    events: list[JobEvent],
) -> JobDetailResponse:
    files = runtime.artifact_service.sort_files(files)
    return JobDetailResponse(
        id=job.id,
        source_filename=job.source_filename,
        status=job.status,
        progress=job.progress,
        source_kind=job.source_kind,
        translation_mode=job.translation_mode,
        document_language=job.document_language,
        resolved_document_language=job.resolved_document_language,
        template_id=job.template_id,
        mineru_batch_id=job.mineru_batch_id,
        mineru_data_id=job.mineru_data_id,
        mineru_callback_seed=job.mineru_callback_seed,
        mineru_status=job.mineru_status,
        mineru_result_zip_url=job.mineru_result_zip_url,
        error_code=job.error_code,
        error_message=job.error_message,
        result_ready=job.result_ready,
        created_at=job.created_at,
        updated_at=job.updated_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        files=[_file_response_from_record(runtime, request, job.id, item) for item in files],
        events=[_event_response_from_record(item) for item in events],
    )


@router.post("", response_model=JobAcceptedResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_jobs_access)])
async def create_job(
    background_tasks: BackgroundTasks,
    request: Request,
    package: UploadFile = File(...),
    template_id: str | None = Form(default=None),
    translation_mode: str | None = Form(default=None),
    document_language: str | None = Form(default=None),
    use_mineru_header_footer: bool = Form(default=False),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> JobAcceptedResponse:
    options = _build_conversion_options(
        template_id,
        translation_mode,
        document_language,
        use_mineru_header_footer,
        runtime,
    )
    if options.translation_mode == "en2zh":
        dependency_checks = runtime.health_service.build_dependency_checks()
        if not dependency_checks["translation_available"]:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=dependency_checks.get("translation_unavailable_reason", "翻译能力当前不可用。"),
            )
    temp_upload_path = await _save_upload_to_temp(package, runtime)

    try:
        job, stage_message = runtime.command_service.create_job_from_saved_upload(
            temp_upload_path=temp_upload_path,
            source_filename=package.filename or temp_upload_path.name,
            options=options,
            trace_id=trace_id,
        )
    except Exception:
        temp_upload_path.unlink(missing_ok=True)
        raise

    background_tasks.add_task(runtime.stage_service.dispatch_message, stage_message.id)
    return JobAcceptedResponse(
        job_id=job.id,
        trace_id=trace_id,
        status=job.status,
        translation_mode=job.translation_mode,
    )


@router.post("/pdf", response_model=JobAcceptedResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_jobs_access)])
async def create_pdf_job(
    background_tasks: BackgroundTasks,
    pdf: UploadFile = File(...),
    template_id: str | None = Form(default=None),
    translation_mode: str | None = Form(default=None),
    document_language: str | None = Form(default=None),
    use_mineru_header_footer: bool = Form(default=False),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> JobAcceptedResponse:
    if not runtime.settings.mineru_api_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MINERU_API_TOKEN 未配置，PDF 在线解析不可用。",
        )
    options = _build_conversion_options(
        template_id,
        translation_mode,
        document_language,
        use_mineru_header_footer,
        runtime,
    )
    if options.translation_mode == "en2zh":
        dependency_checks = runtime.health_service.build_dependency_checks()
        if not dependency_checks["translation_available"]:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=dependency_checks.get("translation_unavailable_reason", "翻译能力当前不可用。"),
            )
    temp_upload_path = await _save_pdf_upload_to_temp(pdf, runtime)

    try:
        job, stage_message = runtime.command_service.create_job_from_pdf_upload(
            temp_upload_path=temp_upload_path,
            source_filename=pdf.filename or temp_upload_path.name,
            options=options,
            trace_id=trace_id,
        )
    except Exception:
        temp_upload_path.unlink(missing_ok=True)
        raise

    background_tasks.add_task(runtime.stage_service.dispatch_message, stage_message.id)
    return JobAcceptedResponse(
        job_id=job.id,
        trace_id=trace_id,
        status=job.status,
        translation_mode=job.translation_mode,
    )


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
        _summary_response_from_record(
            runtime,
            request,
            job,
            runtime.artifact_service.sort_files(runtime.query_service.list_files(job.id)),
        )
        for job in jobs
    ]
    return JobListResponse(items=items, page=page, page_size=page_size, total=total, summary=summary)


@router.get("/{job_id}", response_model=JobDetailResponse, dependencies=[Depends(require_jobs_access)])
def get_job_detail(
    job_id: str,
    request: Request,
    runtime: AppRuntime = Depends(get_runtime),
) -> JobDetailResponse:
    job, files, events = runtime.query_service.get_job_detail(job_id)
    return _detail_response_from_record(runtime, request, job, files, events)


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
        files=[_file_response_from_record(runtime, request, job_id, item) for item in files],
    )


@router.get("/{job_id}/events", response_model=JobEventListResponse, dependencies=[Depends(require_jobs_access)])
def get_job_events(
    job_id: str,
    runtime: AppRuntime = Depends(get_runtime),
) -> JobEventListResponse:
    runtime.query_service.get_job(job_id)
    events = runtime.query_service.list_events(job_id)
    return JobEventListResponse(job_id=job_id, items=[_event_response_from_record(item) for item in events])


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
    return _file_response_from_record(runtime, request, job_id, result_file)


@router.get(
    "/{job_id}/download/{artifact_alias}",
    name="download_artifact",
    dependencies=[Depends(require_jobs_access)],
)
def download_artifact(
    job_id: str,
    artifact_alias: str,
    runtime: AppRuntime = Depends(get_runtime),
) -> FileResponse:
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
        artifact_path = runtime.artifact_service.resolve_download_path(job_paths, file)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not artifact_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="本地产物文件不存在。")

    return FileResponse(
        artifact_path,
        media_type=runtime.artifact_service.media_type_for_file(file),
        filename=runtime.artifact_service.build_download_filename(job, file),
    )


@router.post(
    "/{job_id}/retry",
    response_model=JobOperationAcceptedResponse,
    dependencies=[Depends(require_job_ops_access)],
)
def retry_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    request: Request,
    reason: str = Form(...),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> JobOperationAcceptedResponse:
    result = runtime.lifecycle_service.retry_job(job_id, reason=reason, trace_id=trace_id)
    pending_messages = [
        message
        for message in runtime.repository.list_pending_stage_messages()
        if message.job_id == job_id
    ]
    for message in pending_messages:
        background_tasks.add_task(runtime.stage_service.dispatch_message, message.id)
    return JobOperationAcceptedResponse(
        job_id=result.job_id,
        operation=result.operation,
        accepted=result.accepted,
        status=result.status,
        message=result.message,
    )


@router.post(
    "/{job_id}/cancel",
    response_model=JobDetailResponse,
    dependencies=[Depends(require_job_ops_access)],
)
def cancel_job(
    job_id: str,
    request: Request,
    reason: str = Form(...),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> JobDetailResponse:
    job = runtime.lifecycle_service.cancel_job(job_id, reason=reason, trace_id=trace_id)
    files = runtime.artifact_service.sort_files(runtime.query_service.list_files(job_id))
    events = runtime.query_service.list_events(job_id)
    return _detail_response_from_record(runtime, request, job, files, events)


@router.post(
    "/{job_id}/cleanup-local-files",
    response_model=JobCleanupLocalFilesResponse,
    dependencies=[Depends(require_job_ops_access)],
)
def cleanup_local_files(
    job_id: str,
    reason: str = Form(...),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> JobCleanupLocalFilesResponse:
    result = runtime.lifecycle_service.cleanup_local_files(job_id, reason=reason, trace_id=trace_id)
    return JobCleanupLocalFilesResponse(
        job_id=result.job_id,
        deleted_paths=result.deleted_paths,
        skipped_paths=result.skipped_paths,
        status=result.status,
        message=result.message,
    )
