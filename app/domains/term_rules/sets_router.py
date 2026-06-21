# File: app/domains/term_rules/sets_router.py
# Purpose: 提供术语规则集草稿、发布、默认版本和回滚接口。

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import (
    get_runtime,
    get_trace_id,
    require_admin_access,
    require_admin_actor,
    require_authenticated_or_admin_access,
)
from app.api.errors import bad_request_http_exception, not_found_http_exception
from app.domains.audit.models import ActorContext
from app.core.runtime import AppRuntime
from app.domains.term_rules.models import TermRuleImportValidationFinding
from app.domains.term_rules.schemas import (
    TermRuleCreateRequest,
    TermRuleDraftRuleDeleteResponse,
    TermRuleDraftRuleMutationResponse,
    TermRuleListResponse,
    TermRuleResponse,
    TermRuleSetDiffResponse,
    TermRuleSetExportManifestResponse,
    TermRuleSetExportResponse,
    TermRuleSetDetailResponse,
    TermRuleSetDraftResponse,
    TermRuleSetImportDuplicateResponse,
    TermRuleSetImportReportResponse,
    TermRuleSetImportRequest,
    TermRuleSetImportResponse,
    TermRuleSetDraftUpdateRequest,
    TermRuleSetListResponse,
    TermRuleSetPreflightResponse,
    TermRuleSetPublishRequest,
    TermRuleSetRollbackRequest,
    TermRuleSetVersionResponse,
    TermRuleUpdateRequest,
)
from app.domains.term_rules.versioning_service import (
    TermRuleSetImportDuplicate,
    TermRuleSetImportReport,
    TermRuleSetPreflightError,
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


def _validation_report_response(result) -> dict:
    return _validation_report_payload(result)


def _duplicate_source_term(finding) -> str:
    _prefix, _separator, source_term = finding.message.rpartition(":")
    return source_term.strip() or finding.message


def _build_import_report(result, *, dedupe: str) -> TermRuleSetImportReport:
    duplicates = tuple(
        TermRuleSetImportDuplicate(
            source_term=_duplicate_source_term(item),
            path=item.path,
            message=item.message,
        )
        for item in result.warnings
        if item.code == "duplicate_source_term"
    )
    return TermRuleSetImportReport(
        dedupe=dedupe,
        total_rules=result.summary.rule_count + len(duplicates),
        imported_rules=result.summary.rule_count,
        duplicate_rules=len(duplicates),
        duplicates=duplicates,
    )


def _import_report_response(report: TermRuleSetImportReport) -> TermRuleSetImportReportResponse:
    return TermRuleSetImportReportResponse(
        dedupe=report.dedupe,
        total_rules=report.total_rules,
        imported_rules=report.imported_rules,
        duplicate_rules=report.duplicate_rules,
        duplicates=[
            TermRuleSetImportDuplicateResponse(
                source_term=item.source_term,
                path=item.path,
                message=item.message,
            )
            for item in report.duplicates
        ],
    )


def _import_response(result) -> TermRuleSetImportResponse:
    payload = result.record.payload or {}
    return TermRuleSetImportResponse(
        target=result.target,
        term_rule_set_id=result.record.resource_id,
        version=result.version,
        rule_count=int(payload.get("rule_count") or 0),
        enabled_rule_count=int(payload.get("enabled_rule_count") or 0),
        snapshot_hash=result.record.snapshot_hash,
        validation=_validation_report_response(result.validation),
        import_report=_import_report_response(result.import_report),
    )


def _approved_unpublished_proposal_count(runtime: AppRuntime, term_rule_set_id: str) -> int:
    """返回当前规则集已审核但尚未发布的 proposal 数量。"""

    if runtime.term_rule_proposal_service is None:
        return 0
    return len(runtime.term_rule_proposal_service.list_approved_unpublished_proposals(term_rule_set_id))


@router.get("", response_model=TermRuleSetListResponse)
def list_term_rule_sets(
    runtime: AppRuntime = Depends(get_runtime),
    _access=Depends(require_authenticated_or_admin_access),
) -> TermRuleSetListResponse:
    return _require_term_rule_set_version_service(runtime).list_sets()


@router.get("/{set_id}", response_model=TermRuleSetDetailResponse)
def get_term_rule_set(
    set_id: str,
    runtime: AppRuntime = Depends(get_runtime),
    _access=Depends(require_authenticated_or_admin_access),
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
    _access=Depends(require_authenticated_or_admin_access),
) -> TermRuleSetDraftResponse:
    try:
        return _require_term_rule_set_version_service(runtime).get_draft(set_id)
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc


@router.get("/{set_id}/diff", response_model=TermRuleSetDiffResponse)
def diff_term_rule_set_draft(
    set_id: str,
    from_ref: str = Query(default="default", alias="from"),
    to_ref: str = Query(default="draft", alias="to"),
    include_unchanged: bool = Query(default=False),
    runtime: AppRuntime = Depends(get_runtime),
    _access=Depends(require_authenticated_or_admin_access),
) -> TermRuleSetDiffResponse:
    """返回 Term Rule Set draft 相对基线版本的结构化差异。"""

    try:
        return _require_term_rule_set_version_service(runtime).build_diff(
            set_id,
            from_ref=from_ref,
            to_ref=to_ref,
            include_unchanged=include_unchanged,
        )
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc


@router.get("/{set_id}/preflight", response_model=TermRuleSetPreflightResponse)
def preflight_term_rule_set_draft(
    set_id: str,
    base: str = Query(default="default"),
    runtime: AppRuntime = Depends(get_runtime),
    _access=Depends(require_authenticated_or_admin_access),
) -> TermRuleSetPreflightResponse:
    """返回 Term Rule Set draft 的发布前治理校验报告。"""

    try:
        return _require_term_rule_set_version_service(runtime).build_preflight(
            set_id,
            base_ref=base,
            approved_unpublished_proposal_count=_approved_unpublished_proposal_count(runtime, set_id),
        )
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc


@router.get("/{set_id}/draft/rules", response_model=TermRuleListResponse)
def list_term_rule_set_draft_rules(
    set_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    category_id: str | None = Query(default=None),
    enabled: bool | None = Query(default=None),
    q: str | None = Query(default=None),
    runtime: AppRuntime = Depends(get_runtime),
    _access=Depends(require_authenticated_or_admin_access),
) -> TermRuleListResponse:
    """分页查询 Term Rule Set draft 内的结构化规则。"""

    try:
        return _require_term_rule_set_version_service(runtime).list_draft_rules(
            set_id,
            category_id=category_id,
            enabled=enabled,
            q=q,
            page=page,
            page_size=page_size,
        )
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc


@router.get("/{set_id}/draft/rules/{rule_id}", response_model=TermRuleResponse)
def get_term_rule_set_draft_rule(
    set_id: str,
    rule_id: str,
    runtime: AppRuntime = Depends(get_runtime),
    _access=Depends(require_authenticated_or_admin_access),
) -> TermRuleResponse:
    """读取 Term Rule Set draft 内的一条结构化规则。"""

    try:
        return _require_term_rule_set_version_service(runtime).get_draft_rule(set_id, rule_id)
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc


@router.post(
    "/{set_id}/draft/rules",
    response_model=TermRuleDraftRuleMutationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_access)],
)
def create_term_rule_set_draft_rule(
    set_id: str,
    payload: TermRuleCreateRequest,
    runtime: AppRuntime = Depends(get_runtime),
) -> TermRuleDraftRuleMutationResponse:
    """在 Term Rule Set draft 内新增一条结构化规则。"""

    try:
        return _require_term_rule_set_version_service(runtime).create_draft_rule(set_id, payload)
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc


