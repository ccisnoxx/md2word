"""MySQL persistence adapter for terminology governance releases."""

from __future__ import annotations

# File: app/infrastructure/persistence/mysql/terminology_releases.py
# Purpose: Persist terminology governance releases in MySQL metadata storage.

from typing import Any

from app.domains.terminology.models import TerminologyReleaseRecord, TerminologyReleaseStatus
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend


class MysqlTerminologyReleaseRepository:
    """Read and write terminology governance release records in MySQL."""

    def __init__(self, backend: MysqlPersistenceBackend) -> None:
        self.backend = backend

    def save_release(self, record: TerminologyReleaseRecord) -> TerminologyReleaseRecord:
        existing = self.get_release(record.id, record.version)
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                if existing is None:
                    self._insert(cursor, record)
                else:
                    self._update(cursor, record)
        return record

    def get_release(self, release_id: str, version: str | None = None) -> TerminologyReleaseRecord | None:
        release_id = release_id.strip()
        version = version.strip() if version else None
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                if version is not None:
                    cursor.execute(
                        "SELECT payload FROM terminology_releases WHERE release_id = %s AND version = %s",
                        (release_id, version),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT payload FROM terminology_releases
                        WHERE release_id = %s
                        ORDER BY created_at DESC, version DESC
                        LIMIT 1
                        """,
                        (release_id,),
                    )
                row = cursor.fetchone()
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
            clauses.append("status = %s")
            params.append(status)
        if project is not None:
            clauses.append("project = %s")
            params.append(project)
        if language_pair is not None:
            clauses.append("language_pair = %s")
            params.append(language_pair)
        if content_type is not None:
            clauses.append("content_type = %s")
            params.append(content_type)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at, release_id, version"
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, tuple(params))
                rows = cursor.fetchall()
        return [TerminologyReleaseRecord.model_validate_json(row["payload"]) for row in rows]

    def _insert(self, cursor: Any, record: TerminologyReleaseRecord) -> None:
        cursor.execute(
            """
            INSERT INTO terminology_releases
                (release_id, version, status, project, language_pair, content_type, payload, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            self._params(record),
        )

    def _update(self, cursor: Any, record: TerminologyReleaseRecord) -> None:
        cursor.execute(
            """
            UPDATE terminology_releases
            SET status = %s,
                project = %s,
                language_pair = %s,
                content_type = %s,
                payload = %s,
                updated_at = %s
            WHERE release_id = %s AND version = %s
            """,
            (
                record.status,
                record.scope.project,
                record.scope.language_pair,
                record.scope.content_type,
                self.backend.dump_payload(record),
                record.updated_at.isoformat(),
                record.id,
                record.version,
            ),
        )

    def _params(self, record: TerminologyReleaseRecord) -> tuple[str, ...]:
        return (
            record.id,
            record.version,
            record.status,
            record.scope.project,
            record.scope.language_pair,
            record.scope.content_type,
            self.backend.dump_payload(record),
            record.created_at.isoformat(),
            record.updated_at.isoformat(),
        )
