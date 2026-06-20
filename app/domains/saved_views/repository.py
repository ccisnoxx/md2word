"""Persistence ports for saved_views domain storage."""

from __future__ import annotations

# File: app/domains/saved_views/repository.py
# Purpose: Define saved_views domain persistence ports.

from dataclasses import dataclass
from typing import Protocol

from app.domains.saved_views.models import SavedViewPageKey, SavedViewRecord


@dataclass(frozen=True, slots=True)
class SavedViewScope:
    """Repository scope for the current user's personal saved views."""

    tenant_id: str
    company_id: str
    owner_user_id: str


class SavedViewRepositoryProtocol(Protocol):
    """Persistence contract for personal saved views."""

    def list_saved_views(self, scope: SavedViewScope, page_key: SavedViewPageKey) -> list[SavedViewRecord]: ...
    def list_all_saved_views(self, scope: SavedViewScope) -> list[SavedViewRecord]: ...
    def replace_saved_views_for_page(
        self,
        scope: SavedViewScope,
        page_key: SavedViewPageKey,
        records: list[SavedViewRecord],
    ) -> list[SavedViewRecord]: ...
