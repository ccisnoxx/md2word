from __future__ import annotations

# app/domains/document_jobs/repository.py: 定义 document_jobs domain 依赖的持久化端口。

from datetime import datetime
from typing import Any, Protocol

from app.domains.files.models import DocumentFileRecord

from app.domains.document_jobs.models import (
    DocumentJobCallbackMessage,
    DocumentJobEventRecord,
    DocumentJobRecord,
    DocumentJobReviewStatus,
    DocumentJobTranslationQaIssueType,
    DocumentJobTranslationBatchRecord,
)


class DocumentJobRepositoryProtocol(Protocol):
    """主记录元数据合同；所有写方法共享同 job 的局部序列化点。"""

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
        expected_document_ir_file_id: str | None = None,
        require_no_prepared_result: bool = False,
        expected_prepared_result_file_id: str | None = None,
        **patch: Any,
    ) -> DocumentJobRecord | None: ...

    def prepare_document_job_result(
        self, job_id: str, *, expected_retry_count: int,
        expected_document_ir_file_id: str, candidate: DocumentFileRecord,
    ) -> DocumentJobRecord | None: ...
    def retry_document_job(
        self, job_id: str, *, expected_retry_count: int, max_retries: int, **patch: Any,
    ) -> DocumentJobRecord | None: ...
    def update_document_job_review_if_current(
        self, job_id: str, *, expected_retry_count: int, expected_result_file_id: str | None,
        review_status: DocumentJobReviewStatus, issue_type: DocumentJobTranslationQaIssueType | None,
        note: str | None, reviewed_by: str | None, reviewed_at: datetime | None, updated_at: datetime,
    ) -> DocumentJobRecord | None: ...
    def backfill_document_job_state_if_missing(self, job_id: str) -> bool:
        """锁内重读 raw 并补缺，返回 payload 是否补键；SQL 同时校准投影列。"""
        ...


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
