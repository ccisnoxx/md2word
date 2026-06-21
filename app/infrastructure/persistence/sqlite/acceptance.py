"""SQLite persistence adapter for Acceptance Center runs."""

from __future__ import annotations

# File: app/infrastructure/persistence/sqlite/acceptance.py
# Purpose: Persist acceptance run metadata in sqlite storage.

import sqlite3

from app.domains.acceptance.models import AcceptanceRunRecord, AcceptanceRunStatus, AcceptanceRunTier
from app.infrastructure.persistence.sqlite.backend import SqlitePersistenceBackend


class SqliteAcceptanceRunRepository:
    """Read and write Acceptance Center run metadata in sqlite."""

    def __init__(self, backend: SqlitePersistenceBackend) -> None:
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
            clauses.append("tier = ?")
            params.append(tier)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY updated_at DESC, run_id DESC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        with self.backend.connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [AcceptanceRunRecord.model_validate_json(row["payload"]) for row in rows]

    def get_acceptance_run(self, run_id: str) -> AcceptanceRunRecord | None:
        with self.backend.connect() as connection:
            row = connection.execute(
                "SELECT payload FROM acceptance_runs WHERE run_id = ?",
                (run_id.strip(),),
            ).fetchone()
        return AcceptanceRunRecord.model_validate_json(row["payload"]) if row is not None else None

    def save_acceptance_run(self, run: AcceptanceRunRecord) -> AcceptanceRunRecord:
        with self.backend.connect() as connection:
            self._upsert(connection, run)
        return run

    def _upsert(self, connection: sqlite3.Connection, run: AcceptanceRunRecord) -> None:
        connection.execute(
            """
            INSERT INTO acceptance_runs
                (run_id, tier, status, decision, payload, started_at, finished_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                tier = excluded.tier,
                status = excluded.status,
                decision = excluded.decision,
                payload = excluded.payload,
                started_at = excluded.started_at,
                finished_at = excluded.finished_at,
                updated_at = excluded.updated_at
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
