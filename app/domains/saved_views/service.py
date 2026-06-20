"""Validate and mutate personal saved views for operations pages."""

from __future__ import annotations

# File: app/domains/saved_views/service.py
# Purpose: Validate and mutate personal saved views for operations pages.

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, get_args
from uuid import uuid4

from fastapi import status

from app.core.errors import ApiError
from app.domains.document_jobs.incidents import (
    DOCUMENT_JOB_INCIDENT_FAILURE_TYPES,
    DOCUMENT_JOB_INCIDENT_RETRY_BUCKETS,
    DOCUMENT_JOB_INCIDENT_SORTS,
)
from app.domains.document_jobs.models import (
    DocumentJobStage,
    DocumentJobStatus,
    DocumentJobTranslationQaStatus,
)
from app.domains.document_jobs.service import DOCUMENT_JOB_LIST_SORTS
from app.domains.document_jobs.workflow import DOCUMENT_JOB_STATUS_GROUPS
from app.domains.saved_views.models import SAVED_VIEW_PAGE_KEYS, SavedViewPageKey, SavedViewRecord
from app.domains.saved_views.repository import SavedViewRepositoryProtocol, SavedViewScope
from app.domains.resources.models import utc_now
from app.services.auth.models import AuthenticatedUser


SAVED_VIEW_MAX_PER_PAGE = 20
SAVED_VIEW_NAME_MAX_LENGTH = 64
_WHITESPACE_RE = re.compile(r"\s+")
_SAVED_VIEW_PAGE_PERMISSIONS: dict[SavedViewPageKey, str] = {
    "jobs": "document_jobs:read",
    "translation_qa": "translation_qa:read",
    "incidents": "document_jobs:read",
}


FilterValidator = Callable[[Any], Any]


@dataclass(frozen=True, slots=True)
class SavedViewPageSpec:
    """Validation contract for one saved-view-capable page."""

    allowed_filters: dict[str, FilterValidator]
    allowed_sorts: set[str]


