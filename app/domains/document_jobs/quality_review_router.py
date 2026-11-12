"""document_jobs 质量与复核入口（质量、预览元数据、复核、复核块）及同任务新代请求。

路由使用 QualityReviewApiRoute 的专用错误形状；旧 QA、下载和全局异常处理保持原入口。
"""

from __future__ import annotations

import json
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response

from app.api.dependencies import get_runtime, get_trace_id, require_admin_user, require_current_user
from app.api.errors import api_error_response
from app.core.errors import http_status_for
from app.core.runtime import AppRuntime
from app.domains.document_jobs.http_responses import actor_from_user
from app.domains.document_jobs.quality_review_http import QualityReviewApiRoute, QUALITY_REVIEW_RESPONSES
from app.domains.document_jobs.review import ReviewExpectedSource
from app.domains.document_jobs.schemas.quality_review import (
    DocumentJobNewGenerationRequest,
    DocumentJobNewGenerationResponse,
    DocumentJobNewGenerationErrorResponse,
)
from app.domains.document_jobs.schemas.quality_review import DocumentReviewUpdateRequest
from app.domains.document_jobs.use_cases.common import NewGenerationRequestUnavailable
from app.domains.document_jobs.views.quality_review import (
    DocumentQualityResponse,
    DocumentQualityTablesResponse,
    DocumentQualityPagesResponse,
    DocumentPreviewResponse,
    DocumentCurrentReviewResponse,
    DocumentReviewHistoryResponse,
    DocumentReviewUpdateResponse,
    DocumentReviewBlocksResponse,
    DocumentReviewBlockDetailResponse,
)
from app.services.auth.models import AuthenticatedUser


quality_review_router = APIRouter(route_class=QualityReviewApiRoute)


# 专用子路由拥有九项操作；旧 QA、下载和全局异常处理保持原入口。
@quality_review_router.get("/{job_id}/quality", response_model=DocumentQualityResponse,
                           responses=QUALITY_REVIEW_RESPONSES)
