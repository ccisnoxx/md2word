from __future__ import annotations

# File: app/domains/term_rules/review_router.py
# Purpose: Expose term-rule review batch submission, item review, and history APIs.

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import get_runtime, get_trace_id, require_admin_user, require_current_user
from app.core.errors import ApiError
from app.core.runtime import AppRuntime
from app.domains.audit.models import ActorContext
from app.domains.term_rules.models import (
    TermRuleReviewBatchRecord,
    TermRuleReviewItemRecord,
    TermRuleReviewItemStatus,
    TermRuleVersionRecord,
)
from app.domains.term_rules.schemas import (
    TermRuleReviewBatchCreateRequest,
    TermRuleReviewBatchListResponse,
    TermRuleReviewBatchResponse,
    TermRuleReviewBatchSummaryResponse,
    TermRuleReviewBulkItemResponse,
    TermRuleReviewBulkRequest,
    TermRuleReviewBulkResponse,
    TermRuleReviewDecisionRequest,
    TermRuleReviewItemResponse,
    TermRuleReviewRejectRequest,
    TermRuleVersionResponse,
)
from app.services.auth.models import AuthenticatedUser


router = APIRouter(prefix="/term-rule-reviews", tags=["term-rule-reviews"])


@router.post("/batches", response_model=TermRuleReviewBatchResponse, status_code=status.HTTP_201_CREATED)
def create_review_batch(
    payload: TermRuleReviewBatchCreateRequest,
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
    user: AuthenticatedUser = Depends(require_current_user),
) -> TermRuleReviewBatchResponse:
    service = _require_service(runtime)
    batch, items = service.create_batch(
        submitted_by=user.id,
        submitter_role=user.role,
        submitter_department_id=user.department_id,
        source_job_id=payload.source_job_id,
        source_file_id=payload.source_file_id,
        reason=payload.reason,
        raw_items=payload.items,
        actor=_actor_from_user(user),
        trace_id=trace_id,
    )
    return _batch_response(batch, items)


