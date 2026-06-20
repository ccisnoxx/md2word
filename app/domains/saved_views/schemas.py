"""API request and response schemas for saved_views."""

from __future__ import annotations

# File: app/domains/saved_views/schemas.py
# Purpose: Define saved_views API request and response schemas.

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.domains.saved_views.models import SavedViewPageKey


class SavedViewResponse(BaseModel):
    view_id: str
    tenant_id: str
    company_id: str
    owner_user_id: str
    page_key: SavedViewPageKey
    name: str
    filters: dict[str, Any] = Field(default_factory=dict)
    sort: str
    is_default: bool
    position: int
    created_at: datetime
    updated_at: datetime


class SavedViewListResponse(BaseModel):
    items: list[SavedViewResponse]


class SavedViewCreateRequest(BaseModel):
    page_key: SavedViewPageKey
    name: str
    filters: dict[str, Any] = Field(default_factory=dict)
    sort: str
    is_default: bool = False
    position: int | None = Field(default=None, ge=0)


class SavedViewUpdateRequest(BaseModel):
    name: str | None = None
    filters: dict[str, Any] | None = None
    sort: str | None = None
    is_default: bool | None = None
    position: int | None = Field(default=None, ge=0)


class SavedViewReorderRequest(BaseModel):
    page_key: SavedViewPageKey
    view_ids: list[str]
