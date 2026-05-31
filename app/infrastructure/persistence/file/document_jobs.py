from __future__ import annotations

# app/infrastructure/persistence/file/document_jobs.py: file backend 的 document_jobs adapter。

from typing import Any

from app.domains.document_jobs.models import DocumentJobEventRecord, DocumentJobRecord
from app.infrastructure.persistence.file.backend import FilePersistenceBackend


class FileDocumentJobRepository:
    """用 file backend 读写 DocumentJobRecord 主记录。"""

    def __init__(self, backend: FilePersistenceBackend) -> None:
        self.backend = backend

    def create_document_job(self, record: DocumentJobRecord) -> DocumentJobRecord:
        self.backend.write_json(
            self.backend.document_jobs_dir / record.id / "job.json",
            record.model_dump(mode="json"),
        )
        return record

    def get_document_job(self, job_id: str) -> DocumentJobRecord | None:
        path = self.backend.document_jobs_dir / job_id / "job.json"
        if not path.exists():
            return None
        return DocumentJobRecord.model_validate(self.backend.read_json(path, {}))

    def list_document_jobs(self) -> list[DocumentJobRecord]:
        records: list[DocumentJobRecord] = []
        for path in sorted(self.backend.document_jobs_dir.glob("*/job.json")):
            records.append(DocumentJobRecord.model_validate(self.backend.read_json(path, {})))
        return sorted(records, key=lambda record: (record.created_at, record.id))

    def update_document_job(self, job_id: str, **patch: Any) -> DocumentJobRecord:
        existing = self.get_document_job(job_id)
        if existing is None:
            raise FileNotFoundError(f"文档任务不存在: {job_id}")
        updated = DocumentJobRecord.model_validate(existing.model_copy(update=patch).model_dump(mode="python"))
        self.create_document_job(updated)
        return updated


class FileDocumentJobEventRepository:
    """用 file backend 追加和读取 document job 事件 JSONL。"""

    def __init__(self, backend: FilePersistenceBackend) -> None:
        self.backend = backend

    def append_document_job_event(self, job_id: str, event: DocumentJobEventRecord) -> None:
        self.backend.append_json_line(
            self.backend.document_jobs_dir / job_id / "events.jsonl",
            event.model_dump_json(),
        )

    def list_document_job_events(self, job_id: str) -> list[DocumentJobEventRecord]:
        path = self.backend.document_jobs_dir / job_id / "events.jsonl"
        return [
            DocumentJobEventRecord.model_validate_json(line)
            for line in self.backend.read_json_lines(path)
        ]
