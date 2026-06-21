"""File-backed persistence adapter for Acceptance Center runs."""

from __future__ import annotations

# File: app/infrastructure/persistence/file/acceptance.py
# Purpose: Persist acceptance run metadata in the local file backend.

from app.domains.acceptance.models import AcceptanceRunRecord, AcceptanceRunStatus, AcceptanceRunTier
from app.infrastructure.persistence.file.backend import FilePersistenceBackend


class FileAcceptanceRunRepository:
    """Store Acceptance Center run metadata in one local JSON file."""

    def __init__(self, backend: FilePersistenceBackend) -> None:
        self.backend = backend
        self.path = backend.data_dir / "acceptance_runs.json"

    def list_acceptance_runs(
        self,
        *,
        tier: AcceptanceRunTier | None = None,
        status: AcceptanceRunStatus | None = None,
        limit: int | None = None,
    ) -> list[AcceptanceRunRecord]:
        records = self._read_all()
        if tier is not None:
            records = [record for record in records if record.tier == tier]
        if status is not None:
            records = [record for record in records if record.status == status]
        ordered = sorted(records, key=lambda record: (record.updated_at, record.id), reverse=True)
        return ordered[:limit] if limit is not None else ordered

    def get_acceptance_run(self, run_id: str) -> AcceptanceRunRecord | None:
        normalized_id = run_id.strip()
        return next((record for record in self._read_all() if record.id == normalized_id), None)

    def save_acceptance_run(self, run: AcceptanceRunRecord) -> AcceptanceRunRecord:
        records = self._read_all()
        replaced = False
        for index, record in enumerate(records):
            if record.id == run.id:
                records[index] = run
                replaced = True
                break
        if not replaced:
            records.append(run)
        self._write_all(records)
        return run

    def _read_all(self) -> list[AcceptanceRunRecord]:
        payload = self.backend.read_json(self.path, [])
        raw_runs = payload.get("runs") if isinstance(payload, dict) else payload
        if not isinstance(raw_runs, list):
            raise ValueError("acceptance_runs.json must contain a run list")
        return [AcceptanceRunRecord.model_validate(item) for item in raw_runs]

    def _write_all(self, records: list[AcceptanceRunRecord]) -> None:
        ordered = sorted(records, key=lambda record: record.id)
        self.backend.write_json(
            self.path,
            [record.model_dump(mode="json") for record in ordered],
        )
