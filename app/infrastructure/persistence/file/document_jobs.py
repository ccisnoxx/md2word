from __future__ import annotations

# app/infrastructure/persistence/file/document_jobs.py: file backend 的 document_jobs adapter。

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from app.domains.document_jobs.models import (
    DocumentJobCallbackMessage,
    DocumentJobEventRecord,
    DocumentJobRecord,
    DocumentJobReviewStatus,
    DocumentJobTranslationQaIssueType,
    DocumentJobTranslationBatchRecord,
)
from app.domains.document_jobs.delivery_state import backfill_document_job_state_payload, reviewed_job
from app.infrastructure.persistence.file.backend import FilePersistenceBackend
from app.domains.document_jobs.result_state import matches_current, patched_job, prepare_result, retry_job
from app.domains.files.models import DocumentFileRecord
from app.domains.resources.models import utc_now
from app.infrastructure.persistence.file.record_lock import record_lock


class FileDocumentJobRepository:
    """同一主记录的全部写入共享短锁；对象 I/O 在调用方锁外进行。"""

    def __init__(self, backend: FilePersistenceBackend) -> None:
        self.backend = backend

    def create_document_job(self, record: DocumentJobRecord) -> DocumentJobRecord:
        with record_lock(self.backend.document_jobs_dir / record.id / "job.lock"):
            existing = self.get_document_job(record.id)
            if existing is not None:
                if existing != record:
                    raise ValueError("任务 ID 已存在，不能覆盖主记录。")
                return existing
            self._write_job(None, record)
            return record

    def _write_job(self, connection: Any, record: DocumentJobRecord) -> None:
        self.backend.write_json(self.backend.document_jobs_dir / record.id / "job.json", record.model_dump(mode="json"))

    @contextmanager
    def _locked_payload(self, job_id: str) -> Iterator[tuple[Any, Any]]:
        with record_lock(self.backend.document_jobs_dir / job_id / "job.lock"):
            path = self.backend.document_jobs_dir / job_id / "job.json"
            if not path.exists():
                raise FileNotFoundError(f"文档任务不存在: {job_id}")
            yield None, self.backend.read_json(path, {})

    @contextmanager
    def _locked_job(self, job_id: str) -> Iterator[tuple[Any, DocumentJobRecord]]:
        with self._locked_payload(job_id) as (connection, payload):
            yield connection, DocumentJobRecord.model_validate(payload)

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

    def update_document_job_if_current(
        self, job_id: str, *, allowed_statuses: set[str], allowed_stages: set[str],
        expected_retry_count: int | None = None, expected_document_ir_file_id: str | None = None,
        require_no_prepared_result: bool = False, expected_prepared_result_file_id: str | None = None,
        **patch: Any,
    ) -> DocumentJobRecord | None:
        with self._locked_job(job_id) as (connection, existing):
            if not matches_current(existing, allowed_statuses=allowed_statuses, allowed_stages=allowed_stages,
                                   expected_retry_count=expected_retry_count,
                                   expected_document_ir_file_id=expected_document_ir_file_id,
                                   require_no_prepared_result=require_no_prepared_result,
                                   expected_prepared_result_file_id=expected_prepared_result_file_id):
                return None
            if patch.get("status") == "succeeded" and existing.timeout_at is not None and existing.timeout_at <= utc_now():
                return None
            updated = patched_job(existing, patch)
            self._write_job(connection, updated)
            return updated

    def prepare_document_job_result(
        self, job_id: str, *, expected_retry_count: int, expected_document_ir_file_id: str,
        candidate: DocumentFileRecord,
    ) -> DocumentJobRecord | None:
        with self._locked_job(job_id) as (connection, existing):
            updated = prepare_result(existing, expected_retry_count=expected_retry_count,
                                     expected_document_ir_file_id=expected_document_ir_file_id, candidate=candidate)
            if updated is not None:
                self._write_job(connection, updated)
            return updated

    def retry_document_job(
        self, job_id: str, *, expected_retry_count: int, max_retries: int, **patch: Any,
    ) -> DocumentJobRecord | None:
        with self._locked_job(job_id) as (connection, existing):
            updated = retry_job(existing, expected_retry_count=expected_retry_count, max_retries=max_retries, **patch)
            if updated is not None:
                self._write_job(connection, updated)
            return updated

    def update_document_job(self, job_id: str, **patch: Any) -> DocumentJobRecord:
        with self._locked_job(job_id) as (connection, existing):
            updated = patched_job(existing, patch)
            self._write_job(connection, updated)
            return updated

    def update_document_job_review_if_current(
        self, job_id: str, *, expected_retry_count: int, expected_result_file_id: str | None,
        review_status: DocumentJobReviewStatus, issue_type: DocumentJobTranslationQaIssueType | None,
        note: str | None, reviewed_by: str | None, reviewed_at: datetime | None, updated_at: datetime,
    ) -> DocumentJobRecord | None:
        with self._locked_job(job_id) as (connection, existing):
            updated = reviewed_job(existing, expected_retry_count=expected_retry_count,
                expected_result_file_id=expected_result_file_id, review_status=review_status,
                issue_type=issue_type, note=note, reviewed_by=reviewed_by, reviewed_at=reviewed_at,
                updated_at=updated_at)
            if updated is not None:
                self._write_job(connection, updated)
            return updated

    def backfill_document_job_state_if_missing(self, job_id: str) -> bool:
        with self._locked_payload(job_id) as (_, payload):
            updated = backfill_document_job_state_payload(payload)
            changed = updated != payload
            if changed:
                self.backend.write_json(self.backend.document_jobs_dir / job_id / "job.json", updated)
            return changed


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


