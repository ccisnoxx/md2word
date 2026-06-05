# File: app/domains/term_rules/proposals_router.py
# Purpose: 提供术语 proposal 提交、查询和审核接口。

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_runtime, get_trace_id, require_admin_actor, require_current_user
from app.api.errors import bad_request_http_exception, not_found_http_exception
from app.core.errors import ApiError
from app.core.runtime import AppRuntime
from app.domains.audit.models import ActorContext
from app.domains.term_rules.models import (
    TermRuleProposalIntent,
    TermRuleProposalRecord,
    TermRuleProposalStatus,
)
from app.domains.term_rules.proposals_service import (
    TermRuleProposalBulkReviewItem,
    TermRuleProposalConflictError,
    TermRuleProposalService,
)
from app.domains.term_rules.versioning_service import DEFAULT_TERM_RULE_SET_ID
from app.domains.term_rules.schemas import (
    TermRuleProposalApproveAndPublishRequest,
    TermRuleProposalBulkItemResponse,
    TermRuleProposalBulkRejectRequest,
    TermRuleProposalBulkResponse,
    TermRuleProposalBulkReviewRequest,
    TermRuleProposalConflictResponse,
    TermRuleProposalCreateRequest,
    TermRuleProposalListResponse,
    TermRuleProposalRejectRequest,
    TermRuleProposalResponse,
    TermRuleProposalReviewRequest,
    TermRuleSegmentResponse,
)
from app.services.auth.models import AuthenticatedUser


router = APIRouter(prefix="/term-rule-proposals", tags=["term-rule-proposals"])
TERM_RULE_PROPOSAL_CONFLICT_RESPONSES = {
    status.HTTP_409_CONFLICT: {
        "model": TermRuleProposalConflictResponse,
        "description": "Term Rule Proposal 与当前 draft 存在冲突。",
    },
}


def _require_proposal_service(runtime: AppRuntime) -> TermRuleProposalService:
    service = runtime.term_rule_proposal_service
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Term Rule Proposal 需要 JOBS_REPOSITORY_BACKEND=mysql。",
        )
    return service


def _serialize_proposal(proposal: TermRuleProposalRecord) -> TermRuleProposalResponse:
    return TermRuleProposalResponse(
        id=proposal.id,
        intent=proposal.intent.value,
        status=proposal.status.value,
        source_term=proposal.source_term,
        category_id=proposal.category_id,
        segments=[
            TermRuleSegmentResponse(
                seq=segment.seq,
                segment_text=segment.segment_text,
                render_type=segment.render_type.value,
            )
            for segment in proposal.segments
        ],
        reason=proposal.reason,
        source_job_id=proposal.source_job_id,
        source_file_id=proposal.source_file_id,
        page_number=proposal.page_number,
        context_before=proposal.context_before,
        context_after=proposal.context_after,
        observed_term_rule_set_id=proposal.observed_term_rule_set_id,
        observed_term_rule_version=proposal.observed_term_rule_version,
        target_rule_id=proposal.target_rule_id,
        target_rule_snapshot=proposal.target_rule_snapshot,
        created_by=proposal.created_by,
        created_at=proposal.created_at,
        reviewed_by=proposal.reviewed_by,
        reviewed_at=proposal.reviewed_at,
        review_comment=proposal.review_comment,
        merged_term_rule_set_id=proposal.merged_term_rule_set_id,
        merged_draft_snapshot_hash=proposal.merged_draft_snapshot_hash,
        published_term_rule_set_id=proposal.published_term_rule_set_id,
        published_term_rule_set_version=proposal.published_term_rule_set_version,
        published_at=proposal.published_at,
    )


def _parse_status(raw_status: str | None) -> TermRuleProposalStatus | None:
    if raw_status is None:
        return None
    try:
        return TermRuleProposalStatus(raw_status)
    except ValueError as exc:
        raise bad_request_http_exception(ValueError(f"不支持的 proposal status: {raw_status}")) from exc


def _parse_intent(raw_intent: str) -> TermRuleProposalIntent:
    try:
        return TermRuleProposalIntent(raw_intent)
    except ValueError as exc:
        raise bad_request_http_exception(ValueError(f"不支持的 proposal intent: {raw_intent}")) from exc


