from __future__ import annotations

# app/domains/document_jobs/repository.py: 定义 document_jobs domain 依赖的持久化端口。

from typing import Any, Protocol

from app.domains.document_jobs.models import DocumentJobEventRecord, DocumentJobRecord


class DocumentJobRepositoryProtocol(Protocol):
    """document_jobs metadata 读写合同。"""

    def create_document_job(self, record: DocumentJobRecord) -> DocumentJobRecord: ...
    def get_document_job(self, job_id: str) -> DocumentJobRecord | None: ...
    def list_document_jobs(self) -> list[DocumentJobRecord]: ...
    def update_document_job(self, job_id: str, **patch: Any) -> DocumentJobRecord: ...


class DocumentJobEventRepositoryProtocol(Protocol):
    """document_jobs 事件读写合同。"""

    def append_document_job_event(self, job_id: str, event: DocumentJobEventRecord) -> None: ...
    def list_document_job_events(self, job_id: str) -> list[DocumentJobEventRecord]: ...
