from __future__ import annotations

# app/infrastructure/persistence/file/files.py: file backend 的 job files 和 document files adapter。

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from app.domains.jobs.models import JobFile
from app.domains.files.models import DocumentFileRecord
from app.infrastructure.persistence.file.backend import FilePersistenceBackend
from app.domains.files.result_registration import expired_file, materialized_file, patched_file
from app.infrastructure.persistence.file.record_lock import record_lock


class FileJobFileRepository:
    """用 file backend 读写 JobFile artifact metadata。"""

    def __init__(self, backend: FilePersistenceBackend) -> None:
        self.backend = backend

    def upsert_file(self, job_id: str, file: JobFile) -> None:
        path = self.backend.job_paths(job_id).files_json
        existing = [
            JobFile.model_validate(item)
            for item in self.backend.read_json(path, [])
        ]
        kept = [item for item in existing if item.file_type != file.file_type]
        kept.append(file)
        self.backend.write_json(path, [item.model_dump(mode="json") for item in kept])

    def list_files(self, job_id: str) -> list[JobFile]:
        path = self.backend.job_paths(job_id).files_json
        return [JobFile.model_validate(item) for item in self.backend.read_json(path, [])]


class FileDocumentFileRepository:
    """在同一文件序列化点维护候选身份、物化和不可逆生命周期。"""

    def __init__(self, backend: FilePersistenceBackend) -> None:
        self.backend = backend

    @contextmanager
    def _locked_file(self, file_id: str) -> Iterator[tuple[Any, DocumentFileRecord | None]]:
        with record_lock(self.backend.document_files_dir / f"{file_id}.lock"):
            yield None, self.get_document_file(file_id)

    def _write_file(self, connection: Any, record: DocumentFileRecord, *, create: bool = False) -> None:
        self.backend.write_json(self.backend.document_files_dir / f"{record.id}.json", record.model_dump(mode="json"))

    def create_document_file(self, record: DocumentFileRecord) -> DocumentFileRecord:
        with self._locked_file(record.id) as (connection, existing):
            if existing is not None:
                if existing != record:
                    raise ValueError("文件 ID 已存在，不能覆盖生命周期或证据。")
                return existing
            self._write_file(connection, record, create=True)
            return record

    def get_document_file(self, file_id: str) -> DocumentFileRecord | None:
        path = self.backend.document_files_dir / f"{file_id}.json"
        if not path.exists():
            return None
        return DocumentFileRecord.model_validate(self.backend.read_json(path, {}))

    def list_document_files(self) -> list[DocumentFileRecord]:
        records: list[DocumentFileRecord] = []
        for path in sorted(self.backend.document_files_dir.glob("*.json")):
            records.append(DocumentFileRecord.model_validate(self.backend.read_json(path, {})))
        return sorted(records, key=lambda record: (record.created_at, record.id))

    def update_document_file(self, file_id: str, **patch: Any) -> DocumentFileRecord:
        with self._locked_file(file_id) as (connection, existing):
            if existing is None:
                raise FileNotFoundError(f"文件不存在: {file_id}")
            updated = patched_file(existing, patch)
            self._write_file(connection, updated)
            return updated

    def materialize_prepared_result(self, descriptor: DocumentFileRecord) -> DocumentFileRecord:
        with self._locked_file(descriptor.id) as (connection, existing):
            if existing is None:
                raise FileNotFoundError(f"结果候选不存在: {descriptor.id}")
            updated = materialized_file(existing, descriptor)
            self._write_file(connection, updated)
            return updated

    def expire_document_file(self, file_id: str, *, now: datetime) -> DocumentFileRecord:
        with self._locked_file(file_id) as (connection, existing):
            if existing is None:
                raise FileNotFoundError(f"文件不存在: {file_id}")
            updated = expired_file(existing, now=now)
            self._write_file(connection, updated)
            return updated
