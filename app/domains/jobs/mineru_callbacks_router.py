from __future__ import annotations

# app/domains/jobs/mineru_callbacks_router.py: 接收可信 MinerU callback，并把 workflow 推进委托给应用层。

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from app.api.dependencies import (
    get_runtime,
    get_trace_id,
)
from app.api.errors import bad_request_http_exception, not_found_http_exception
from app.api.mineru_callback_guards import (
    verify_mineru_callback_checksum_for_job,
    verify_mineru_callback_identity,
    verify_mineru_callback_request,
    verify_mineru_callback_result_url,
)
from app.domains.jobs.workflow import JobWorkflowViolation, build_mineru_callback_transition
from app.domains.jobs.presenters import build_job_detail_response
from app.core.runtime import AppRuntime
from app.domains.jobs.schemas import JobDetailResponse


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
        # 可信 callback 是否允许推进当前 job，由纯 workflow 规则统一判定。
        try:
            build_mineru_callback_transition(
                job,
                callback_state=str(normalized_payload.get("state") or ""),
                batch_id=normalized_payload.get("batch_id"),
                data_id=normalized_payload.get("data_id"),
                full_zip_url=normalized_payload.get("full_zip_url"),
            )
        except JobWorkflowViolation as exc:
            raise bad_request_http_exception(exc) from exc
        verify_mineru_callback_checksum_for_job(normalized_payload, job, runtime)
        job, stage_message = runtime.command_service.enqueue_callback(normalized_payload, trace_id, job=job)
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc

    background_tasks.add_task(runtime.stage_dispatcher.dispatch, stage_message.id)
    files = runtime.artifact_service.sort_files(runtime.query_service.list_files(job.id))
    events = runtime.query_service.list_events(job.id)
    return build_job_detail_response(runtime, request, job, files, events)
