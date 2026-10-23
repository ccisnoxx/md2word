from __future__ import annotations

# app/infrastructure/persistence/sqlite/document_jobs.py: sqlite backend 的 document_jobs adapter。

import sqlite3
import json
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from app.domains.document_jobs.models import (
    DocumentJobCallbackMessage,
    DocumentJobEventRecord,
    DocumentJobRecord,
    DocumentJobReviewStatus,
    DocumentJobTranslationQaIssueType,
    DocumentJobTranslationBatchRecord,
)
from app.domains.document_jobs.delivery_state import (
    backfill_document_job_state_payload, document_job_state_columns, reviewed_job,
)
from app.domains.document_jobs.repository import (
    TranslationBatchTreeInvalidError,
    reduce_translation_batch_generation,
    reducer_blocks_result_promotion,
    translation_plan_record,
    validate_expected_root_plans_or_raise,
    validate_translation_batch_tree_or_raise,
)
from app.infrastructure.persistence.sqlite.backend import SqlitePersistenceBackend
from app.domains.document_jobs.result_state import matches_current, patched_job, prepare_result, retry_job
from app.domains.files.models import DocumentFileRecord
from app.domains.resources.models import utc_now
from app.domains.document_jobs.preview_state import (
    PreviewArtifactObservation, PreviewClaim, PreviewClaimRequest, begin_preview_registration, claim_preview, finish_preview,
)


class SqliteDocumentJobRepository:
    """同一主记录的全部写入共享短锁；对象 I/O 在调用方锁外进行。"""

    def __init__(self, backend: SqlitePersistenceBackend) -> None:
        self.backend = backend

    def create_document_job(self, record: DocumentJobRecord) -> DocumentJobRecord:
        with self.backend.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO document_jobs (job_id, payload, created_at, updated_at, "
                "quality_status, review_status, delivery_status, quality_summary_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (record.id, self.backend.dump_payload(record), record.created_at.isoformat(), record.updated_at.isoformat(),
                 *document_job_state_columns(record)),
            )
        return record

    def _write_job(self, connection: Any, record: DocumentJobRecord) -> None:
        connection.execute(
            "UPDATE document_jobs SET payload = ?, created_at = ?, updated_at = ?, "
            "quality_status = ?, review_status = ?, delivery_status = ?, quality_summary_json = ? WHERE job_id = ?",
            (self.backend.dump_payload(record), record.created_at.isoformat(), record.updated_at.isoformat(),
             *document_job_state_columns(record), record.id),
        )

    @contextmanager
    def _locked_payload(self, job_id: str) -> Iterator[tuple[Any, Any]]:
        with self.backend.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT payload FROM document_jobs WHERE job_id = ?", (job_id,)).fetchone()
            if row is None:
                raise FileNotFoundError(f"文档任务不存在: {job_id}")
            yield connection, json.loads(row["payload"])

    @contextmanager
    def _locked_job(self, job_id: str) -> Iterator[tuple[Any, DocumentJobRecord]]:
        with self._locked_payload(job_id) as (connection, payload):
            yield connection, DocumentJobRecord.model_validate(payload)

    def get_document_job(self, job_id: str) -> DocumentJobRecord | None:
        with self.backend.connect() as connection:
            row = connection.execute(
                "SELECT payload FROM document_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return DocumentJobRecord.model_validate_json(row["payload"])

    def list_document_jobs(self) -> list[DocumentJobRecord]:
        with self.backend.connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM document_jobs ORDER BY created_at, job_id"
            ).fetchall()
        return [DocumentJobRecord.model_validate_json(row["payload"]) for row in rows]

    def update_document_job_if_current(
        self, job_id: str, *, allowed_statuses: set[str], allowed_stages: set[str],
        expected_retry_count: int | None = None, expected_document_ir_file_id: str | None = None,
        require_no_prepared_result: bool = False, expected_prepared_result_file_id: str | None = None,
        preview_contribution: dict | None = None,
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
            updated = patched_job(existing, patch, preview_contribution=preview_contribution)
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

    def claim_document_job_preview(self, job_id: str, *, request: PreviewClaimRequest,
        observation: PreviewArtifactObservation | None = None,
    ) -> PreviewClaim:
        with self._locked_job(job_id) as (connection, existing):
            claim = claim_preview(existing, request, observation=observation, now=utc_now())
            if claim.job != existing:
                self._write_job(connection, claim.job)
            return claim

    def finish_document_job_preview(
        self, job_id: str, *, request: PreviewClaimRequest, revision: int, lease_token: str,
        status: str, manifest_file_id: str, error_code: str | None, retryable: bool, evidence: dict,
    ) -> DocumentJobRecord | None:
        with self._locked_job(job_id) as (connection, existing):
            updated = finish_preview(existing, request, revision=revision, lease_token=lease_token,
                status=status, manifest_file_id=manifest_file_id, error_code=error_code,
                retryable=retryable, evidence=evidence, now=utc_now())
            if updated is not None:
                self._write_job(connection, updated)
            return updated

    def begin_document_job_preview_registration(
        self, job_id: str, *, request: PreviewClaimRequest, revision: int, lease_token: str, attempt: int,
    ) -> DocumentJobRecord | None:
        with self._locked_job(job_id) as (connection, existing):
            updated = begin_preview_registration(existing, request, revision=revision, lease_token=lease_token,
                                                 attempt=attempt, now=utc_now())
            if updated is not None:
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
        with self._locked_payload(job_id) as (connection, payload):
            updated = backfill_document_job_state_payload(payload)
            connection.execute(
                "UPDATE document_jobs SET payload = ?, quality_status = ?, review_status = ?, "
                "delivery_status = ?, quality_summary_json = ? WHERE job_id = ?",
                (json.dumps(updated, ensure_ascii=False),
                 *document_job_state_columns(DocumentJobRecord.model_validate(updated)), job_id),
            )
            return updated != payload

    def update_document_job(self, job_id: str, **patch: Any) -> DocumentJobRecord:
        with self._locked_job(job_id) as (connection, existing):
            updated = patched_job(existing, patch)
            self._write_job(connection, updated)
            return updated


class SqliteDocumentJobEventRepository:
    """用 sqlite backend 追加和读取 document job 事件。

    当前 sqlite 存储沿用既有 `job_events` 表，保持历史 payload shape 不变。
    """

    def __init__(self, backend: SqlitePersistenceBackend) -> None:
        self.backend = backend

    def append_document_job_event(self, job_id: str, event: DocumentJobEventRecord) -> None:
        with self.backend.connect() as connection:
            connection.execute(
                """
                INSERT INTO job_events (job_id, payload, created_at)
                VALUES (?, ?, ?)
                """,
                (job_id, self.backend.dump_payload(event), event.created_at.isoformat()),
            )

    def list_document_job_events(self, job_id: str) -> list[DocumentJobEventRecord]:
        with self.backend.connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM job_events WHERE job_id = ? ORDER BY id",
                (job_id,),
            ).fetchall()
        return [DocumentJobEventRecord.model_validate_json(row["payload"]) for row in rows]