class SavedViewService:
    """Apply personal saved-view invariants before persistence."""

    def __init__(self, repository: SavedViewRepositoryProtocol) -> None:
        self.repository = repository

    def list_views(self, *, user: AuthenticatedUser, page_key: SavedViewPageKey) -> list[SavedViewRecord]:
        """Return current user's personal views for one page."""

        self._ensure_supported_page(page_key)
        self._ensure_page_access(user, page_key)
        return self._ordered(self.repository.list_saved_views(self._scope(user), page_key))

    def create_view(
        self,
        *,
        user: AuthenticatedUser,
        page_key: SavedViewPageKey,
        name: str,
        filters: dict[str, Any],
        sort: str,
        is_default: bool = False,
        position: int | None = None,
    ) -> SavedViewRecord:
        """Create one personal saved view and normalize page ordering/defaults."""

        self._ensure_supported_page(page_key)
        self._ensure_page_access(user, page_key)
        scope = self._scope(user)
        current = self._ordered(self.repository.list_saved_views(scope, page_key))
        if len(current) >= SAVED_VIEW_MAX_PER_PAGE:
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "当前页面个人视图数量已达上限。")
        normalized_name = self._normalize_name(name)
        self._ensure_unique_name(current, normalized_name)
        normalized_filters, normalized_sort = self._validate_state(page_key, filters, sort)
        now = utc_now()
        record = SavedViewRecord(
            view_id=f"savedview_{uuid4().hex[:12]}",
            tenant_id=user.tenant_id,
            company_id=user.company_id,
            owner_user_id=user.id,
            page_key=page_key,
            name=normalized_name,
            filters=normalized_filters,
            sort=normalized_sort,
            is_default=is_default,
            position=position if position is not None else len(current),
            created_at=now,
            updated_at=now,
        )
        next_records = list(current)
        insert_at = self._bounded_position(record.position, len(next_records))
        next_records.insert(insert_at, record)
        preferred_default_view_id = record.view_id if record.is_default else None
        return self._persist_and_get(scope, page_key, next_records, record.view_id, preferred_default_view_id)

    def update_view(
        self,
        *,
        user: AuthenticatedUser,
        view_id: str,
        name: str | None = None,
        filters: dict[str, Any] | None = None,
        sort: str | None = None,
        is_default: bool | None = None,
        position: int | None = None,
    ) -> SavedViewRecord:
        """Patch a personal view without allowing ownership or page-key changes."""

        scope = self._scope(user)
        existing = self._find_owned(scope, view_id)
        self._ensure_page_access(user, existing.page_key)
        current = self._ordered(self.repository.list_saved_views(scope, existing.page_key))
        target_index = self._index_of(current, view_id)
        target = current[target_index]
        next_name = self._normalize_name(name) if name is not None else target.name
        self._ensure_unique_name(current, next_name, ignore_view_id=view_id)
        next_filters = filters if filters is not None else target.filters
        next_sort = sort if sort is not None else target.sort
        normalized_filters, normalized_sort = self._validate_state(existing.page_key, next_filters, next_sort)
        updated = target.model_copy(
            update={
                "name": next_name,
                "filters": normalized_filters,
                "sort": normalized_sort,
                "is_default": target.is_default if is_default is None else is_default,
                "position": target.position if position is None else position,
                "updated_at": utc_now(),
            }
        )
        next_records = [record for record in current if record.view_id != view_id]
        insert_at = target_index if position is None else self._bounded_position(position, len(next_records))
        next_records.insert(insert_at, SavedViewRecord.model_validate(updated.model_dump(mode="python")))
        preferred_default_view_id = view_id if updated.is_default else None
        return self._persist_and_get(scope, existing.page_key, next_records, view_id, preferred_default_view_id)

    def delete_view(self, *, user: AuthenticatedUser, view_id: str) -> None:
        """Delete one personal saved view owned by the current user."""

        scope = self._scope(user)
        existing = self._find_owned(scope, view_id)
        self._ensure_page_access(user, existing.page_key)
        current = self._ordered(self.repository.list_saved_views(scope, existing.page_key))
        next_records = [record for record in current if record.view_id != view_id]
        self.repository.replace_saved_views_for_page(scope, existing.page_key, self._normalize_positions(next_records))

    def reorder_views(
        self,
        *,
        user: AuthenticatedUser,
        page_key: SavedViewPageKey,
        view_ids: list[str],
    ) -> list[SavedViewRecord]:
        """Replace the position order for all personal views on one page."""

        self._ensure_supported_page(page_key)
        self._ensure_page_access(user, page_key)
        if len(view_ids) != len(set(view_ids)):
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "view_ids 不能重复。")
        scope = self._scope(user)
        current = self._ordered(self.repository.list_saved_views(scope, page_key))
        by_id = {record.view_id: record for record in current}
        if set(view_ids) != set(by_id):
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "reorder 必须提交当前页面完整个人视图 ID。")
        reordered = [by_id[view_id].model_copy(update={"updated_at": utc_now()}) for view_id in view_ids]
        return self.repository.replace_saved_views_for_page(scope, page_key, self._normalize_positions(reordered))

    def _scope(self, user: AuthenticatedUser) -> SavedViewScope:
        return SavedViewScope(
            tenant_id=user.tenant_id,
            company_id=user.company_id,
            owner_user_id=user.id,
        )

    def _find_owned(self, scope: SavedViewScope, view_id: str) -> SavedViewRecord:
        normalized_view_id = view_id.strip()
        if not normalized_view_id:
            raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", "saved view 不存在。")
        for record in self.repository.list_all_saved_views(scope):
            if record.view_id == normalized_view_id:
                return record
        raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", "saved view 不存在。")

    def _persist_and_get(
        self,
        scope: SavedViewScope,
        page_key: SavedViewPageKey,
        records: list[SavedViewRecord],
        view_id: str,
        preferred_default_view_id: str | None = None,
    ) -> SavedViewRecord:
        normalized = self._normalize_default(self._normalize_positions(records), preferred_default_view_id)
        persisted = self.repository.replace_saved_views_for_page(scope, page_key, normalized)
        return next(record for record in persisted if record.view_id == view_id)

    def _ordered(self, records: list[SavedViewRecord]) -> list[SavedViewRecord]:
        return sorted(records, key=lambda item: (item.position, item.created_at, item.view_id))

    def _normalize_positions(self, records: list[SavedViewRecord]) -> list[SavedViewRecord]:
        return [
            SavedViewRecord.model_validate(record.model_copy(update={"position": index}).model_dump(mode="python"))
            for index, record in enumerate(records)
        ]

    def _normalize_default(
        self,
        records: list[SavedViewRecord],
        preferred_default_view_id: str | None = None,
    ) -> list[SavedViewRecord]:
        preferred_exists = any(
            record.view_id == preferred_default_view_id and record.is_default for record in records
        )
        default_seen = False
        normalized: list[SavedViewRecord] = []
        for record in records:
            keep_default = record.is_default and (
                (preferred_exists and record.view_id == preferred_default_view_id)
                or (not preferred_exists and not default_seen)
            )
            if keep_default:
                default_seen = True
                normalized.append(record)
                continue
            if record.is_default:
                normalized.append(
                    SavedViewRecord.model_validate(record.model_copy(update={"is_default": False}).model_dump(mode="python"))
                )
                continue
            normalized.append(record)
        return normalized

    def _bounded_position(self, position: int, length: int) -> int:
        return min(max(position, 0), length)

    def _index_of(self, records: list[SavedViewRecord], view_id: str) -> int:
        for index, record in enumerate(records):
            if record.view_id == view_id:
                return index
        raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", "saved view 不存在。")

    def _ensure_supported_page(self, page_key: str) -> None:
        if page_key not in SAVED_VIEW_PAGE_KEYS:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "page_key 不支持。")

    def _ensure_page_access(self, user: AuthenticatedUser, page_key: SavedViewPageKey) -> None:
        required_permission = _SAVED_VIEW_PAGE_PERMISSIONS[page_key]
        if required_permission not in set(user.token_scopes):
            raise ApiError(status.HTTP_403_FORBIDDEN, "role_forbidden", "当前角色无权限访问该页面。")

    def _normalize_name(self, name: str) -> str:
        normalized = _WHITESPACE_RE.sub(" ", name.strip())
        if not normalized:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "saved view 名称不能为空。")
        if len(normalized) > SAVED_VIEW_NAME_MAX_LENGTH:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "saved view 名称过长。")
        return normalized

    def _ensure_unique_name(
        self,
        records: list[SavedViewRecord],
        name: str,
        *,
        ignore_view_id: str | None = None,
    ) -> None:
        normalized = name.casefold()
        for record in records:
            if record.view_id == ignore_view_id:
                continue
            if record.name.casefold() == normalized:
                raise ApiError(status.HTTP_409_CONFLICT, "conflict", "同一页面下 saved view 名称已存在。")

    def _validate_state(
        self,
        page_key: SavedViewPageKey,
        filters: dict[str, Any],
        sort: str,
    ) -> tuple[dict[str, Any], str]:
        spec = _PAGE_SPECS[page_key]
        if sort not in spec.allowed_sorts:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "sort 查询参数非法。")
        if not isinstance(filters, dict):
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "filters 必须是 JSON object。")
        if "sort" in filters:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "sort 必须作为顶层字段保存。")
        normalized: dict[str, Any] = {}
        for key, value in filters.items():
            validator = spec.allowed_filters.get(key)
            if validator is None:
                raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", f"filters.{key} 不允许保存。")
            normalized_value = validator(value)
            if normalized_value is not None:
                normalized[key] = normalized_value
        self._validate_cross_field(page_key, normalized)
        return normalized, sort

    def _validate_cross_field(self, page_key: SavedViewPageKey, filters: dict[str, Any]) -> None:
        if page_key == "jobs" and filters.get("status") and filters.get("status_group"):
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "status 与 status_group 不能同时保存。")
        created_from = filters.get("created_from")
        created_to = filters.get("created_to")
        if page_key == "jobs" and isinstance(created_from, str) and isinstance(created_to, str):
            if _parse_datetime(created_from) > _parse_datetime(created_to):
                raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "created_from 不能晚于 created_to。")


