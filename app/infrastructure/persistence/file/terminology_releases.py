"""File-backed persistence adapter for terminology governance releases."""

from __future__ import annotations

# File: app/infrastructure/persistence/file/terminology_releases.py
# Purpose: Persist terminology governance releases in the local file metadata backend.

from app.domains.terminology.models import TerminologyReleaseRecord, TerminologyReleaseStatus
from app.infrastructure.persistence.file.backend import FilePersistenceBackend


class FileTerminologyReleaseRepository:
    """Store terminology governance release records in one local JSON metadata file."""

    def __init__(self, backend: FilePersistenceBackend) -> None:
        self.backend = backend
        self.path = backend.data_dir / "terminology_releases.json"

    def save_release(self, record: TerminologyReleaseRecord) -> TerminologyReleaseRecord:
        records = self._read_all()
        replaced = False
        for index, existing in enumerate(records):
            if existing.id == record.id and existing.version == record.version:
                records[index] = record
                replaced = True
                break
        if not replaced:
            records.append(record)
        self._write_all(records)
        return record

    def get_release(self, release_id: str, version: str | None = None) -> TerminologyReleaseRecord | None:
        release_id = release_id.strip()
        version = version.strip() if version else None
        matches = [record for record in self._read_all() if record.id == release_id]
        if version is not None:
            return next((record for record in matches if record.version == version), None)
        return matches[-1] if matches else None

    def list_releases(
        self,
        *,
        status: TerminologyReleaseStatus | None = None,
        project: str | None = None,
        language_pair: str | None = None,
        content_type: str | None = None,
    ) -> list[TerminologyReleaseRecord]:
        records = self._read_all()
        if status is not None:
            records = [record for record in records if record.status == status]
        if project is not None:
            records = [record for record in records if record.scope.project == project]
        if language_pair is not None:
            records = [record for record in records if record.scope.language_pair == language_pair]
        if content_type is not None:
            records = [record for record in records if record.scope.content_type == content_type]
        return records

    def _read_all(self) -> list[TerminologyReleaseRecord]:
        payload = self.backend.read_json(self.path, [])
        raw_releases = payload.get("releases") if isinstance(payload, dict) else payload
        if not isinstance(raw_releases, list):
            raise ValueError("terminology_releases.json must contain a release list")
        return sorted(
            [TerminologyReleaseRecord.model_validate(item) for item in raw_releases],
            key=lambda record: (record.created_at, record.id, record.version),
        )

    def _write_all(self, records: list[TerminologyReleaseRecord]) -> None:
        ordered = sorted(records, key=lambda record: (record.created_at, record.id, record.version))
        self.backend.write_json(
            self.path,
            [record.model_dump(mode="json") for record in ordered],
        )
