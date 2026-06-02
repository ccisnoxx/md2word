from __future__ import annotations

# app/domains/translation/proposals_router.py: 提供 Translation Term Proposal 提交、查询和审核接口。

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_runtime, get_trace_id, require_admin_actor, require_current_user
from app.api.errors import bad_request_http_exception, not_found_http_exception
from app.core.errors import ApiError
from app.core.runtime import AppRuntime
from app.domains.audit.models import ActorContext
from app.domains.translation.models import TranslationTermProposalRecord, TranslationTermProposalStatus
from app.domains.translation.proposals_service import (
    TranslationTermProposalConflictError,
    TranslationTermProposalService,
)
from app.domains.translation.schemas import (
    TranslationTermProposalApproveAndPublishRequest,
    TranslationTermProposalChangeResponse,
    TranslationTermProposalCreateRequest,
    TranslationTermProposalListResponse,
    TranslationTermProposalRejectRequest,
    TranslationTermProposalResponse,
    TranslationTermProposalReviewRequest,
)
from app.services.auth.models import AuthenticatedUser


router = APIRouter(prefix="/translation-term-proposals", tags=["translation-term-proposals"])


def _require_translation_term_proposal_service(runtime: AppRuntime) -> TranslationTermProposalService:
    service = runtime.translation_term_proposal_service
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Translation Term Proposal 需要 JOBS_REPOSITORY_BACKEND=mysql。",
        )
    return service


def _actor_from_user(user: AuthenticatedUser) -> ActorContext:
    return ActorContext(actor_id=user.id, actor_role=user.role, source="jwt")


def _serialize_proposal(proposal: TranslationTermProposalRecord) -> TranslationTermProposalResponse:
    return TranslationTermProposalResponse(
        id=proposal.id,
        status=proposal.status,
        submitted_by=proposal.submitted_by,
        source_job_id=proposal.source_job_id,
        source_file_id=proposal.source_file_id,
        observed_translation_term_set_id=proposal.observed_translation_term_set_id,
        observed_translation_term_version=proposal.observed_translation_term_version,
        reviewed_by=proposal.reviewed_by,
        reviewed_at=proposal.reviewed_at,
        review_note=proposal.review_note,
        published_translation_term_set_id=proposal.published_translation_term_set_id,
        published_translation_term_version=proposal.published_translation_term_version,
        published_at=proposal.published_at,
        changes=[
            TranslationTermProposalChangeResponse(
                seq=change.seq,
                action=change.action,
                source_term=change.source_term,
                normalized_source_term=change.normalized_source_term,
                target_term=change.target_term,
                case_sensitive=change.case_sensitive,
                status=change.status,
                priority=change.priority,
                domain=change.domain,
                category=change.category,
                note=change.note,
            )
            for change in proposal.changes
        ],
        created_at=proposal.created_at,
    )


def _parse_status(raw_status: str | None) -> TranslationTermProposalStatus | None:
    if raw_status is None:
        return None
    if raw_status not in {"pending", "approved", "rejected", "published"}:
        raise bad_request_http_exception(ValueError(f"不支持的 proposal status: {raw_status}"))
    return raw_status


def _ensure_proposal_visible(proposal: TranslationTermProposalRecord, user: AuthenticatedUser) -> None:
    if user.role == "admin" or proposal.submitted_by == user.id:
        return
    raise ApiError(status.HTTP_403_FORBIDDEN, "role_forbidden", "当前角色无权限查看该 proposal。")