@router.get("/batches", response_model=TermRuleReviewBatchListResponse)
def list_review_batches(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    mine: bool = Query(default=False),
    submitted_by: str | None = Query(default=None),
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> TermRuleReviewBatchListResponse:
    service = _require_service(runtime)
    effective_submitter = user.id if user.role != "admin" or mine else submitted_by
    batches, total = service.list_batches(submitted_by=effective_submitter, page=page, page_size=page_size)
    return TermRuleReviewBatchListResponse(
        items=[
            _batch_response(batch, service.list_items(batch_id=batch.id), include_items=False)
            for batch in batches
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/batches/{batch_id}", response_model=TermRuleReviewBatchResponse)
def get_review_batch(
    batch_id: str,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> TermRuleReviewBatchResponse:
    service = _require_service(runtime)
    batch = service.get_batch(batch_id)
    _ensure_batch_visible(batch, user)
    return _batch_response(batch, service.list_items(batch_id=batch.id))


@router.get("/items", response_model=list[TermRuleReviewItemResponse])
def list_review_items(
    status_value: TermRuleReviewItemStatus | None = Query(default=None, alias="status"),
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_admin_user),
) -> list[TermRuleReviewItemResponse]:
    service = _require_service(runtime)
    return [_item_response(item) for item in service.repository.list_items(status=status_value)]


@router.post("/items/{item_id}/approve", response_model=TermRuleReviewItemResponse)
def approve_review_item(
    item_id: str,
    payload: TermRuleReviewDecisionRequest,
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
    user: AuthenticatedUser = Depends(require_admin_user),
) -> TermRuleReviewItemResponse:
    service = _require_service(runtime)
    item = service.approve_item(
        item_id,
        reviewed_by=user.id,
        reason=payload.reason,
        actor=_actor_from_user(user),
        trace_id=trace_id,
    )
    return _item_response(item)


@router.post("/items/{item_id}/reject", response_model=TermRuleReviewItemResponse)
def reject_review_item(
    item_id: str,
    payload: TermRuleReviewRejectRequest,
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
    user: AuthenticatedUser = Depends(require_admin_user),
) -> TermRuleReviewItemResponse:
    service = _require_service(runtime)
    item = service.reject_item(
        item_id,
        reviewed_by=user.id,
        reason=payload.reason,
        actor=_actor_from_user(user),
        trace_id=trace_id,
    )
    return _item_response(item)


@router.post("/items/bulk-approve", response_model=TermRuleReviewBulkResponse)
def bulk_approve_review_items(
    payload: TermRuleReviewBulkRequest,
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
    user: AuthenticatedUser = Depends(require_admin_user),
) -> TermRuleReviewBulkResponse:
    return _bulk_response(
        "approve",
        _require_service(runtime).bulk_review(
            action="approve",
            item_ids=payload.item_ids,
            reviewed_by=user.id,
            reason=payload.reason,
            actor=_actor_from_user(user),
            trace_id=trace_id,
        ),
    )


@router.post("/items/bulk-reject", response_model=TermRuleReviewBulkResponse)
def bulk_reject_review_items(
    payload: TermRuleReviewBulkRequest,
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
    user: AuthenticatedUser = Depends(require_admin_user),
) -> TermRuleReviewBulkResponse:
    return _bulk_response(
        "reject",
        _require_service(runtime).bulk_review(
            action="reject",
            item_ids=payload.item_ids,
            reviewed_by=user.id,
            reason=payload.reason,
            actor=_actor_from_user(user),
            trace_id=trace_id,
        ),
    )


@router.get("/history", response_model=list[TermRuleVersionResponse])
def list_term_rule_versions(
    rule_id: str | None = Query(default=None),
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_current_user),
) -> list[TermRuleVersionResponse]:
    service = _require_service(runtime)
    return [_version_response(version) for version in service.repository.list_versions(rule_id=rule_id)]


def _require_service(runtime: AppRuntime):
    service = runtime.term_rule_review_service
    if service is None:
        raise ApiError(status.HTTP_503_SERVICE_UNAVAILABLE, "service_unavailable", "术语规则审核流需要 MySQL/resource version backend。")
    return service


def _ensure_batch_visible(batch: TermRuleReviewBatchRecord, user: AuthenticatedUser) -> None:
    if user.role == "admin" or batch.submitted_by == user.id:
        return
    raise ApiError(status.HTTP_403_FORBIDDEN, "role_forbidden", "只能查看自己提交的术语规则审核批次。")


def _batch_response(
    batch: TermRuleReviewBatchRecord,
    items: list[TermRuleReviewItemRecord],
    *,
    include_items: bool = True,
) -> TermRuleReviewBatchResponse:
    summary = _summary(items)
    return TermRuleReviewBatchResponse(
        id=batch.id,
        submitted_by=batch.submitted_by,
        submitter_department_id=batch.submitter_department_id,
        source_job_id=batch.source_job_id,
        source_file_id=batch.source_file_id,
        reason=batch.reason,
        status=_batch_status(summary),
        summary=summary,
        items=[_item_response(item) for item in items] if include_items else [],
        created_at=batch.created_at,
        updated_at=batch.updated_at,
    )


def _summary(items: list[TermRuleReviewItemRecord]) -> TermRuleReviewBatchSummaryResponse:
    counts = {status_value.value: 0 for status_value in TermRuleReviewItemStatus}
    for item in items:
        counts[item.status.value] = counts.get(item.status.value, 0) + 1
    return TermRuleReviewBatchSummaryResponse(
        pending=counts.get("pending", 0),
        approved=counts.get("approved", 0),
        rejected=counts.get("rejected", 0),
        conflict=counts.get("conflict", 0),
        total=len(items),
    )


def _batch_status(summary: TermRuleReviewBatchSummaryResponse) -> str:
    if summary.pending:
        return "pending"
    if summary.total == 0:
        return "empty"
    if summary.approved == summary.total:
        return "approved"
    if summary.rejected == summary.total:
        return "rejected"
    if summary.conflict and not summary.approved:
        return "conflict"
    return "partial_approved"


def _item_response(item: TermRuleReviewItemRecord) -> TermRuleReviewItemResponse:
    return TermRuleReviewItemResponse(
        id=item.id,
        batch_id=item.batch_id,
        seq=item.seq,
        action=item.action.value,
        status=item.status.value,
        scope_type=item.scope_type.value,
        scope_id=item.scope_id,
        normalized_term=item.normalized_term,
        target_rule_id=item.target_rule_id,
        base_version=item.base_version,
        submitted_snapshot=item.submitted_snapshot,
        rejection_reason=item.rejection_reason,
        conflict_reason=item.conflict_reason,
        reviewed_by=item.reviewed_by,
        reviewed_at=item.reviewed_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _version_response(version: TermRuleVersionRecord) -> TermRuleVersionResponse:
    return TermRuleVersionResponse(
        id=version.id,
        rule_id=version.rule_id,
        version=version.version,
        action=version.action.value,
        scope_type=version.scope_type.value,
        scope_id=version.scope_id,
        normalized_term=version.normalized_term,
        review_item_id=version.review_item_id,
        before_snapshot=version.before_snapshot,
        after_snapshot=version.after_snapshot,
        created_by=version.created_by,
        created_at=version.created_at,
    )


def _bulk_response(action: str, results) -> TermRuleReviewBulkResponse:
    items = [
        TermRuleReviewBulkItemResponse(
            item_id=result.item_id,
            ok=result.ok,
            status_code=result.status_code,
            error_code=result.error_code,
            detail=result.detail,
            item=_item_response(result.item) if result.item is not None else None,
        )
        for result in results
    ]
    succeeded = sum(1 for item in items if item.ok)
    return TermRuleReviewBulkResponse(
        action=action,
        total=len(items),
        succeeded=succeeded,
        failed=len(items) - succeeded,
        items=items,
    )


def _actor_from_user(user: AuthenticatedUser) -> ActorContext:
    return ActorContext(actor_id=user.id, actor_role=user.role, source="jwt")