@router.patch(
    "/{set_id}/draft/rules/{rule_id}",
    response_model=TermRuleDraftRuleMutationResponse,
    dependencies=[Depends(require_admin_access)],
)
def update_term_rule_set_draft_rule(
    set_id: str,
    rule_id: str,
    payload: TermRuleUpdateRequest,
    runtime: AppRuntime = Depends(get_runtime),
) -> TermRuleDraftRuleMutationResponse:
    """更新 Term Rule Set draft 内的一条结构化规则。"""

    try:
        return _require_term_rule_set_version_service(runtime).update_draft_rule(
            set_id,
            rule_id,
            payload,
        )
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc


@router.delete(
    "/{set_id}/draft/rules/{rule_id}",
    response_model=TermRuleDraftRuleDeleteResponse,
    dependencies=[Depends(require_admin_access)],
)
def delete_term_rule_set_draft_rule(
    set_id: str,
    rule_id: str,
    runtime: AppRuntime = Depends(get_runtime),
) -> TermRuleDraftRuleDeleteResponse:
    """从 Term Rule Set draft 内移除一条结构化规则。"""

    try:
        return _require_term_rule_set_version_service(runtime).delete_draft_rule(set_id, rule_id)
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc


@router.put(
    "/{set_id}/draft/rules",
    response_model=TermRuleSetDraftResponse,
    dependencies=[Depends(require_admin_access)],
)
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