class FileDocumentJobCallbackMessageStore:
    """用 file backend 读写 document_jobs callback message。"""

    def __init__(self, backend: FilePersistenceBackend) -> None:
        self.backend = backend

    def put_or_get_callback_message(
        self,
        message: DocumentJobCallbackMessage,
    ) -> tuple[DocumentJobCallbackMessage, bool]:
        existing = self._get_by_dedupe_key(message.dedupe_key)
        if existing is not None:
            return existing, False
        self._write_message(message)
        return message, True

    def get_callback_message(self, message_id: str) -> DocumentJobCallbackMessage | None:
        path = self.backend.document_job_callback_messages_dir / f"{message_id}.json"
        if not path.exists():
            return None
        return DocumentJobCallbackMessage.model_validate(self.backend.read_json(path, {}))

    def list_callback_messages(
        self,
        job_id: str | None = None,
        *,
        statuses: set[str] | None = None,
        limit: int | None = None,
    ) -> list[DocumentJobCallbackMessage]:
        messages = [
            self._read_message(path)
            for path in sorted(self.backend.document_job_callback_messages_dir.glob("*.json"))
        ]
        filtered = [
            message
            for message in sorted(messages, key=lambda item: (item.created_at, item.id))
            if (job_id is None or message.job_id == job_id)
            and (statuses is None or message.status in statuses)
        ]
        if limit is not None:
            return filtered[:limit]
        return filtered

    def list_replayable_callback_messages(self, job_id: str | None = None) -> list[DocumentJobCallbackMessage]:
        return self.list_callback_messages(job_id, statuses={"pending", "running"})

    def mark_callback_message_running(
        self,
        message_id: str,
        *,
        attempts: int,
        lease_owner: str | None,
        leased_at: Any,
        lease_expires_at: Any,
        updated_at: Any,
    ) -> DocumentJobCallbackMessage | None:
        message = self.get_callback_message(message_id)
        if message is None:
            raise FileNotFoundError(f"document job callback message 不存在: {message_id}")
        if message.status not in {"pending", "running"}:
            return None
        return self._update_message(
            message,
            status="running",
            attempts=attempts,
            lease_owner=lease_owner,
            leased_at=leased_at,
            lease_expires_at=lease_expires_at,
            error_code=None,
            error_message=None,
            updated_at=updated_at,
        )

    def mark_callback_message_processed(self, message_id: str, *, updated_at: Any) -> DocumentJobCallbackMessage:
        return self._update_message_by_id(message_id, status="processed", updated_at=updated_at)

    def mark_callback_message_failed(
        self,
        message_id: str,
        *,
        error_code: str,
        error_message: str,
        updated_at: Any,
    ) -> DocumentJobCallbackMessage:
        return self._update_message_by_id(
            message_id,
            status="failed",
            error_code=error_code,
            error_message=error_message,
            lease_owner=None,
            leased_at=None,
            lease_expires_at=None,
            updated_at=updated_at,
        )

    def mark_callback_message_ignored(
        self,
        message_id: str,
        *,
        error_code: str,
        error_message: str,
        updated_at: Any,
    ) -> DocumentJobCallbackMessage:
        return self._update_message_by_id(
            message_id,
            status="ignored",
            error_code=error_code,
            error_message=error_message,
            lease_owner=None,
            leased_at=None,
            lease_expires_at=None,
            updated_at=updated_at,
        )

    def count_callback_messages_by_status(self, job_id: str | None = None) -> dict[str, int]:
        counts = {"pending": 0, "running": 0, "processed": 0, "failed": 0, "ignored": 0}
        for message in self.list_callback_messages(job_id):
            counts[message.status] = counts.get(message.status, 0) + 1
        return counts

    def _get_by_dedupe_key(self, dedupe_key: str) -> DocumentJobCallbackMessage | None:
        for path in sorted(self.backend.document_job_callback_messages_dir.glob("*.json")):
            message = self._read_message(path)
            if message.dedupe_key == dedupe_key:
                return message
        return None

    def _update_message_by_id(self, message_id: str, **patch: Any) -> DocumentJobCallbackMessage:
        message = self.get_callback_message(message_id)
        if message is None:
            raise FileNotFoundError(f"document job callback message 不存在: {message_id}")
        return self._update_message(message, **patch)

    def _update_message(self, message: DocumentJobCallbackMessage, **patch: Any) -> DocumentJobCallbackMessage:
        updated = DocumentJobCallbackMessage.model_validate(message.model_copy(update=patch).model_dump(mode="python"))
        self._write_message(updated)
        return updated

    def _write_message(self, message: DocumentJobCallbackMessage) -> None:
        self.backend.write_json(
            self.backend.document_job_callback_messages_dir / f"{message.id}.json",
            message.model_dump(mode="json"),
        )

    def _read_message(self, path) -> DocumentJobCallbackMessage:
        return DocumentJobCallbackMessage.model_validate(self.backend.read_json(path, {}))


