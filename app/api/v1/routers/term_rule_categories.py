from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_runtime
from app.core.runtime import AppRuntime
from app.schemas.api_v1 import TermRuleCategoryListItemResponse, TermRuleCategoryListResponse


router = APIRouter(prefix="/term-rule-categories", tags=["term-rule-categories"])


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
