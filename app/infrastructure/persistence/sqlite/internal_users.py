"""SQLite persistence adapter for managed internal users."""

from __future__ import annotations

# File: app/infrastructure/persistence/sqlite/internal_users.py
# Purpose: Persist managed internal users in sqlite metadata storage.

import sqlite3

from app.domains.users.models import InternalUserRecord, InternalUserRole, InternalUserStatus
from app.infrastructure.persistence.sqlite.backend import SqlitePersistenceBackend


class SqliteInternalUserRepository:
    """Read and write managed internal users in sqlite."""

    def __init__(self, backend: SqlitePersistenceBackend) -> None:
        self.backend = backend

    def count_internal_users(self) -> int:
        with self.backend.connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM internal_users").fetchone()
        return int(row["count"])

    def list_internal_users(
        self,
        *,
        role: InternalUserRole | None = None,
        status: InternalUserStatus | None = None,
    ) -> list[InternalUserRecord]:
        query = "SELECT payload FROM internal_users"
        clauses: list[str] = []
        params: list[str] = []
        if role is not None:
            clauses.append("role = ?")
            params.append(role)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at, normalized_username, user_id"
        with self.backend.connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [InternalUserRecord.model_validate_json(row["payload"]) for row in rows]

    def get_internal_user(self, user_id: str) -> InternalUserRecord | None:
        with self.backend.connect() as connection:
            row = connection.execute(
                "SELECT payload FROM internal_users WHERE user_id = ?",
                (user_id.strip(),),
            ).fetchone()
        return InternalUserRecord.model_validate_json(row["payload"]) if row is not None else None

    def get_internal_user_by_username(self, normalized_username: str) -> InternalUserRecord | None:
        with self.backend.connect() as connection:
            row = connection.execute(
                "SELECT payload FROM internal_users WHERE normalized_username = ?",
                (normalized_username.strip().lower(),),
            ).fetchone()
        return InternalUserRecord.model_validate_json(row["payload"]) if row is not None else None

    def save_internal_user(self, user: InternalUserRecord) -> InternalUserRecord:
        with self.backend.connect() as connection:
            self._upsert(connection, user)
        return user

    def _upsert(self, connection: sqlite3.Connection, user: InternalUserRecord) -> None:
        connection.execute(
            """
            INSERT INTO internal_users
                (user_id, normalized_username, role, status, payload, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                normalized_username = excluded.normalized_username,
                role = excluded.role,
                status = excluded.status,
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (
                user.id,
                user.normalized_username,
                user.role,
                user.status,
                self.backend.dump_payload(user),
                user.created_at.isoformat(),
                user.updated_at.isoformat(),
            ),
        )