@router.post("", response_model=TranslationTermProposalResponse, status_code=status.HTTP_201_CREATED)
def create_translation_term_proposal(
    payload: TranslationTermProposalCreateRequest,
    user: AuthenticatedUser = Depends(require_current_user),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> TranslationTermProposalResponse:
    try:
        proposal = _require_translation_term_proposal_service(runtime).create_proposal(
            language_pair=payload.language_pair,
            changes=[item.model_dump() for item in payload.changes],
            submitted_by=user.id,
            source_job_id=payload.source_job_id,
            source_file_id=payload.source_file_id,
            observed_translation_term_set_id=payload.observed_translation_term_set_id,
            observed_translation_term_version=payload.observed_translation_term_version,
            actor=_actor_from_user(user),
            trace_id=trace_id,
        )
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc
    return _serialize_proposal(proposal)


@router.get("", response_model=TranslationTermProposalListResponse)
def list_translation_term_proposals(
    scope: str = Query(default="my", pattern="^(my|all|pending)$"),
    proposal_status: str | None = Query(default=None, alias="status"),
    user: AuthenticatedUser = Depends(require_current_user),
    runtime: AppRuntime = Depends(get_runtime),
) -> TranslationTermProposalListResponse:
    if user.role != "admin" and scope != "my":
        raise ApiError(status.HTTP_403_FORBIDDEN, "role_forbidden", "当前角色无权限查看其他人的 proposal。")
    service = _require_translation_term_proposal_service(runtime)
    status_filter = "pending" if scope == "pending" else _parse_status(proposal_status)
    submitted_by = user.id if scope == "my" else None
    items = service.list_proposals(status=status_filter, submitted_by=submitted_by)
    return TranslationTermProposalListResponse(items=[_serialize_proposal(item) for item in items], total=len(items))


@router.get("/{proposal_id}", response_model=TranslationTermProposalResponse)
def get_translation_term_proposal(
    proposal_id: str,
    user: AuthenticatedUser = Depends(require_current_user),
    runtime: AppRuntime = Depends(get_runtime),
) -> TranslationTermProposalResponse:
    try:
        proposal = _require_translation_term_proposal_service(runtime).get_proposal(proposal_id)
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    _ensure_proposal_visible(proposal, user)
    return _serialize_proposal(proposal)


@router.post("/{proposal_id}/approve", response_model=TranslationTermProposalResponse)
def approve_translation_term_proposal(
    proposal_id: str,
    payload: TranslationTermProposalReviewRequest | None = None,
    actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> TranslationTermProposalResponse:
    try:
        proposal = _require_translation_term_proposal_service(runtime).approve_proposal(
            proposal_id,
            reviewed_by=actor.actor_id or "admin",
            review_note=payload.review_note if payload is not None else None,
            actor=actor,
            trace_id=trace_id,
        )
    except TranslationTermProposalConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "translation_term_proposal_conflict", "conflicts": list(exc.conflicts)},
        ) from exc
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc
    return _serialize_proposal(proposal)


@router.post("/{proposal_id}/approve-and-publish", response_model=TranslationTermProposalResponse)
def approve_and_publish_translation_term_proposal(
    proposal_id: str,
    payload: TranslationTermProposalApproveAndPublishRequest | None = None,
    actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> TranslationTermProposalResponse:
    try:
        proposal = _require_translation_term_proposal_service(runtime).approve_and_publish_proposal(
            proposal_id,
            reviewed_by=actor.actor_id or "admin",
            review_note=payload.review_note if payload is not None else None,
            release_note=payload.release_note if payload is not None else None,
            actor=actor,
            trace_id=trace_id,
        )
    except TranslationTermProposalConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "translation_term_proposal_conflict", "conflicts": list(exc.conflicts)},
        ) from exc
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc
    return _serialize_proposal(proposal)


@router.post("/{proposal_id}/reject", response_model=TranslationTermProposalResponse)
def reject_translation_term_proposal(
    proposal_id: str,
    payload: TranslationTermProposalRejectRequest,
    actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> TranslationTermProposalResponse:
    try:
        proposal = _require_translation_term_proposal_service(runtime).reject_proposal(
            proposal_id,
            reviewed_by=actor.actor_id or "admin",
            review_note=payload.review_note,
            actor=actor,
            trace_id=trace_id,
        )
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc
    return _serialize_proposal(proposal)