class SqliteDocumentJobCallbackMessageStore:
    """用 sqlite backend 读写 document_jobs callback message。"""

    def __init__(self, backend: SqlitePersistenceBackend) -> None:
        self.backend = backend

    def put_or_get_callback_message(
        self,
        message: DocumentJobCallbackMessage,
    ) -> tuple[DocumentJobCallbackMessage, bool]:
        with self.backend.connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO document_job_callback_messages
                    (message_id, job_id, status, dedupe_key, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.id,
                    message.job_id,
                    message.status,
                    message.dedupe_key,
                    self.backend.dump_payload(message),
                    message.created_at.isoformat(),
                    message.updated_at.isoformat(),
                ),
            )
            row = connection.execute(
                "SELECT payload FROM document_job_callback_messages WHERE dedupe_key = ?",
                (message.dedupe_key,),
            ).fetchone()
        if row is None:
            raise FileNotFoundError(f"document job callback message 不存在: {message.id}")
        stored = DocumentJobCallbackMessage.model_validate_json(row["payload"])
        return stored, stored.id == message.id

    def get_callback_message(self, message_id: str) -> DocumentJobCallbackMessage | None:
        with self.backend.connect() as connection:
            row = connection.execute(
                "SELECT payload FROM document_job_callback_messages WHERE message_id = ?",
                (message_id,),
            ).fetchone()
        if row is None:
            return None
        return DocumentJobCallbackMessage.model_validate_json(row["payload"])

    def list_callback_messages(
        self,
        job_id: str | None = None,
        *,
        statuses: set[str] | None = None,
        limit: int | None = None,
    ) -> list[DocumentJobCallbackMessage]:
        query = "SELECT payload FROM document_job_callback_messages WHERE 1 = 1"
        params: list[str | int] = []
        if job_id is not None:
            query += " AND job_id = ?"
            params.append(job_id)
        if statuses is not None:
            ordered_statuses = sorted(statuses)
            placeholders = ", ".join("?" for _ in ordered_statuses)
            query += f" AND status IN ({placeholders})"
            params.extend(ordered_statuses)
        query += " ORDER BY created_at, message_id"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        with self.backend.connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [DocumentJobCallbackMessage.model_validate_json(row["payload"]) for row in rows]

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
        return self._update_if_replayable(
            message_id,
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
        return self._update_message(message_id, status="processed", updated_at=updated_at)

    def mark_callback_message_failed(
        self,
        message_id: str,
        *,
        error_code: str,
        error_message: str,
        updated_at: Any,
    ) -> DocumentJobCallbackMessage:
        return self._update_message(
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
        return self._update_message(
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
        query = "SELECT status, COUNT(*) AS count FROM document_job_callback_messages"
        params: tuple[str, ...] = ()
        if job_id is not None:
            query += " WHERE job_id = ?"
            params = (job_id,)
        query += " GROUP BY status"
        with self.backend.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        for row in rows:
            counts[row["status"]] = row["count"]
        return counts

    def _update_if_replayable(self, message_id: str, **patch: Any) -> DocumentJobCallbackMessage | None:
        message = self.get_callback_message(message_id)
        if message is None:
            raise FileNotFoundError(f"document job callback message 不存在: {message_id}")
        if message.status not in {"pending", "running"}:
            return None
        return self._update_message(message_id, **patch)

    def _update_message(self, message_id: str, **patch: Any) -> DocumentJobCallbackMessage:
        with self.backend.connect() as connection:
            row = connection.execute(
                "SELECT payload FROM document_job_callback_messages WHERE message_id = ?",
                (message_id,),
            ).fetchone()
            if row is None:
                raise FileNotFoundError(f"document job callback message 不存在: {message_id}")
            updated = DocumentJobCallbackMessage.model_validate_json(row["payload"]).model_copy(update=patch)
            connection.execute(
                """
                UPDATE document_job_callback_messages
                SET job_id = ?, status = ?, dedupe_key = ?, payload = ?, created_at = ?, updated_at = ?
                WHERE message_id = ?
                """,
                (
                    updated.job_id,
                    updated.status,
                    updated.dedupe_key,
                    self.backend.dump_payload(updated),
                    updated.created_at.isoformat(),
                    updated.updated_at.isoformat(),
                    message_id,
                ),
            )
        return updated


class SqliteDocumentJobTranslationBatchRepository:
    """用 sqlite backend 读写 provider translation batch 记录。"""

    def __init__(self, backend: SqlitePersistenceBackend) -> None:
        self.backend = backend

    def create_translation_batch(self, record: DocumentJobTranslationBatchRecord) -> DocumentJobTranslationBatchRecord:
        with self.backend.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            job_row = connection.execute(
                "SELECT payload FROM document_jobs WHERE job_id = ?", (record.job_id,)
            ).fetchone()
            if job_row is None:
                raise FileNotFoundError(f"文档任务不存在: {record.job_id}")
            job = DocumentJobRecord.model_validate_json(job_row["payload"])
            if job.retry_count != record.generation:
                raise TranslationBatchTreeInvalidError("批次写入与当前任务代次不一致。")
            row = connection.execute(
                "SELECT payload FROM document_job_translation_batches WHERE batch_id = ?",
                (record.id,),
            ).fetchone()
            if row is not None:
                existing = DocumentJobTranslationBatchRecord.model_validate_json(row["payload"])
                if existing != record:
                    raise ValueError("翻译批次 ID 已存在，不能覆盖已有记录。")
                return existing
            self._insert_record(connection, record)
        return record

    def get_translation_batch(self, batch_id: str) -> DocumentJobTranslationBatchRecord | None:
        with self.backend.connect() as connection:
            row = connection.execute(
                "SELECT payload FROM document_job_translation_batches WHERE batch_id = ?",
                (batch_id,),
            ).fetchone()
        if row is None:
            return None
        return DocumentJobTranslationBatchRecord.model_validate_json(row["payload"])

    def list_translation_batches(
        self,
        job_id: str,
        *,
        generation: int | None = None,
    ) -> list[DocumentJobTranslationBatchRecord]:
        query = "SELECT payload FROM document_job_translation_batches WHERE job_id = ?"
        params: list[str | int] = [job_id]
        if generation is not None:
            query += " AND generation = ?"
            params.append(generation)
        query += " ORDER BY created_at, batch_id"
        with self.backend.connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [DocumentJobTranslationBatchRecord.model_validate_json(row["payload"]) for row in rows]

    def update_translation_batch(self, batch_id: str, **patch: Any) -> DocumentJobTranslationBatchRecord:
        with self.backend.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT payload FROM document_job_translation_batches WHERE batch_id = ?",
                (batch_id,),
            ).fetchone()
            if row is None:
                raise FileNotFoundError(f"translation batch 不存在: {batch_id}")
            existing = DocumentJobTranslationBatchRecord.model_validate_json(row["payload"])
            updated = DocumentJobTranslationBatchRecord.model_validate(
                existing.model_copy(update=patch).model_dump(mode="python")
            )
            self._upsert_record(connection, updated)
        return updated

    def update_translation_batch_if_current(
        self,
        batch_id: str,
        *,
        allowed_statuses: set[str],
        expected_generation: int,
        expected_attempt_count: int | None = None,
        expected_lease_owner: str | None = None,
        expected_job_id: str | None = None,
        expected_job_status: set[str] | None = None,
        expected_job_stages: set[str] | None = None,
        expected_plans: Sequence[Any] | None = None,
        **patch: Any,
    ) -> DocumentJobTranslationBatchRecord | None:
        with self.backend.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT payload FROM document_job_translation_batches WHERE batch_id = ?",
                (batch_id,),
            ).fetchone()
            if row is None:
                raise FileNotFoundError(f"translation batch 不存在: {batch_id}")
            existing = DocumentJobTranslationBatchRecord.model_validate_json(row["payload"])
            if expected_job_id is not None and existing.job_id != expected_job_id:
                return None
            job_row = connection.execute(
                "SELECT payload FROM document_jobs WHERE job_id = ?", (existing.job_id,)
            ).fetchone()
            if job_row is None:
                raise FileNotFoundError(f"文档任务不存在: {existing.job_id}")
            job = DocumentJobRecord.model_validate_json(job_row["payload"])
            if job.retry_count != expected_generation:
                return None
            if expected_job_status is not None and job.status not in expected_job_status:
                return None
            if expected_job_stages is not None and job.stage not in expected_job_stages:
                return None
            if (
                existing.generation != expected_generation
                or existing.status not in allowed_statuses
                or (expected_attempt_count is not None and existing.attempt_count != expected_attempt_count)
                or (expected_lease_owner is not None and existing.lease_owner != expected_lease_owner)
            ):
                return None
            if expected_plans is not None:
                current_batches = self._list_locked(connection, existing.job_id, expected_generation)
                validate_translation_batch_tree_or_raise(
                    job_id=existing.job_id,
                    generation=expected_generation,
                    expected_plans=expected_plans,
                    batches=current_batches,
                )
                summary = reduce_translation_batch_generation(
                    job=job, expected_plans=expected_plans, batches=current_batches,
                    provider_call_budget=None, as_of=utc_now(),
                )
                if reducer_blocks_result_promotion(summary) and not (
                    existing.status == "failed" and patch.get("status") == "failed"
                ):
                    return None
            updated = DocumentJobTranslationBatchRecord.model_validate(
                existing.model_copy(update=patch).model_dump(mode="python")
            )
            self._upsert_record(connection, updated)
        return updated

    def ensure_translation_batch_roots(
        self,
        job_id: str,
        *,
        generation: int,
        expected_plans: Sequence[Any],
    ) -> list[DocumentJobTranslationBatchRecord]:
        validate_expected_root_plans_or_raise(
            job_id=job_id, generation=generation, expected_plans=expected_plans,
        )
        expected_records = [translation_plan_record(plan) for plan in expected_plans]
        with self.backend.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            job_row = connection.execute(
                "SELECT payload FROM document_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            if job_row is None:
                raise FileNotFoundError(f"文档任务不存在: {job_id}")
            job = DocumentJobRecord.model_validate_json(job_row["payload"])
            actual = self._list_locked(connection, job_id, generation)
            if job.retry_count != generation or job.status in {"failed", "succeeded", "canceled"}:
                return self._list_locked(connection, job_id, job.retry_count)
            if not actual:
                if not expected_records:
                    return []
                for record in expected_records:
                    if record.job_id != job_id or record.generation != generation:
                        raise TranslationBatchTreeInvalidError("根计划与当前任务代次不一致。")
                    self._insert_record(connection, record)
                return expected_records
            validate_translation_batch_tree_or_raise(
                job_id=job_id, generation=generation,
                expected_plans=expected_plans, batches=actual,
            )
            return actual

    def get_translation_batch_snapshot(
        self,
        job_id: str,
        *,
        generation: int | None = None,
    ) -> tuple[DocumentJobRecord, list[DocumentJobTranslationBatchRecord]]:
        with self.backend.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT payload FROM document_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            if row is None:
                raise FileNotFoundError(f"文档任务不存在: {job_id}")
            return DocumentJobRecord.model_validate_json(row["payload"]), self._list_locked(connection, job_id, generation)

    def enqueue_translation_batch(
        self,
        batch_id: str,
        *,
        expected_generation: int,
        expected_attempt_count: int,
        provider_call_budget: int,
        expected_plans: Sequence[Any],
    ) -> DocumentJobTranslationBatchRecord | None:
        with self.backend.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = self._select_batch(connection, batch_id)
            if current is None:
                raise FileNotFoundError(f"translation batch 不存在: {batch_id}")
            row = connection.execute(
                "SELECT payload FROM document_jobs WHERE job_id = ?", (current.job_id,)
            ).fetchone()
            if row is None:
                raise FileNotFoundError(f"文档任务不存在: {current.job_id}")
            job = DocumentJobRecord.model_validate_json(row["payload"])
            batches = self._list_locked(connection, current.job_id, expected_generation)
            if job.retry_count != expected_generation or job.status != "running" or job.stage != "translating":
                return None
            validate_translation_batch_tree_or_raise(
                job_id=current.job_id, generation=expected_generation,
                expected_plans=expected_plans, batches=batches,
            )
            summary = reduce_translation_batch_generation(
                job=job, expected_plans=expected_plans, batches=batches,
                provider_call_budget=provider_call_budget, as_of=utc_now(),
            )
            if summary.outcome in {"failed", "completed", "canceled"}:
                return None
            if (
                current.status not in {"pending", "failed"}
                or current.attempt_count != expected_attempt_count
                or current.attempt_count >= current.max_attempts
                or (current.status == "failed" and not current.retryable)
                or sum(max(0, item.attempt_count) for item in batches) >= provider_call_budget
            ):
                return None
            updated = self._updated_record(current, {
                "status": "queued", "lease_owner": None, "leased_at": None,
                "lease_expires_at": None,
            })
            self._upsert_record(connection, updated)
            return updated

    def claim_translation_batch(
        self,
        batch_id: str,
        *,
        expected_generation: int,
        expected_attempt_count: int,
        lease_owner: str,
        leased_at: datetime,
        lease_expires_at: datetime,
        provider_call_budget: int,
        expected_plans: Sequence[Any],
    ) -> DocumentJobTranslationBatchRecord | None:
        with self.backend.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT payload FROM document_job_translation_batches WHERE batch_id = ?", (batch_id,)
            ).fetchone()
            if row is None:
                raise FileNotFoundError(f"translation batch 不存在: {batch_id}")
            current = DocumentJobTranslationBatchRecord.model_validate_json(row["payload"])
            job_row = connection.execute(
                "SELECT payload FROM document_jobs WHERE job_id = ?", (current.job_id,)
            ).fetchone()
            if job_row is None:
                raise FileNotFoundError(f"文档任务不存在: {current.job_id}")
            job = DocumentJobRecord.model_validate_json(job_row["payload"])
            batches = self._list_locked(connection, current.job_id, expected_generation)
            if job.retry_count != expected_generation or job.status != "running" or job.stage != "translating":
                return None
            validate_translation_batch_tree_or_raise(
                job_id=current.job_id, generation=expected_generation,
                expected_plans=expected_plans, batches=batches,
            )
            summary = reduce_translation_batch_generation(
                job=job, expected_plans=expected_plans, batches=batches,
                provider_call_budget=provider_call_budget, as_of=utc_now(),
            )
            if summary.outcome in {"failed", "completed", "canceled"}:
                return None
            if (
                current.status not in {"pending", "queued", "failed"}
                or current.attempt_count != expected_attempt_count
                or current.attempt_count >= current.max_attempts
                or (current.status == "failed" and not current.retryable)
                or sum(max(0, batch.attempt_count) for batch in batches) >= provider_call_budget
            ):
                return None
            updated = self._updated_record(current, {
                "status": "running", "attempt_count": current.attempt_count + 1,
                "lease_owner": lease_owner, "leased_at": leased_at,
                "lease_expires_at": lease_expires_at, "error_code": None,
                "error_message": None, "retryable": False,
            })
            self._upsert_record(connection, updated)
            return updated

    def release_translation_batch_lease(
        self,
        batch_id: str,
        *,
        expected_generation: int,
        expected_attempt_count: int,
        expected_lease_owner: str,
        now: datetime,
        expected_plans: Sequence[Any],
        **patch: Any,
    ) -> DocumentJobTranslationBatchRecord | None:
        with self.backend.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = self._select_batch(connection, batch_id)
            if current is None:
                raise FileNotFoundError(f"translation batch 不存在: {batch_id}")
            job_row = connection.execute(
                "SELECT payload FROM document_jobs WHERE job_id = ?", (current.job_id,)
            ).fetchone()
            if job_row is None:
                raise FileNotFoundError(f"文档任务不存在: {current.job_id}")
            job = DocumentJobRecord.model_validate_json(job_row["payload"])
            batches = self._list_locked(connection, current.job_id, expected_generation)
            if (
                job.retry_count != expected_generation
                or job.status != "running"
                or job.stage != "translating"
            ):
                return None
            validate_translation_batch_tree_or_raise(
                job_id=current.job_id,
                generation=expected_generation,
                expected_plans=expected_plans,
                batches=batches,
            )
            reduce_translation_batch_generation(
                job=job, expected_plans=expected_plans, batches=batches,
                provider_call_budget=None, as_of=now,
            )
            expiry = current.lease_expires_at
            now_utc = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
            if (
                current.generation != expected_generation or current.status != "running"
                or current.attempt_count != expected_attempt_count
                or current.lease_owner != expected_lease_owner or expiry is None
                or (expiry if expiry.tzinfo is not None else expiry.replace(tzinfo=timezone.utc)) > now_utc
            ):
                return None
            updated = self._updated_record(current, {
                "status": "failed", "lease_owner": None, "leased_at": None,
                "lease_expires_at": None, **patch,
            })
            self._upsert_record(connection, updated)
            return updated

    def split_translation_batch(
        self,
        batch_id: str,
        *,
        expected_generation: int,
        expected_attempt_count: int,
        expected_lease_owner: str,
        expected_plans: Sequence[Any],
        children: Sequence[DocumentJobTranslationBatchRecord],
    ) -> tuple[DocumentJobTranslationBatchRecord, tuple[DocumentJobTranslationBatchRecord, ...]] | None:
        with self.backend.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            parent = self._select_batch(connection, batch_id)
            if parent is None:
                raise FileNotFoundError(f"translation batch 不存在: {batch_id}")
            job_row = connection.execute(
                "SELECT payload FROM document_jobs WHERE job_id = ?", (parent.job_id,)
            ).fetchone()
            if job_row is None:
                raise FileNotFoundError(f"文档任务不存在: {parent.job_id}")
            job = DocumentJobRecord.model_validate_json(job_row["payload"])
            batches = self._list_locked(connection, parent.job_id, expected_generation)
            if (
                job.retry_count != expected_generation
                or job.status != "running"
                or job.stage != "translating"
            ):
                return None
            validate_translation_batch_tree_or_raise(
                job_id=parent.job_id,
                generation=expected_generation,
                expected_plans=expected_plans,
                batches=batches,
            )
            summary = reduce_translation_batch_generation(
                job=job, expected_plans=expected_plans, batches=batches,
                provider_call_budget=None, as_of=utc_now(),
            )
            if parent.status != "split" and reducer_blocks_result_promotion(summary):
                return None
            if parent.status == "split":
                stored = tuple(self._select_batch(connection, child.id) for child in children)
                if all(record is not None for record in stored):
                    return parent, tuple(record for record in stored if record is not None)
                raise TranslationBatchTreeInvalidError("split 父节点缺少已登记子节点。")
            if (
                parent.generation != expected_generation or parent.status != "running"
                or parent.attempt_count != expected_attempt_count
                or parent.lease_owner != expected_lease_owner or len(children) != 2
                or any(not child.item_ids for child in children)
            ):
                return None
            expected_ids = {f"{parent.id}_s{parent.split_level + 1}_01", f"{parent.id}_s{parent.split_level + 1}_02"}
            if {child.id for child in children} != expected_ids:
                raise TranslationBatchTreeInvalidError("split 子节点 ID 不符合确定性身份。")
            for child in children:
                stored = self._select_batch(connection, child.id)
                if (
                    child.job_id != parent.job_id or child.generation != parent.generation
                    or child.job_retry_count != parent.job_retry_count or child.root_batch_id != parent.root_batch_id
                    or child.parent_batch_id != parent.id or child.split_level != parent.split_level + 1
                    or child.item_count != len(child.item_ids)
                ):
                    raise TranslationBatchTreeInvalidError("split 子节点绑定或 item 计数不一致。")
                if stored is not None and stored != child:
                    raise TranslationBatchTreeInvalidError("split 子节点 ID 已绑定其他内容。")
            updated_parent = self._updated_record(parent, {
                "status": "split", "lease_owner": None, "leased_at": None,
                "lease_expires_at": None, "retryable": False,
            })
            self._upsert_record(connection, updated_parent)
            for child in children:
                if self._select_batch(connection, child.id) is None:
                    self._insert_record(connection, child)
            return updated_parent, tuple(children)

    def _select_batch(self, connection: sqlite3.Connection, batch_id: str) -> DocumentJobTranslationBatchRecord | None:
        row = connection.execute(
            "SELECT payload FROM document_job_translation_batches WHERE batch_id = ?", (batch_id,)
        ).fetchone()
        return None if row is None else DocumentJobTranslationBatchRecord.model_validate_json(row["payload"])

    def _list_locked(self, connection: sqlite3.Connection, job_id: str, generation: int | None) -> list[DocumentJobTranslationBatchRecord]:
        query = "SELECT payload FROM document_job_translation_batches WHERE job_id = ?"
        params: list[str | int] = [job_id]
        if generation is not None:
            query += " AND generation = ?"
            params.append(generation)
        query += " ORDER BY created_at, batch_id"
        rows = connection.execute(query, tuple(params)).fetchall()
        return [DocumentJobTranslationBatchRecord.model_validate_json(row["payload"]) for row in rows]

    @staticmethod
    def _updated_record(existing: DocumentJobTranslationBatchRecord, patch: dict[str, Any]) -> DocumentJobTranslationBatchRecord:
        return DocumentJobTranslationBatchRecord.model_validate(existing.model_copy(update=patch).model_dump(mode="python"))

    def _insert_record(self, connection: sqlite3.Connection, record: DocumentJobTranslationBatchRecord) -> None:
        connection.execute(
            """
            INSERT INTO document_job_translation_batches
                (batch_id, job_id, generation, status, payload, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.job_id,
                record.generation,
                record.status,
                self.backend.dump_payload(record),
                record.created_at.isoformat(),
                record.updated_at.isoformat(),
            ),
        )

    def _upsert_record(self, connection: sqlite3.Connection, record: DocumentJobTranslationBatchRecord) -> None:
        connection.execute(
            """
            INSERT INTO document_job_translation_batches
                (batch_id, job_id, generation, status, payload, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(batch_id) DO UPDATE SET
                job_id = excluded.job_id,
                generation = excluded.generation,
                status = excluded.status,
                payload = excluded.payload,
                created_at = excluded.created_at,
                updated_at = excluded.updated_at
            """,
            (
                record.id,
                record.job_id,
                record.generation,
                record.status,
                self.backend.dump_payload(record),
                record.created_at.isoformat(),
                record.updated_at.isoformat(),
            ),
        )
