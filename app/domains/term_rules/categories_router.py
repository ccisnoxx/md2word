# File: app/domains/term_rules/categories_router.py
# Purpose: 提供术语规则分类查询和管理接口。

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_runtime
from app.api.dependencies import require_admin_access
from app.api.errors import bad_request_http_exception, not_found_http_exception
from app.core.runtime import AppRuntime
from app.domains.term_rules.schemas import (
    TermRuleCategoryCreateRequest,
    TermRuleCategoryListItemResponse,
    TermRuleCategoryListResponse,
    TermRuleCategoryUpdateRequest,
    TermRuleDeleteResponse,
)
from app.domains.term_rules.models import TermRuleCategoryRecord
from app.domains.term_rules.versioning_service import DEFAULT_TERM_RULE_SET_ID
from app.domains.term_rules.write_guard import ensure_legacy_term_rule_write_allowed


router = APIRouter(prefix="/term-rule-categories", tags=["term-rule-categories"])


def _category_response(
    category: TermRuleCategoryRecord,
    rule_count: int,
    enabled_rule_count: int,
) -> TermRuleCategoryListItemResponse:
    """把 category record 和计数转换为 API 响应模型。"""

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


def _draft_category_items(runtime: AppRuntime) -> list[TermRuleCategoryListItemResponse] | None:
    """版本化模式下从 default Term Rule Set draft 读取分类，避免 legacy store 与 draft 脱节。"""

    if runtime.term_rule_set_version_service is None:
        return None
    store = runtime.term_rule_set_version_service.get_draft_store(DEFAULT_TERM_RULE_SET_ID)
    counts: dict[str, tuple[int, int]] = {}
    for rule in store.rules:
        total, enabled = counts.get(rule.category_id, (0, 0))
        counts[rule.category_id] = (total + 1, enabled + (1 if rule.enabled else 0))
    return [
        _category_response(category, *counts.get(category.id, (0, 0)))
        for category in sorted(store.categories, key=lambda item: (item.priority, item.code))
    ]


def _serialize_category(runtime: AppRuntime, category_id: str) -> TermRuleCategoryListItemResponse:
    for category, rule_count, enabled_rule_count in runtime.term_rule_service.list_categories_with_counts():
        if category.id == category_id:
            return _category_response(category, rule_count, enabled_rule_count)
    raise FileNotFoundError(f"分类不存在: {category_id}")


@router.get("", response_model=TermRuleCategoryListResponse)
def list_term_rule_categories(
    runtime: AppRuntime = Depends(get_runtime),
) -> TermRuleCategoryListResponse:
    """列出可提交 proposal 的分类；版本化模式优先返回 default draft 分类。"""

    draft_items = _draft_category_items(runtime)
    if draft_items is not None:
        return TermRuleCategoryListResponse(items=draft_items)
    items = [
        _category_response(category, rule_count, enabled_rule_count)
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