class FileDocumentJobTranslationBatchRepository:
    """用 file backend 读写 provider translation batch 记录。"""

    def __init__(self, backend: FilePersistenceBackend) -> None:
        self.backend = backend

    def create_translation_batch(self, record: DocumentJobTranslationBatchRecord) -> DocumentJobTranslationBatchRecord:
        self._write_record(record)
        return record

    def get_translation_batch(self, batch_id: str) -> DocumentJobTranslationBatchRecord | None:
        path = self.backend.document_job_translation_batches_dir / f"{batch_id}.json"
        if not path.exists():
            return None
        return DocumentJobTranslationBatchRecord.model_validate(self.backend.read_json(path, {}))

    def list_translation_batches(
        self,
        job_id: str,
        *,
        generation: int | None = None,
    ) -> list[DocumentJobTranslationBatchRecord]:
        records = [
            self._read_record(path)
            for path in sorted(self.backend.document_job_translation_batches_dir.glob("*.json"))
        ]
        filtered = [
            record
            for record in records
            if record.job_id == job_id and (generation is None or record.generation == generation)
        ]
        return sorted(filtered, key=lambda item: (item.created_at, item.id))

    def update_translation_batch(self, batch_id: str, **patch: Any) -> DocumentJobTranslationBatchRecord:
        existing = self.get_translation_batch(batch_id)
        if existing is None:
            raise FileNotFoundError(f"translation batch 不存在: {batch_id}")
        updated = DocumentJobTranslationBatchRecord.model_validate(
            existing.model_copy(update=patch).model_dump(mode="python")
        )
        self._write_record(updated)
        return updated

    def update_translation_batch_if_current(
        self,
        batch_id: str,
        *,
        allowed_statuses: set[str],
        expected_generation: int,
        **patch: Any,
    ) -> DocumentJobTranslationBatchRecord | None:
        existing = self.get_translation_batch(batch_id)
        if existing is None:
            raise FileNotFoundError(f"translation batch 不存在: {batch_id}")
        if existing.generation != expected_generation or existing.status not in allowed_statuses:
            return None
        updated = DocumentJobTranslationBatchRecord.model_validate(
            existing.model_copy(update=patch).model_dump(mode="python")
        )
        self._write_record(updated)
        return updated

    def _write_record(self, record: DocumentJobTranslationBatchRecord) -> None:
        self.backend.write_json(
            self.backend.document_job_translation_batches_dir / f"{record.id}.json",
            record.model_dump(mode="json"),
        )

    def _read_record(self, path) -> DocumentJobTranslationBatchRecord:
        return DocumentJobTranslationBatchRecord.model_validate(self.backend.read_json(path, {}))