@router.post("/{set_id}/import", response_model=TermRuleSetImportResponse)
def import_term_rule_set(
    set_id: str,
    payload: TermRuleSetImportRequest,
    actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> TermRuleSetImportResponse:
    validation_result = runtime.term_rule_import_validation_service.validate_yaml_text(payload.yaml_text)
    errors = list(validation_result.errors)
    if payload.dedupe == "reject":
        errors.extend(
            TermRuleImportValidationFinding(
                code=item.code,
                message=item.message,
                path=item.path,
            )
            for item in validation_result.warnings
            if item.code == "duplicate_source_term"
        )
    validation_report = _require_term_rule_set_version_service(runtime).build_import_validation_report(
        valid=not errors,
        store=validation_result.parsed_store,
        errors=errors,
        warnings=validation_result.warnings,
    )
    if not validation_report.valid or validation_result.parsed_store is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_term_rule_set_import",
                "report": _validation_report_payload(validation_report),
            },
        )
    try:
        result = _require_term_rule_set_version_service(runtime).import_store(
            set_id,
            validation_result.parsed_store,
            target=payload.target,
            dedupe=payload.dedupe,
            validation=validation_report,
            import_report=_build_import_report(validation_result, dedupe=payload.dedupe),
            actor=actor,
            trace_id=trace_id,
        )
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc
    return _import_response(result)


@router.get("/{set_id}/export", response_model=TermRuleSetExportResponse)
def export_term_rule_set(
    set_id: str,
    version: str | None = Query(default=None),
    export_format: str = Query(default="term_rules_v2", alias="format", pattern="^(term_rules_v2|legacy_runtime)$"),
    actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> TermRuleSetExportResponse:
    try:
        result = _require_term_rule_set_version_service(runtime).export_version(
            set_id,
            version=version,
            export_format=export_format,
            actor=actor,
            trace_id=trace_id,
        )
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc
    return TermRuleSetExportResponse(
        manifest=TermRuleSetExportManifestResponse(
            set_id=result.set_id,
            version=result.version,
            format=result.format,
            exported_at=result.exported_at,
            exported_by=result.exported_by,
        ),
        yaml_text=result.yaml_text,
    )


@router.post("/{set_id}/publish", response_model=TermRuleSetVersionResponse)
def publish_term_rule_set_draft(
    set_id: str,
    payload: TermRuleSetPublishRequest,
    actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> TermRuleSetVersionResponse:
    """发布当前 draft；发布前 blocking preflight finding 会阻止创建版本。"""

    request = payload
    try:
        published = _require_term_rule_set_version_service(runtime).publish_draft(
            set_id,
            make_default=request.make_default,
            published_by=request.published_by,
            publish_reason=request.publish_reason,
            actor=actor,
            trace_id=trace_id,
        )
        if runtime.term_rule_proposal_service is not None:
            runtime.term_rule_proposal_service.mark_approved_proposals_published(
                term_rule_set_id=set_id,
                published_version=published.version,
        )
        return published
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except TermRuleSetPreflightError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "term_rule_set_preflight_failed",
                "report": exc.report.model_dump(mode="json"),
            },
        ) from exc
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