def _ensure_proposal_visible(proposal: TermRuleProposalRecord, user: AuthenticatedUser) -> None:
    if user.role == "admin" or proposal.created_by == user.id:
        return
    raise ApiError(status.HTTP_403_FORBIDDEN, "role_forbidden", "当前角色无权限查看该 proposal。")


def _actor_from_user(user: AuthenticatedUser) -> ActorContext:
    return ActorContext(actor_id=user.id, actor_role=user.role, source="jwt")


def _proposal_conflict_http_exception(exc: TermRuleProposalConflictError) -> HTTPException:
    """把 service 层 proposal 冲突转换为稳定的结构化 409 响应。"""

    detail = TermRuleProposalConflictResponse(
        message="proposal 与当前 draft 存在冲突，请重新核对后处理。",
        conflicts=list(exc.conflicts),
    ).model_dump(mode="json")
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _serialize_bulk_item(item: TermRuleProposalBulkReviewItem) -> TermRuleProposalBulkItemResponse:
    """把 service 层批量审核结果映射为 API item。"""

    return TermRuleProposalBulkItemResponse(
        proposal_id=item.proposal_id,
        ok=item.ok,
        status_code=item.status_code,
        error_code=item.error_code,
        detail=item.detail,
        proposal=_serialize_proposal(item.proposal) if item.proposal is not None else None,
    )


def _build_bulk_response(
    action: str,
    items: list[TermRuleProposalBulkReviewItem],
) -> TermRuleProposalBulkResponse:
    """汇总批量审核成功和失败数量。"""

    succeeded = sum(1 for item in items if item.ok)
    return TermRuleProposalBulkResponse(
        action=action,
        total=len(items),
        succeeded=succeeded,
        failed=len(items) - succeeded,
        items=[_serialize_bulk_item(item) for item in items],
    )


