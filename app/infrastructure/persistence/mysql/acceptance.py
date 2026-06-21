"""MySQL persistence adapter for Acceptance Center runs."""

from __future__ import annotations

# File: app/infrastructure/persistence/mysql/acceptance.py
# Purpose: Persist acceptance run metadata in MySQL storage.

from typing import Any

from app.domains.acceptance.models import AcceptanceRunRecord, AcceptanceRunStatus, AcceptanceRunTier
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend


class MysqlAcceptanceRunRepository:
    """Read and write Acceptance Center run metadata in MySQL."""

    def __init__(self, backend: MysqlPersistenceBackend) -> None:
        self.backend = backend

    def list_acceptance_runs(
        self,
        *,
        tier: AcceptanceRunTier | None = None,
        status: AcceptanceRunStatus | None = None,
        limit: int | None = None,
    ) -> list[AcceptanceRunRecord]:
        query = "SELECT payload FROM acceptance_runs"
        clauses: list[str] = []
        params: list[str | int] = []
        if tier is not None:
            clauses.append("tier = %s")
            params.append(tier)
        if status is not None:
            clauses.append("status = %s")
            params.append(status)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY updated_at DESC, run_id DESC"
        if limit is not None:
            query += " LIMIT %s"
            params.append(limit)
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, tuple(params))
                rows = cursor.fetchall()
        return [AcceptanceRunRecord.model_validate_json(row["payload"]) for row in rows]

    def get_acceptance_run(self, run_id: str) -> AcceptanceRunRecord | None:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT payload FROM acceptance_runs WHERE run_id = %s",
                    (run_id.strip(),),
                )
                row = cursor.fetchone()
        return AcceptanceRunRecord.model_validate_json(row["payload"]) if row is not None else None

    def save_acceptance_run(self, run: AcceptanceRunRecord) -> AcceptanceRunRecord:
        existing = self.get_acceptance_run(run.id)
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                if existing is None:
                    self._insert(cursor, run)
                else:
                    self._update(cursor, run)
        return run

    def _insert(self, cursor: Any, run: AcceptanceRunRecord) -> None:
        cursor.execute(
            """
            INSERT INTO acceptance_runs
                (run_id, tier, status, decision, payload, started_at, finished_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                run.id,
                run.tier,
                run.status,
                run.decision,
                self.backend.dump_payload(run),
                run.started_at.isoformat() if run.started_at is not None else None,
                run.finished_at.isoformat() if run.finished_at is not None else None,
                run.updated_at.isoformat(),
            ),
        )

    def _update(self, cursor: Any, run: AcceptanceRunRecord) -> None:
        cursor.execute(
            """
            UPDATE acceptance_runs
            SET tier = %s,
                status = %s,
                decision = %s,
                payload = %s,
                started_at = %s,
                finished_at = %s,
                updated_at = %s
            WHERE run_id = %s
            """,
            (
                run.tier,
                run.status,
                run.decision,
                self.backend.dump_payload(run),
                run.started_at.isoformat() if run.started_at is not None else None,
                run.finished_at.isoformat() if run.finished_at is not None else None,
                run.updated_at.isoformat(),
                run.id,
            ),
        )
