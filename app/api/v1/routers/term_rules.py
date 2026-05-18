from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_runtime, require_admin_access
from app.core.runtime import AppRuntime
from app.schemas.api_v1 import (
    RuleExportResponse,
    RuleImportRequest,
    RuleSimulationRequest,
    RuleSimulationResponse,
    TermRuleFileSyncResponse,
    TermRuleImportValidationFindingResponse,
    TermRuleImportValidationReportResponse,
    TermRuleImportValidationSummaryResponse,
    TermRuleListResponse,
    TermRuleResponse,
    TermRuleSegmentResponse,
)


router = APIRouter(prefix="/term-rules", tags=["term-rules"])


def _serialize_rule(runtime: AppRuntime, rule) -> TermRuleResponse:
    categories = {item.id: item for item, _, _ in runtime.term_rule_service.list_categories_with_counts()}
    category = categories.get(rule.category_id)
    return TermRuleResponse(
        id=rule.id,
        category_id=rule.category_id,
        category_code=category.code if category is not None else "",
        category_name=category.name if category is not None else "",
        source_term=rule.source_term,
        rule_mode=rule.rule_mode.value,
        apply_scope=rule.apply_scope.value,
        case_sensitive=rule.case_sensitive,
        enabled=rule.enabled,
        priority=rule.priority,
        segments=[
            TermRuleSegmentResponse(
                seq=segment.seq,
                segment_text=segment.segment_text,
                render_type=segment.render_type.value,
            )
            for segment in rule.segments
        ],
        custom_html=rule.custom_html,
        custom_markdown=rule.custom_markdown,
        notes=rule.notes,
    )


@router.get("", response_model=TermRuleListResponse)
def list_term_rules(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    category_id: str | None = Query(default=None),
    enabled: bool | None = Query(default=None),
    q: str | None = Query(default=None),
    runtime: AppRuntime = Depends(get_runtime),
) -> TermRuleListResponse:
    items, total = runtime.term_rule_service.query_rules_page(
        category_id=category_id,
        enabled=enabled,
        q=q,
        page=page,
        page_size=page_size,
    )
    return TermRuleListResponse(
        items=[_serialize_rule(runtime, item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/export", response_model=RuleExportResponse)
def export_term_rules(
    runtime: AppRuntime = Depends(get_runtime),
) -> RuleExportResponse:
    return RuleExportResponse(yaml_text=runtime.term_rule_service.export_store_yaml())


@router.get("/{rule_id}", response_model=TermRuleResponse)
def get_term_rule(
    rule_id: str,
    runtime: AppRuntime = Depends(get_runtime),
) -> TermRuleResponse:
    try:
        rule = runtime.term_rule_service.get_rule(rule_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _serialize_rule(runtime, rule)


@router.post("/simulate", response_model=RuleSimulationResponse)
def simulate_term_rules(
    payload: RuleSimulationRequest,
    runtime: AppRuntime = Depends(get_runtime),
) -> RuleSimulationResponse:
    return RuleSimulationResponse.model_validate(runtime.term_rule_service.simulate(payload.text))


@router.post("/import/validate", response_model=TermRuleImportValidationReportResponse)
def validate_term_rule_import(
    payload: RuleImportRequest,
    runtime: AppRuntime = Depends(get_runtime),
) -> TermRuleImportValidationReportResponse:
    result = runtime.term_rule_import_validation_service.validate_yaml_text(payload.yaml_text)
    return TermRuleImportValidationReportResponse(
        valid=result.valid,
        summary=TermRuleImportValidationSummaryResponse(
            category_count=result.summary.category_count,
            rule_count=result.summary.rule_count,
            error_count=result.summary.error_count,
            warning_count=result.summary.warning_count,
        ),
        errors=[
            TermRuleImportValidationFindingResponse(code=item.code, message=item.message, path=item.path)
            for item in result.errors
        ],
        warnings=[
            TermRuleImportValidationFindingResponse(code=item.code, message=item.message, path=item.path)
            for item in result.warnings
        ],
    )


@router.post("/import", response_model=TermRuleListResponse, dependencies=[Depends(require_admin_access)])
def import_term_rules(
    payload: RuleImportRequest,
    runtime: AppRuntime = Depends(get_runtime),
) -> TermRuleListResponse:
    result = runtime.term_rule_import_validation_service.validate_yaml_text(payload.yaml_text)
    if not result.valid or result.parsed_store is None:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_import_payload",
                "report": {
                    "valid": result.valid,
                    "summary": {
                        "category_count": result.summary.category_count,
                        "rule_count": result.summary.rule_count,
                        "error_count": result.summary.error_count,
                        "warning_count": result.summary.warning_count,
                    },
                    "errors": [item.model_dump() for item in result.errors],
                    "warnings": [item.model_dump() for item in result.warnings],
                },
            },
        )

    store = runtime.term_rule_service.apply_import_store(result.parsed_store)
    items = sorted(store.rules, key=lambda item: (item.priority, item.source_term))
    return TermRuleListResponse(
        items=[_serialize_rule(runtime, item) for item in items],
        page=1,
        page_size=max(len(items), 1),
        total=len(items),
    )


@router.post("/sync-files", response_model=TermRuleFileSyncResponse, dependencies=[Depends(require_admin_access)])
def sync_term_rule_files(
    runtime: AppRuntime = Depends(get_runtime),
) -> TermRuleFileSyncResponse:
    result = runtime.term_rule_file_sync_service.sync_files()
    return TermRuleFileSyncResponse(
        repository_backend=result.repository_backend,
        category_count=result.category_count,
        rule_count=result.rule_count,
        bootstrap_seed_path=str(result.bootstrap_seed_path),
        runtime_yaml_path=str(result.runtime_yaml_path),
        warnings=result.warnings,
    )
