"""MySQL persistence adapter for managed internal users."""

from __future__ import annotations

# File: app/infrastructure/persistence/mysql/internal_users.py
# Purpose: Persist managed internal users in MySQL metadata storage.

from typing import Any

from app.domains.users.models import InternalUserRecord, InternalUserRole, InternalUserStatus
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend


class MysqlInternalUserRepository:
    """Read and write managed internal users in MySQL."""

    def __init__(self, backend: MysqlPersistenceBackend) -> None:
        self.backend = backend

    def count_internal_users(self) -> int:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) AS count FROM internal_users")
                row = cursor.fetchone()
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
            clauses.append("role = %s")
            params.append(role)
        if status is not None:
            clauses.append("status = %s")
            params.append(status)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at, normalized_username, user_id"
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, tuple(params))
                rows = cursor.fetchall()
        return [InternalUserRecord.model_validate_json(row["payload"]) for row in rows]

    def get_internal_user(self, user_id: str) -> InternalUserRecord | None:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT payload FROM internal_users WHERE user_id = %s",
                    (user_id.strip(),),
                )
                row = cursor.fetchone()
        return InternalUserRecord.model_validate_json(row["payload"]) if row is not None else None

    def get_internal_user_by_username(self, normalized_username: str) -> InternalUserRecord | None:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT payload FROM internal_users WHERE normalized_username = %s",
                    (normalized_username.strip().lower(),),
                )
                row = cursor.fetchone()
        return InternalUserRecord.model_validate_json(row["payload"]) if row is not None else None

    def save_internal_user(self, user: InternalUserRecord) -> InternalUserRecord:
        existing = self.get_internal_user(user.id)
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                if existing is None:
                    self._insert(cursor, user)
                else:
                    self._update(cursor, user)
        return user

    def _insert(self, cursor: Any, user: InternalUserRecord) -> None:
        cursor.execute(
            """
            INSERT INTO internal_users
                (user_id, normalized_username, role, status, payload, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
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

    def _update(self, cursor: Any, user: InternalUserRecord) -> None:
        cursor.execute(
            """
            UPDATE internal_users
            SET normalized_username = %s,
                role = %s,
                status = %s,
                payload = %s,
                updated_at = %s
            WHERE user_id = %s
            """,
            (
                user.normalized_username,
                user.role,
                user.status,
                self.backend.dump_payload(user),
                user.updated_at.isoformat(),
                user.id,
            ),
        )