@router.post("", response_model=TermRuleProposalResponse, status_code=status.HTTP_201_CREATED)
def create_term_rule_proposal(
    payload: TermRuleProposalCreateRequest,
    user: AuthenticatedUser = Depends(require_current_user),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> TermRuleProposalResponse:
    try:
        proposal = _require_proposal_service(runtime).create_proposal(
            intent=_parse_intent(payload.intent),
            source_term=payload.source_term,
            category_id=payload.category_id,
            segments=[item.model_dump() for item in payload.segments] if payload.segments is not None else None,
            reason=payload.reason,
            source_job_id=payload.source_job_id,
            source_file_id=payload.source_file_id,
            page_number=payload.page_number,
            context_before=payload.context_before,
            context_after=payload.context_after,
            observed_term_rule_set_id=payload.observed_term_rule_set_id,
            observed_term_rule_version=payload.observed_term_rule_version,
            target_rule_id=payload.target_rule_id,
            created_by=user.id,
            actor=_actor_from_user(user),
            trace_id=trace_id,
        )
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc
    return _serialize_proposal(proposal)


@router.get("", response_model=TermRuleProposalListResponse)
def list_term_rule_proposals(
    scope: str = Query(default="my", pattern="^(my|all|pending_review|approved_unpublished)$"),
    proposal_status: str | None = Query(default=None, alias="status"),
    user: AuthenticatedUser = Depends(require_current_user),
    runtime: AppRuntime = Depends(get_runtime),
) -> TermRuleProposalListResponse:
    if user.role != "admin" and scope != "my":
        raise ApiError(status.HTTP_403_FORBIDDEN, "role_forbidden", "当前角色无权限查看其他人的 proposal。")
    service = _require_proposal_service(runtime)
    if scope == "approved_unpublished":
        items = service.list_approved_unpublished_proposals(DEFAULT_TERM_RULE_SET_ID)
    else:
        status_filter = TermRuleProposalStatus.PENDING_REVIEW if scope == "pending_review" else _parse_status(proposal_status)
        created_by = user.id if scope == "my" else None
        items = service.list_proposals(status=status_filter, created_by=created_by)
    return TermRuleProposalListResponse(items=[_serialize_proposal(item) for item in items], total=len(items))


@router.post("/bulk-approve", response_model=TermRuleProposalBulkResponse)
def bulk_approve_term_rule_proposals(
    payload: TermRuleProposalBulkReviewRequest,
    actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> TermRuleProposalBulkResponse:
    """批量 approve term rule proposals，逐项复用单条审核语义。"""

    try:
        items = _require_proposal_service(runtime).bulk_approve_proposals(
            payload.proposal_ids,
            reviewed_by=actor.actor_id or "admin",
            review_comment=payload.review_comment,
            actor=actor,
            trace_id=trace_id,
        )
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc
    return _build_bulk_response("approve", items)


@router.post("/bulk-reject", response_model=TermRuleProposalBulkResponse)
def bulk_reject_term_rule_proposals(
    payload: TermRuleProposalBulkRejectRequest,
    actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> TermRuleProposalBulkResponse:
    """批量 reject term rule proposals，逐项复用单条拒绝语义。"""

    try:
        items = _require_proposal_service(runtime).bulk_reject_proposals(
            payload.proposal_ids,
            reviewed_by=actor.actor_id or "admin",
            review_comment=payload.review_comment,
            actor=actor,
            trace_id=trace_id,
        )
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc
    return _build_bulk_response("reject", items)


@router.get("/{proposal_id}", response_model=TermRuleProposalResponse)
def get_term_rule_proposal(
    proposal_id: str,
    user: AuthenticatedUser = Depends(require_current_user),
    runtime: AppRuntime = Depends(get_runtime),
) -> TermRuleProposalResponse:
    try:
        proposal = _require_proposal_service(runtime).get_proposal(proposal_id)
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    _ensure_proposal_visible(proposal, user)
    return _serialize_proposal(proposal)


@router.post(
    "/{proposal_id}/approve",
    response_model=TermRuleProposalResponse,
    responses=TERM_RULE_PROPOSAL_CONFLICT_RESPONSES,
)
def approve_term_rule_proposal(
    proposal_id: str,
    payload: TermRuleProposalReviewRequest | None = None,
    actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> TermRuleProposalResponse:
    """审核 proposal，并在 draft 证据冲突时返回结构化 409。"""

    try:
        proposal = _require_proposal_service(runtime).approve_proposal(
            proposal_id,
            reviewed_by=actor.actor_id or "admin",
            review_comment=payload.review_comment if payload is not None else None,
            actor=actor,
            trace_id=trace_id,
        )
    except TermRuleProposalConflictError as exc:
        raise _proposal_conflict_http_exception(exc) from exc
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc
    return _serialize_proposal(proposal)


@router.post(
    "/{proposal_id}/approve-and-publish",
    response_model=TermRuleProposalResponse,
    responses=TERM_RULE_PROPOSAL_CONFLICT_RESPONSES,
)
def approve_and_publish_term_rule_proposal(
    proposal_id: str,
    payload: TermRuleProposalApproveAndPublishRequest | None = None,
    actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> TermRuleProposalResponse:
    """审核并发布 proposal；approve 阶段冲突时不执行发布。"""

    try:
        proposal = _require_proposal_service(runtime).approve_and_publish_proposal(
            proposal_id,
            reviewed_by=actor.actor_id or "admin",
            review_comment=payload.review_comment if payload is not None else None,
            publish_reason=payload.publish_reason if payload is not None else None,
            actor=actor,
            trace_id=trace_id,
        )
    except TermRuleProposalConflictError as exc:
        raise _proposal_conflict_http_exception(exc) from exc
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc
    return _serialize_proposal(proposal)


@router.post("/{proposal_id}/reject", response_model=TermRuleProposalResponse)
def reject_term_rule_proposal(
    proposal_id: str,
    payload: TermRuleProposalRejectRequest,
    actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> TermRuleProposalResponse:
    try:
        proposal = _require_proposal_service(runtime).reject_proposal(
            proposal_id,
            reviewed_by=actor.actor_id or "admin",
            review_comment=payload.review_comment,
            actor=actor,
            trace_id=trace_id,
        )
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc
    return _serialize_proposal(proposal)
