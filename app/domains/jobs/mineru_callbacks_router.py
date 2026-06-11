from __future__ import annotations

# app/domains/jobs/mineru_callbacks_router.py: 接收可信 MinerU callback，并把 workflow 推进委托给应用层。

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

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
from app.core.runtime import AppRuntime
from app.domains.document_jobs.schemas import DocumentJobResponse


router = APIRouter(prefix="/mineru-callbacks", tags=["mineru-callbacks"])
logger = logging.getLogger("business")


@router.post("/result", response_model=DocumentJobResponse, status_code=status.HTTP_200_OK)
async def receive_mineru_callback(
    request: Request,
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> DocumentJobResponse:
    payload = await request.json()
    try:
        verify_mineru_callback_identity(request, runtime)
        normalized_payload = verify_mineru_callback_request(payload)
        verify_mineru_callback_result_url(normalized_payload, runtime)
        document_job = runtime.document_job_execution_service.find_job_for_mineru_callback(normalized_payload)
        if document_job is None:
            raise FileNotFoundError("document_job not found for MinerU callback")
        verify_mineru_callback_checksum_for_job(normalized_payload, document_job, runtime)
        document_job, _callback_message, _created, should_enqueue = (
            runtime.document_job_execution_service.enqueue_mineru_callback_for_job(
                document_job,
                normalized_payload,
                trace_id=trace_id,
            )
        )
        if should_enqueue and runtime.document_job_task_queue is not None:
            try:
                runtime.document_job_task_queue.enqueue(document_job.id, trace_id=trace_id, run_inline=False)
            except RuntimeError as exc:
                # callback 已持久化，返回 200 避免上游重复风暴；Worker/replay 后续仍可处理。
                logger.warning(
                    "[trace_id=%s job_id=%s status=document_job_callback_wakeup_failed] %s",
                    trace_id,
                    document_job.id,
                    exc,
                )
        document_job = runtime.document_job_repository.get_document_job(document_job.id) or document_job
        return DocumentJobResponse(**document_job.model_dump(mode="python"))
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc
