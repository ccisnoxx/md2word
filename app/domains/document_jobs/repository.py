from __future__ import annotations

# app/domains/document_jobs/repository.py: 定义 document_jobs domain 依赖的持久化端口。

from typing import Any, Protocol

from app.domains.document_jobs.models import (
    DocumentJobCallbackMessage,
    DocumentJobEventRecord,
    DocumentJobRecord,
    DocumentJobTranslationBatchRecord,
)


class DocumentJobRepositoryProtocol(Protocol):
    """document_jobs metadata 读写合同。"""

    def create_document_job(self, record: DocumentJobRecord) -> DocumentJobRecord: ...
    def get_document_job(self, job_id: str) -> DocumentJobRecord | None: ...
    def list_document_jobs(self) -> list[DocumentJobRecord]: ...
    def update_document_job(self, job_id: str, **patch: Any) -> DocumentJobRecord: ...
    def update_document_job_if_current(
        self,
        job_id: str,
        *,
        allowed_statuses: set[str],
        allowed_stages: set[str],
        expected_retry_count: int | None = None,
        **patch: Any,
    ) -> DocumentJobRecord | None: ...


class DocumentJobEventRepositoryProtocol(Protocol):
    """document_jobs 事件读写合同。"""

    def append_document_job_event(self, job_id: str, event: DocumentJobEventRecord) -> None: ...
    def list_document_job_events(self, job_id: str) -> list[DocumentJobEventRecord]: ...


class DocumentJobCallbackMessageStoreProtocol(Protocol):
    """document_jobs MinerU callback 专用消息合同。"""

    def put_or_get_callback_message(self, message: DocumentJobCallbackMessage) -> tuple[DocumentJobCallbackMessage, bool]: ...
    def get_callback_message(self, message_id: str) -> DocumentJobCallbackMessage | None: ...
    def list_callback_messages(
        self,
        job_id: str | None = None,
        *,
        statuses: set[str] | None = None,
        limit: int | None = None,
    ) -> list[DocumentJobCallbackMessage]: ...
    def list_replayable_callback_messages(self, job_id: str | None = None) -> list[DocumentJobCallbackMessage]: ...
    def mark_callback_message_running(
        self,
        message_id: str,
        *,
        attempts: int,
        lease_owner: str | None,
        leased_at: Any,
        lease_expires_at: Any,
        updated_at: Any,
    ) -> DocumentJobCallbackMessage | None: ...
    def mark_callback_message_processed(self, message_id: str, *, updated_at: Any) -> DocumentJobCallbackMessage: ...
    def mark_callback_message_failed(
        self,
        message_id: str,
        *,
        error_code: str,
        error_message: str,
        updated_at: Any,
    ) -> DocumentJobCallbackMessage: ...
    def mark_callback_message_ignored(
        self,
        message_id: str,
        *,
        error_code: str,
        error_message: str,
        updated_at: Any,
    ) -> DocumentJobCallbackMessage: ...
    def count_callback_messages_by_status(self, job_id: str | None = None) -> dict[str, int]: ...


class DocumentJobTranslationBatchRepositoryProtocol(Protocol):
    """Provider translation batch metadata contract."""

    def create_translation_batch(self, record: DocumentJobTranslationBatchRecord) -> DocumentJobTranslationBatchRecord: ...
    def get_translation_batch(self, batch_id: str) -> DocumentJobTranslationBatchRecord | None: ...
    def list_translation_batches(
        self,
        job_id: str,
        *,
        generation: int | None = None,
    ) -> list[DocumentJobTranslationBatchRecord]: ...
    def update_translation_batch(self, batch_id: str, **patch: Any) -> DocumentJobTranslationBatchRecord: ...
    def update_translation_batch_if_current(
        self,
        batch_id: str,
        *,
        allowed_statuses: set[str],
        expected_generation: int,
        **patch: Any,
    ) -> DocumentJobTranslationBatchRecord | None: ...
