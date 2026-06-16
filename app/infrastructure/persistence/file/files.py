from __future__ import annotations

# app/infrastructure/persistence/file/files.py: file backend 的 job files 和 document files adapter。

from typing import Any

from app.domains.jobs.models import JobFile
from app.domains.files.models import DocumentFileRecord
from app.infrastructure.persistence.file.backend import FilePersistenceBackend


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
    """用 file backend 读写 document_files metadata。"""

    def __init__(self, backend: FilePersistenceBackend) -> None:
        self.backend = backend

    def create_document_file(self, record: DocumentFileRecord) -> DocumentFileRecord:
        self.backend.write_json(
            self.backend.document_files_dir / f"{record.id}.json",
            record.model_dump(mode="json"),
        )
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
        existing = self.get_document_file(file_id)
        if existing is None:
            raise FileNotFoundError(f"文件不存在: {file_id}")
        updated = existing.model_copy(update=patch)
        self.create_document_file(updated)
        return updated