def get_document_job_quality(
    job_id: str,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> DocumentQualityResponse:
    """读取后端权威质量摘要、有效复核与可用动作。"""
    return runtime.document_job_use_cases.quality_review.get_document_quality(job_id, user=user)


@quality_review_router.get("/{job_id}/quality/tables", response_model=DocumentQualityTablesResponse,
                           responses=QUALITY_REVIEW_RESPONSES)
def get_document_job_quality_tables(
    job_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> DocumentQualityTablesResponse:
    """分页读取严格认证后、经过白名单投影的表格证据。"""
    return runtime.document_job_use_cases.quality_review.get_document_quality_tables(job_id, user=user, limit=limit, cursor=cursor)


@quality_review_router.get("/{job_id}/quality/pages", response_model=DocumentQualityPagesResponse,
                           responses=QUALITY_REVIEW_RESPONSES)
def get_document_job_quality_pages(
    job_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> DocumentQualityPagesResponse:
    """读取已有页级报告，保留未检查、不完整与低置信来源。"""
    return runtime.document_job_use_cases.quality_review.get_document_quality_pages(job_id, user=user, limit=limit, cursor=cursor)


@quality_review_router.get("/{job_id}/preview", response_model=DocumentPreviewResponse,
                           responses=QUALITY_REVIEW_RESPONSES)
def get_document_job_preview_metadata(
    job_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> DocumentPreviewResponse:
    """只返回当前预览的已验证元数据和文件 ID，不生产或签发下载链接。"""
    return runtime.document_job_use_cases.quality_review.get_document_preview(job_id, user=user, limit=limit, cursor=cursor)


@quality_review_router.get("/{job_id}/review", response_model=DocumentCurrentReviewResponse,
                           responses=QUALITY_REVIEW_RESPONSES)
def get_document_job_review(
    job_id: str,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> DocumentCurrentReviewResponse:
    """读取同一次主件观察对应的有效复核与后端动作。"""
    return runtime.document_job_use_cases.quality_review.get_document_review(job_id, user=user)


@quality_review_router.get("/{job_id}/review/history", response_model=DocumentReviewHistoryResponse,
                           responses=QUALITY_REVIEW_RESPONSES)
def list_document_job_review_history(
    job_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> DocumentReviewHistoryResponse:
    """按固定序号高水位窗口读取追加历史。"""
    return runtime.document_job_use_cases.quality_review.get_document_review_history(job_id, user=user, limit=limit, cursor=cursor)


@quality_review_router.patch("/{job_id}/review", response_model=DocumentReviewUpdateResponse,
                             responses=QUALITY_REVIEW_RESPONSES)
def update_document_job_review(
    job_id: str,
    payload: DocumentReviewUpdateRequest,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
    trace_id: str = Depends(get_trace_id),
) -> DocumentReviewUpdateResponse:
    """按客户端观察来源提交一次复核；异常响应不代表记录必然未提交。"""
    return runtime.document_job_use_cases.quality_review.submit_document_review_with_source(
        job_id,
        user=user,
        review_status=payload.status,
        issue_type=payload.issue_type,
        note=payload.note,
        expected_source=ReviewExpectedSource.model_validate(payload.expected_source.model_dump()),
        trace_id=trace_id,
    )


@quality_review_router.get("/{job_id}/review/blocks", response_model=DocumentReviewBlocksResponse,
                           responses=QUALITY_REVIEW_RESPONSES)
def list_document_job_review_blocks(
    job_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    source_page_index: int | None = Query(default=None, ge=0),
    block_type: Literal["heading", "paragraph", "table", "image", "list", "formula"] | None = None,
    problem: Literal["all", "flagged"] = "all",
    severity: Literal["all", "blocker", "warning", "info"] = "all",
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
    trace_id: str = Depends(get_trace_id),
) -> DocumentReviewBlocksResponse:
    """有限读取当前 IR 的内容导航；筛选不把页级候选当块级缺陷。"""
    result = runtime.document_job_use_cases.quality_review.list_document_review_blocks(job_id, user=user, limit=limit,
        cursor=cursor, source_page_index=source_page_index, block_type=block_type, problem=problem, severity=severity)
    runtime.audit_service.record(actor=actor_from_user(user), action="document_job.review_blocks",
        target_type="document_job", target_id=job_id, trace_id=trace_id,
        details={"generation": result.source.generation, "item_count": len(result.items), "outcome": result.availability})
    return result


@quality_review_router.get("/{job_id}/review/blocks/{block_id}", response_model=DocumentReviewBlockDetailResponse,
                           responses=QUALITY_REVIEW_RESPONSES)
def get_document_job_review_block(
    job_id: str,
    block_id: str,
    snapshot_id: str = Query(pattern=r"^[0-9a-f]{64}$"),
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = Query(default=None),
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
    trace_id: str = Depends(get_trace_id),
) -> DocumentReviewBlockDetailResponse:
    """读取已选来源中的内容分片、术语及批次摘要，不触发任何生产者。"""
    result = runtime.document_job_use_cases.quality_review.get_document_review_block(job_id, block_id, user=user,
        snapshot_id=snapshot_id, limit=limit, cursor=cursor)
    runtime.audit_service.record(actor=actor_from_user(user), action="document_job.review_block",
        target_type="document_job", target_id=job_id, trace_id=trace_id,
        details={"generation": result.source.generation, "item_count": len(result.items), "outcome": "succeeded"})
    return result



_NEW_GENERATION_RESPONSES = {
    **{code: value for code, value in QUALITY_REVIEW_RESPONSES.items() if code != 400},
    200: {**QUALITY_REVIEW_RESPONSES[200], "model": DocumentJobNewGenerationResponse,
        "description": "已接受请求的只读事实和当前任务观察；不会重新投递。"},
    202: {**QUALITY_REVIEW_RESPONSES[200], "model": DocumentJobNewGenerationResponse,
        "description": "新代命令已接受；不代表生成已经成功。"},
    503: {**QUALITY_REVIEW_RESPONSES[503], "model": DocumentJobNewGenerationErrorResponse,
        "description": "接受结果未知或已接受后投递异常；保留原 UUID 并通过 GET 对账，禁止自动换 key。"},
    404: {**QUALITY_REVIEW_RESPONSES[404], "description": "可见任务、原源 PDF 实物或指定接受记录不存在。"},
    409: {**QUALITY_REVIEW_RESPONSES[409], "description": "来源、预算、任务状态或原 UUID 的身份与参数冲突。"},
    500: {**QUALITY_REVIEW_RESPONSES[500],
        "description": "服务内部错误；接受可能已提交，请保留原 UUID，使用 GET generation-requests/{request_id} 对账。"},
}


def _new_generation_unavailable_response(request: Request, error: NewGenerationRequestUnavailable):
    response = api_error_response(request, http_status_for(error), error.code, error.message, reason_code=error.reason_code)
    content = json.loads(response.body)
    content["error"]["generation_request_id"] = error.generation_request_id
    if error.accepted_generation is not None:
        content["error"].update(accepted=True, accepted_generation=error.accepted_generation)
    from fastapi.responses import JSONResponse
    return JSONResponse(content, status_code=http_status_for(error))


@quality_review_router.post("/{job_id}/new-generation", response_model=DocumentJobNewGenerationResponse,
    status_code=202, responses=_NEW_GENERATION_RESPONSES)
def request_document_job_new_generation(job_id: str, payload: DocumentJobNewGenerationRequest,
    request: Request, response: Response, runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_admin_user), trace_id: str = Depends(get_trace_id),
):
    """仅内部 Admin JWT 可显式开始同任务的新代；重放只返回接受事实。"""
    try:
        result, created = runtime.document_job_use_cases.publication.request_new_generation(job_id, user=user,
            request_id=payload.request_id, note=payload.note,
            expected_source=ReviewExpectedSource.model_validate(payload.expected_source.model_dump()), trace_id=trace_id)
    except NewGenerationRequestUnavailable as error:
        return _new_generation_unavailable_response(request, error)
    response.status_code = 202 if created else 200
    return result


@quality_review_router.get("/{job_id}/generation-requests/{request_id}", response_model=DocumentJobNewGenerationResponse,
    responses={code: value for code, value in _NEW_GENERATION_RESPONSES.items() if code != 202})
def get_document_job_generation_request(job_id: str, request_id: UUID, request: Request,
    runtime: AppRuntime = Depends(get_runtime), user: AuthenticatedUser = Depends(require_current_user),
):
    """主库同任务串行读取原 Admin 的接受事实，不补投或补写。"""
    try:
        return runtime.document_job_use_cases.publication.get_generation_request(job_id, request_id=str(request_id), user=user)
    except NewGenerationRequestUnavailable as error:
        return _new_generation_unavailable_response(request, error)
