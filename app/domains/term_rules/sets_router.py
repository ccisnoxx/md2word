from __future__ import annotations

# app/domains/term_rules/sets_router.py: 提供术语规则集草稿、发布、默认版本和回滚接口。

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_runtime, get_trace_id, require_admin_access, require_admin_actor
from app.api.errors import bad_request_http_exception, not_found_http_exception
from app.domains.audit.models import ActorContext
from app.core.runtime import AppRuntime
from app.domains.term_rules.schemas import (
    TermRuleSetDetailResponse,
    TermRuleSetDraftResponse,
    TermRuleSetDraftUpdateRequest,
    TermRuleSetListResponse,
    TermRuleSetPublishRequest,
    TermRuleSetRollbackRequest,
    TermRuleSetVersionResponse,
)


router = APIRouter(prefix="/term-rule-sets", tags=["term-rule-sets"])


def _require_term_rule_set_version_service(runtime: AppRuntime):
    service = runtime.term_rule_set_version_service
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Term Rule Set 版本发布需要 JOBS_REPOSITORY_BACKEND=mysql。",
        )
    return service


def _validation_report_payload(result) -> dict:
    return {
        "valid": result.valid,
        "summary": {
            "category_count": result.summary.category_count,
            "rule_count": result.summary.rule_count,
            "error_count": result.summary.error_count,
            "warning_count": result.summary.warning_count,
        },
        "errors": [item.model_dump() for item in result.errors],
        "warnings": [item.model_dump() for item in result.warnings],
    }


@router.get("", response_model=TermRuleSetListResponse)
def list_term_rule_sets(
    runtime: AppRuntime = Depends(get_runtime),
) -> TermRuleSetListResponse:
    return _require_term_rule_set_version_service(runtime).list_sets()


@router.get("/{set_id}", response_model=TermRuleSetDetailResponse)
def get_term_rule_set(
    set_id: str,
    runtime: AppRuntime = Depends(get_runtime),
) -> TermRuleSetDetailResponse:
    try:
        return _require_term_rule_set_version_service(runtime).get_set_detail(set_id)
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc


@router.get("/{set_id}/draft", response_model=TermRuleSetDraftResponse)
def get_term_rule_set_draft(
    set_id: str,
    runtime: AppRuntime = Depends(get_runtime),
) -> TermRuleSetDraftResponse:
    try:
        return _require_term_rule_set_version_service(runtime).get_draft(set_id)
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc


@router.put("/{set_id}/draft/rules", response_model=TermRuleSetDraftResponse, dependencies=[Depends(require_admin_access)])
def update_term_rule_set_draft_rules(
    set_id: str,
    payload: TermRuleSetDraftUpdateRequest,
    runtime: AppRuntime = Depends(get_runtime),
) -> TermRuleSetDraftResponse:
    service = _require_term_rule_set_version_service(runtime)
    result = runtime.term_rule_import_validation_service.validate_yaml_text(payload.yaml_text)
    if not result.valid or result.parsed_store is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_term_rule_set_draft",
                "report": _validation_report_payload(result),
            },
        )
    try:
        return service.update_draft(set_id, result.parsed_store)
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc


@router.post("/{set_id}/publish", response_model=TermRuleSetVersionResponse)
def publish_term_rule_set_draft(
    set_id: str,
    payload: TermRuleSetPublishRequest | None = None,
    actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> TermRuleSetVersionResponse:
    request = payload or TermRuleSetPublishRequest()
    try:
        return _require_term_rule_set_version_service(runtime).publish_draft(
            set_id,
            make_default=request.make_default,
            published_by=request.published_by,
            publish_reason=request.publish_reason,
            actor=actor,
            trace_id=trace_id,
        )
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc


@router.post("/{set_id}/versions/{version}/set-default", response_model=TermRuleSetVersionResponse)
def set_default_term_rule_set_version(
    set_id: str,
    version: str,
    actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> TermRuleSetVersionResponse:
    try:
        return _require_term_rule_set_version_service(runtime).set_default_version(
            set_id,
            version,
            actor=actor,
            trace_id=trace_id,
        )
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc


@router.post("/{set_id}/rollback", response_model=TermRuleSetVersionResponse)
def rollback_term_rule_set_version(
    set_id: str,
    payload: TermRuleSetRollbackRequest,
    actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> TermRuleSetVersionResponse:
    try:
        return _require_term_rule_set_version_service(runtime).rollback(
            set_id,
            payload.version,
            actor=actor,
            trace_id=trace_id,
        )
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc
