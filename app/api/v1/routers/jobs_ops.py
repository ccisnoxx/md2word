from __future__ import annotations

# app/api/v1/routers/jobs_ops.py: 暴露 job 操作接口并通过运行时端口触发后续调度。

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request, status

from app.api.dependencies import get_runtime, get_trace_id, require_job_ops_actor
from app.api.errors import bad_request_http_exception, not_found_http_exception
from app.api.v1.routers.jobs_presenters import build_job_detail_response
from app.clients.mineru_client import MinerUError
from app.core.audit_models import ActorContext
from app.core.runtime import AppRuntime
from app.schemas.jobs import JobCleanupLocalFilesResponse, JobDetailResponse, JobOperationAcceptedResponse


router = APIRouter()


@router.post(
    "/{job_id}/retry",
    response_model=JobOperationAcceptedResponse,
)
def retry_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    request: Request,
    reason: str = Form(...),
    actor: ActorContext = Depends(require_job_ops_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> JobOperationAcceptedResponse:
    result = runtime.lifecycle_service.retry_job(job_id, reason=reason, trace_id=trace_id, actor=actor)
    pending_messages = [
        message
        for message in runtime.stage_message_store.list_replayable_stage_messages()
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
)
def cancel_job(
    job_id: str,
    request: Request,
    reason: str = Form(...),
    actor: ActorContext = Depends(require_job_ops_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> JobDetailResponse:
    job = runtime.lifecycle_service.cancel_job(job_id, reason=reason, trace_id=trace_id, actor=actor)
    files = runtime.artifact_service.sort_files(runtime.query_service.list_files(job_id))
    events = runtime.query_service.list_events(job_id)
    return build_job_detail_response(runtime, request, job, files, events)


@router.post(
    "/{job_id}/recover-mineru-result",
    response_model=JobOperationAcceptedResponse,
)
def recover_mineru_result(
    job_id: str,
    background_tasks: BackgroundTasks,
    actor: ActorContext = Depends(require_job_ops_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> JobOperationAcceptedResponse:
    del actor
    if not runtime.settings.mineru_api_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MINERU_API_TOKEN 未配置，无法主动查询 MinerU 结果。",
        )
    job = runtime.query_service.get_job(job_id)
    try:
        stage_message = runtime.stage_service.enqueue_mineru_result_recovery(job, trace_id)
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc
    except MinerUError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    background_tasks.add_task(runtime.stage_dispatcher.dispatch, stage_message.id)
    return JobOperationAcceptedResponse(
        job_id=job.id,
        operation="recover-mineru-result",
        accepted=True,
        status="queued",
        message="已主动查询 MinerU 结果并进入后台处理。",
    )


@router.post(
    "/{job_id}/cleanup-local-files",
    response_model=JobCleanupLocalFilesResponse,
)
def cleanup_local_files(
    job_id: str,
    reason: str = Form(...),
    actor: ActorContext = Depends(require_job_ops_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> JobCleanupLocalFilesResponse:
    result = runtime.lifecycle_service.cleanup_local_files(job_id, reason=reason, trace_id=trace_id, actor=actor)
    return JobCleanupLocalFilesResponse(
        job_id=result.job_id,
        deleted_paths=result.deleted_paths,
        skipped_paths=result.skipped_paths,
        status=result.status,
        message=result.message,
    )