def _string_enum(values: set[str], field_name: str, *, trim: bool = True) -> FilterValidator:
    def validate(value: Any) -> str | None:
        if value is None:
            return None
        normalized = value.strip() if trim and isinstance(value, str) else value
        if not isinstance(normalized, str) or normalized not in values:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", f"{field_name} 查询参数非法。")
        return normalized

    return validate


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "字符串筛选值非法。")
    normalized = value.strip()
    return normalized or None


def _boolean(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "布尔筛选值非法。")


def _positive_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "正整数筛选值非法。")
    return value


def _datetime_string(value: Any) -> str | None:
    normalized = _optional_string(value)
    if normalized is None:
        return None
    _parse_datetime(normalized)
    return normalized


def _parse_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "日期筛选值必须是 ISO datetime。") from exc


_DOCUMENT_JOB_STATUSES = set(get_args(DocumentJobStatus))
_DOCUMENT_JOB_STAGES = set(get_args(DocumentJobStage))
_TRANSLATION_QA_STATUSES = set(get_args(DocumentJobTranslationQaStatus))
_TRANSLATION_QA_FILTERS = _TRANSLATION_QA_STATUSES | {"all"}


_PAGE_SPECS: dict[SavedViewPageKey, SavedViewPageSpec] = {
    "jobs": SavedViewPageSpec(
        allowed_filters={
            "status": _string_enum(_DOCUMENT_JOB_STATUSES, "status"),
            "status_group": _string_enum(set(DOCUMENT_JOB_STATUS_GROUPS), "status_group"),
            "translation_qa_status": _string_enum(_TRANSLATION_QA_FILTERS, "translation_qa_status"),
            "q": _optional_string,
            "include_archived": _boolean,
            "created_from": _datetime_string,
            "created_to": _datetime_string,
        },
        allowed_sorts=set(DOCUMENT_JOB_LIST_SORTS),
    ),
    "translation_qa": SavedViewPageSpec(
        allowed_filters={
            "translation_qa_status": _string_enum(_TRANSLATION_QA_FILTERS, "translation_qa_status"),
            "status": _string_enum(_DOCUMENT_JOB_STATUSES, "status"),
            "q": _optional_string,
            "include_archived": _boolean,
        },
        allowed_sorts=set(DOCUMENT_JOB_LIST_SORTS),
    ),
    "incidents": SavedViewPageSpec(
        allowed_filters={
            "status": _string_enum(_DOCUMENT_JOB_STATUSES, "status"),
            "stage": _string_enum(_DOCUMENT_JOB_STAGES, "stage"),
            "failure_type": _string_enum(DOCUMENT_JOB_INCIDENT_FAILURE_TYPES, "failure_type"),
            "retryable": _boolean,
            "retry_count": _string_enum(DOCUMENT_JOB_INCIDENT_RETRY_BUCKETS, "retry_count"),
            "stalled_minutes": _positive_int,
            "q": _optional_string,
        },
        allowed_sorts=set(DOCUMENT_JOB_INCIDENT_SORTS),
    ),
}
