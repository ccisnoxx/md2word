from __future__ import annotations

# app/infrastructure/persistence/file/files.py: file backend 的 job files 和 document files adapter。

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from app.domains.jobs.models import JobFile
from app.domains.files.models import DocumentFileRecord
from app.infrastructure.persistence.file.backend import FilePersistenceBackend
from app.domains.files.result_registration import (
    expired_file, materialized_file, patched_file, ensure_file_mutation_allowed,
    reserved_file_deletion, finished_file_deletion, ensure_new_file_identity, ensure_result_descriptor_matches,
)
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
        with self.backend.publication_lifecycle_lock(), record_lock(self.backend.document_files_dir / f"{file_id}.lock"):
            yield None, self.get_document_file(file_id)

    def _write_file(self, connection: Any, record: DocumentFileRecord, *, create: bool = False) -> None:
        self.backend.write_json(self.backend.document_files_dir / f"{record.id}.json", record.model_dump(mode="json"))

    def is_document_file_protected(self, file_id: str) -> bool:
        return any(file_id in record.protected_file_ids for record in self.backend.list_publication_records())

    def _is_protected(self, connection: Any, file_id: str) -> bool:
        return any(file_id in record.protected_file_ids for record in self.backend.list_publication_records())

    def create_document_file(self, record: DocumentFileRecord) -> DocumentFileRecord:
        with self._locked_file(record.id) as (connection, existing):
            if existing is not None:
                if existing != record:
                    raise ValueError("文件 ID 已存在，不能覆盖生命周期或证据。")
                return existing
            ensure_new_file_identity(record)
            record = record.model_copy(update={"review_source_revision": 0})
            self._write_file(connection, record, create=True)
            return record

    def get_document_file(self, file_id: str) -> DocumentFileRecord | None:
        path = self.backend.document_files_dir / f"{file_id}.json"
        if not path.exists():
            return None
        record = DocumentFileRecord.model_validate(self.backend.read_json(path, {}))
        if record.id != file_id:
            raise ValueError("文件寻址与 payload 的 id 不一致。")
        return record

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
            if any(getattr(updated, key) != getattr(existing, key) for key in ("object_key", "storage_provider", "bucket")):
                ensure_new_file_identity(updated)
            ensure_file_mutation_allowed(existing, updated, protected=self._is_protected(connection, file_id))
            self._write_file(connection, updated)
            return updated

    def materialize_prepared_result(self, descriptor: DocumentFileRecord) -> DocumentFileRecord:
        with self._locked_file(descriptor.id) as (connection, existing):
            if existing is None:
                raise FileNotFoundError(f"结果候选不存在: {descriptor.id}")
            if self._is_protected(connection, descriptor.id):
                ensure_result_descriptor_matches(existing, descriptor)
                return existing
            updated = materialized_file(existing, descriptor)
            ensure_file_mutation_allowed(existing, updated, protected=False)
            self._write_file(connection, updated)
            return updated

    def expire_document_file(self, file_id: str, *, now: datetime) -> DocumentFileRecord:
        with self._locked_file(file_id) as (connection, existing):
            if existing is None:
                raise FileNotFoundError(f"文件不存在: {file_id}")
            if self._is_protected(connection, file_id) or existing.deletion_claim is not None:
                return existing
            updated = expired_file(existing, now=now)
            self._write_file(connection, updated)
            return updated

    def reserve_document_file_deletion(self, file_id: str, *, claim_id: str, now: datetime) -> DocumentFileRecord:
        with self._locked_file(file_id) as (connection, existing):
            if existing is None:
                raise FileNotFoundError(f"文件不存在: {file_id}")
            if self._is_protected(connection, file_id):
                raise ValueError("文件被不可变发布记录引用，不能删除。")
            updated = reserved_file_deletion(existing, claim_id=claim_id, now=now)
            self._write_file(connection, updated)
            return updated

    def finish_document_file_deletion(self, file_id: str, *, claim_id: str, now: datetime) -> DocumentFileRecord:
        with self._locked_file(file_id) as (connection, existing):
            if existing is None:
                raise FileNotFoundError(f"文件不存在: {file_id}")
            if self._is_protected(connection, file_id):
                raise ValueError("文件被不可变发布记录引用，不能删除。")
            updated = finished_file_deletion(existing, claim_id=claim_id, now=now)
            self._write_file(connection, updated)
            return updated
