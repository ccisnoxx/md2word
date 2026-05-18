from __future__ import annotations

from fastapi import Request

from app.core.job_models import JobEvent, JobFile, JobRecord
from app.core.runtime import AppRuntime
from app.schemas.api_v1 import JobDetailResponse, JobEventResponse, JobFileResponse, JobSummaryResponse


def build_job_file_response(runtime: AppRuntime, request: Request, job_id: str, file: JobFile) -> JobFileResponse:
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


def build_job_event_response(event: JobEvent) -> JobEventResponse:
    return JobEventResponse(
        stage=event.stage,
        message=event.message,
        status=event.status,
        error_code=event.error_code,
        details=event.details,
        trace_id=event.trace_id,
        created_at=event.created_at,
    )


def build_job_summary_response(
    runtime: AppRuntime,
    request: Request,
    job: JobRecord,
    files: list[JobFile],
) -> JobSummaryResponse:
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


def build_job_detail_response(
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
        files=[build_job_file_response(runtime, request, job.id, item) for item in files],
        events=[build_job_event_response(item) for item in events],
    )
