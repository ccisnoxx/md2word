from __future__ import annotations

# app/api/v1/routers/jobs_ops.py: 暴露 job 操作接口并通过运行时端口触发后续调度。

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Request

from app.api.dependencies import get_runtime, get_trace_id, require_job_ops_access
from app.api.v1.routers.jobs_presenters import build_job_detail_response
from app.core.runtime import AppRuntime
from app.schemas.api_v1 import JobCleanupLocalFilesResponse, JobDetailResponse, JobOperationAcceptedResponse


router = APIRouter()


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
        background_tasks.add_task(runtime.stage_dispatcher.dispatch, message.id)
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
    return build_job_detail_response(runtime, request, job, files, events)


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
