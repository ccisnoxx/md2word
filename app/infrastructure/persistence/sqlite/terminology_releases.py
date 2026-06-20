"""SQLite persistence adapter for terminology governance releases."""

from __future__ import annotations

# File: app/infrastructure/persistence/sqlite/terminology_releases.py
# Purpose: Persist terminology governance releases in sqlite metadata storage.

import sqlite3

from app.domains.terminology.models import TerminologyReleaseRecord, TerminologyReleaseStatus
from app.infrastructure.persistence.sqlite.backend import SqlitePersistenceBackend


class SqliteTerminologyReleaseRepository:
    """Read and write terminology governance release records in sqlite."""

    def __init__(self, backend: SqlitePersistenceBackend) -> None:
        self.backend = backend

    def save_release(self, record: TerminologyReleaseRecord) -> TerminologyReleaseRecord:
        with self.backend.connect() as connection:
            self._upsert(connection, record)
        return record

    def get_release(self, release_id: str, version: str | None = None) -> TerminologyReleaseRecord | None:
        release_id = release_id.strip()
        version = version.strip() if version else None
        if version is not None:
            query = "SELECT payload FROM terminology_releases WHERE release_id = ? AND version = ?"
            params = (release_id, version)
        else:
            query = "SELECT payload FROM terminology_releases WHERE release_id = ? ORDER BY created_at DESC, version DESC LIMIT 1"
            params = (release_id,)
        with self.backend.connect() as connection:
            row = connection.execute(query, params).fetchone()
        return TerminologyReleaseRecord.model_validate_json(row["payload"]) if row is not None else None

    def list_releases(
        self,
        *,
        status: TerminologyReleaseStatus | None = None,
        project: str | None = None,
        language_pair: str | None = None,
        content_type: str | None = None,
    ) -> list[TerminologyReleaseRecord]:
        query = "SELECT payload FROM terminology_releases"
        clauses: list[str] = []
        params: list[str] = []
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if project is not None:
            clauses.append("project = ?")
            params.append(project)
        if language_pair is not None:
            clauses.append("language_pair = ?")
            params.append(language_pair)
        if content_type is not None:
            clauses.append("content_type = ?")
            params.append(content_type)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at, release_id, version"
        with self.backend.connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [TerminologyReleaseRecord.model_validate_json(row["payload"]) for row in rows]

    def _upsert(self, connection: sqlite3.Connection, record: TerminologyReleaseRecord) -> None:
        connection.execute(
            """
            INSERT INTO terminology_releases
                (release_id, version, status, project, language_pair, content_type, payload, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(release_id, version) DO UPDATE SET
                status = excluded.status,
                project = excluded.project,
                language_pair = excluded.language_pair,
                content_type = excluded.content_type,
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (
                record.id,
                record.version,
                record.status,
                record.scope.project,
                record.scope.language_pair,
                record.scope.content_type,
                self.backend.dump_payload(record),
                record.created_at.isoformat(),
                record.updated_at.isoformat(),
            ),
        )
