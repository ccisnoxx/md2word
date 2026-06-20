"""Persisted personal saved-view records for operations pages."""

from __future__ import annotations

# File: app/domains/saved_views/models.py
# Purpose: Define persisted personal saved-view records for operations pages.

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.domains.resources.models import utc_now


SavedViewPageKey = Literal["jobs", "translation_qa", "incidents"]
SAVED_VIEW_PAGE_KEYS: tuple[SavedViewPageKey, ...] = ("jobs", "translation_qa", "incidents")


class SavedViewRecord(BaseModel):
    """A personal reusable filter/sort state owned by one authenticated user."""

    view_id: str
    tenant_id: str
    company_id: str
    owner_user_id: str
    page_key: SavedViewPageKey
    name: str
    filters: dict[str, Any] = Field(default_factory=dict)
    sort: str
    is_default: bool = False
    position: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
