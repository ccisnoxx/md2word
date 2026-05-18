from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from app.api.dependencies import (
    get_runtime,
    get_trace_id,
)
from app.api.mineru_callback_guards import (
    verify_mineru_callback_checksum_for_job,
    verify_mineru_callback_identity,
    verify_mineru_callback_job_state,
    verify_mineru_callback_request,
    verify_mineru_callback_result_url,
)
from app.api.v1.routers.jobs_presenters import build_job_detail_response
from app.core.runtime import AppRuntime
from app.schemas.api_v1 import JobDetailResponse


router = APIRouter(prefix="/mineru-callbacks", tags=["mineru-callbacks"])


@router.post("/result", response_model=JobDetailResponse, status_code=status.HTTP_200_OK)
async def receive_mineru_callback(
    request: Request,
    background_tasks: BackgroundTasks,
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> JobDetailResponse:
    payload = await request.json()
    try:
        verify_mineru_callback_identity(request, runtime)
        normalized_payload = verify_mineru_callback_request(payload)
        verify_mineru_callback_result_url(normalized_payload, runtime)
        job = runtime.command_service.find_job_for_callback(normalized_payload)
        verify_mineru_callback_job_state(job)
        verify_mineru_callback_checksum_for_job(normalized_payload, job, runtime)
        job, stage_message = runtime.command_service.enqueue_callback(normalized_payload, trace_id, job=job)
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    background_tasks.add_task(runtime.stage_service.dispatch_message, stage_message.id)
    files = runtime.artifact_service.sort_files(runtime.query_service.list_files(job.id))
    events = runtime.query_service.list_events(job.id)
    return build_job_detail_response(runtime, request, job, files, events)
