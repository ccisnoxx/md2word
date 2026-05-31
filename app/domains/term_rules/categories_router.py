from __future__ import annotations

# app/domains/term_rules/categories_router.py: 提供术语规则分类查询和管理接口。

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_runtime
from app.api.dependencies import require_admin_access
from app.api.errors import bad_request_http_exception, not_found_http_exception
from app.domains.term_rules.write_guard import ensure_legacy_term_rule_write_allowed
from app.core.runtime import AppRuntime
from app.domains.term_rules.schemas import (
    TermRuleCategoryCreateRequest,
    TermRuleCategoryListItemResponse,
    TermRuleCategoryListResponse,
    TermRuleCategoryUpdateRequest,
    TermRuleDeleteResponse,
)


router = APIRouter(prefix="/term-rule-categories", tags=["term-rule-categories"])


def _serialize_category(runtime: AppRuntime, category_id: str) -> TermRuleCategoryListItemResponse:
    for category, rule_count, enabled_rule_count in runtime.term_rule_service.list_categories_with_counts():
        if category.id == category_id:
            return TermRuleCategoryListItemResponse(
                id=category.id,
                code=category.code,
                name=category.name,
                priority=category.priority,
                enabled=category.enabled,
                description=category.description,
                rule_count=rule_count,
                enabled_rule_count=enabled_rule_count,
            )
    raise FileNotFoundError(f"分类不存在: {category_id}")


@router.get("", response_model=TermRuleCategoryListResponse)
def list_term_rule_categories(
    runtime: AppRuntime = Depends(get_runtime),
) -> TermRuleCategoryListResponse:
    items = [
        TermRuleCategoryListItemResponse(
            id=category.id,
            code=category.code,
            name=category.name,
            priority=category.priority,
            enabled=category.enabled,
            description=category.description,
            rule_count=rule_count,
            enabled_rule_count=enabled_rule_count,
        )
        for category, rule_count, enabled_rule_count in runtime.term_rule_service.list_categories_with_counts()
    ]
    return TermRuleCategoryListResponse(items=items)


@router.post("", response_model=TermRuleCategoryListItemResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin_access)])
def create_term_rule_category(
    payload: TermRuleCategoryCreateRequest,
    runtime: AppRuntime = Depends(get_runtime),
) -> TermRuleCategoryListItemResponse:
    ensure_legacy_term_rule_write_allowed(runtime)
    try:
        category = runtime.term_rule_service.create_category(
            category_id=payload.id,
            code=payload.code,
            name=payload.name,
            priority=payload.priority,
            enabled=payload.enabled,
            description=payload.description,
        )
        return _serialize_category(runtime, category.id)
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc


@router.patch("/{category_id}", response_model=TermRuleCategoryListItemResponse, dependencies=[Depends(require_admin_access)])
def update_term_rule_category(
    category_id: str,
    payload: TermRuleCategoryUpdateRequest,
    runtime: AppRuntime = Depends(get_runtime),
) -> TermRuleCategoryListItemResponse:
    ensure_legacy_term_rule_write_allowed(runtime)
    fields = {
        field_name: getattr(payload, field_name)
        for field_name in payload.model_fields_set
        if getattr(payload, field_name) is not None
    }
    try:
        category = runtime.term_rule_service.update_category(category_id, fields)
        return _serialize_category(runtime, category.id)
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc


@router.delete("/{category_id}", response_model=TermRuleDeleteResponse, dependencies=[Depends(require_admin_access)])
def delete_term_rule_category(
    category_id: str,
    runtime: AppRuntime = Depends(get_runtime),
) -> TermRuleDeleteResponse:
    ensure_legacy_term_rule_write_allowed(runtime)
    try:
        runtime.term_rule_service.delete_category(category_id)
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc
    return TermRuleDeleteResponse(id=category_id, deleted=True)
