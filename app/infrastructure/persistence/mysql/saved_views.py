"""MySQL persistence adapter for personal saved views."""

from __future__ import annotations

# File: app/infrastructure/persistence/mysql/saved_views.py
# Purpose: Persist personal saved views in MySQL metadata storage.

from typing import Any

from app.domains.saved_views.models import SavedViewPageKey, SavedViewRecord
from app.domains.saved_views.repository import SavedViewScope
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend


class MysqlSavedViewRepository:
    """Read and replace personal saved views in MySQL."""

    def __init__(self, backend: MysqlPersistenceBackend) -> None:
        self.backend = backend

    def list_saved_views(self, scope: SavedViewScope, page_key: SavedViewPageKey) -> list[SavedViewRecord]:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT payload FROM saved_views
                    WHERE tenant_id = %s AND company_id = %s AND owner_user_id = %s AND page_key = %s
                    ORDER BY position, created_at, view_id
                    """,
                    (scope.tenant_id, scope.company_id, scope.owner_user_id, page_key),
                )
                rows = cursor.fetchall()
        return [SavedViewRecord.model_validate_json(row["payload"]) for row in rows]

    def list_all_saved_views(self, scope: SavedViewScope) -> list[SavedViewRecord]:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT payload FROM saved_views
                    WHERE tenant_id = %s AND company_id = %s AND owner_user_id = %s
                    ORDER BY page_key, position, created_at, view_id
                    """,
                    (scope.tenant_id, scope.company_id, scope.owner_user_id),
                )
                rows = cursor.fetchall()
        return [SavedViewRecord.model_validate_json(row["payload"]) for row in rows]

    def replace_saved_views_for_page(
        self,
        scope: SavedViewScope,
        page_key: SavedViewPageKey,
        records: list[SavedViewRecord],
    ) -> list[SavedViewRecord]:
        ordered = sorted(records, key=lambda record: (record.position, record.created_at, record.view_id))
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM saved_views
                    WHERE tenant_id = %s AND company_id = %s AND owner_user_id = %s AND page_key = %s
                    """,
                    (scope.tenant_id, scope.company_id, scope.owner_user_id, page_key),
                )
                for record in ordered:
                    self._insert(cursor, record)
        return ordered

    def _insert(self, cursor: Any, record: SavedViewRecord) -> None:
        cursor.execute(
            """
            INSERT INTO saved_views
                (view_id, tenant_id, company_id, owner_user_id, page_key, position, is_default, payload, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                record.view_id,
                record.tenant_id,
                record.company_id,
                record.owner_user_id,
                record.page_key,
                record.position,
                1 if record.is_default else 0,
                self.backend.dump_payload(record),
                record.created_at.isoformat(),
                record.updated_at.isoformat(),
            ),
        )
