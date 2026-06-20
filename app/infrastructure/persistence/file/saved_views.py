"""File-backed persistence adapter for personal saved views."""

from __future__ import annotations

# File: app/infrastructure/persistence/file/saved_views.py
# Purpose: Persist personal saved views in the local file metadata backend.

from urllib.parse import quote

from app.domains.saved_views.models import SAVED_VIEW_PAGE_KEYS, SavedViewPageKey, SavedViewRecord
from app.domains.saved_views.repository import SavedViewScope
from app.infrastructure.persistence.file.backend import FilePersistenceBackend


class FileSavedViewRepository:
    """Use one JSON file per owner/page for file-backend saved views."""

    def __init__(self, backend: FilePersistenceBackend) -> None:
        self.backend = backend

    def list_saved_views(self, scope: SavedViewScope, page_key: SavedViewPageKey) -> list[SavedViewRecord]:
        return self._read_page(scope, page_key)

    def list_all_saved_views(self, scope: SavedViewScope) -> list[SavedViewRecord]:
        records: list[SavedViewRecord] = []
        for page_key in SAVED_VIEW_PAGE_KEYS:
            records.extend(self._read_page(scope, page_key))
        return records

    def replace_saved_views_for_page(
        self,
        scope: SavedViewScope,
        page_key: SavedViewPageKey,
        records: list[SavedViewRecord],
    ) -> list[SavedViewRecord]:
        ordered = sorted(records, key=lambda record: (record.position, record.created_at, record.view_id))
        self.backend.write_json(
            self._page_path(scope, page_key),
            [record.model_dump(mode="json") for record in ordered],
        )
        return ordered

    def _read_page(self, scope: SavedViewScope, page_key: SavedViewPageKey) -> list[SavedViewRecord]:
        payload = self.backend.read_json(self._page_path(scope, page_key), [])
        return sorted(
            [SavedViewRecord.model_validate(item) for item in payload],
            key=lambda record: (record.position, record.created_at, record.view_id),
        )

    def _page_path(self, scope: SavedViewScope, page_key: SavedViewPageKey):
        return (
            self.backend.saved_views_dir
            / _safe_part(scope.tenant_id)
            / _safe_part(scope.company_id)
            / _safe_part(scope.owner_user_id)
            / f"{page_key}.json"
        )


def _safe_part(value: str) -> str:
    return quote(value.strip() or "_", safe="")
