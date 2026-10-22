from __future__ import annotations

# app/infrastructure/persistence/file/document_jobs.py: file backend 的 document_jobs adapter。

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
from app.domains.document_jobs.delivery_state import backfill_document_job_state_payload, reviewed_job
from app.domains.document_jobs.repository import (
    TranslationBatchTreeInvalidError,
    reduce_translation_batch_generation,
    reducer_blocks_result_promotion,
    translation_plan_record,
    validate_expected_root_plans_or_raise,
    validate_translation_batch_tree_or_raise,
)
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

    def update_document_job(self, job_id: str, **patch: Any) -> DocumentJobRecord:
        with self._locked_job(job_id) as (connection, existing):
            updated = patched_job(existing, patch)
            self._write_job(connection, updated)
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
        with record_lock(self.backend.document_jobs_dir / record.job_id / "job.lock"):
            job = self._read_job_unlocked(record.job_id)
            if job is None:
                raise FileNotFoundError(f"文档任务不存在: {record.job_id}")
            if job.retry_count != record.generation:
                raise TranslationBatchTreeInvalidError("批次写入与当前任务代次不一致。")
            existing = self._read_record_by_id(record.id)
            if existing is not None:
                if existing != record:
                    raise ValueError("翻译批次 ID 已存在，不能覆盖已有记录。")
                return existing
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
        with record_lock(self.backend.document_jobs_dir / existing.job_id / "job.lock"):
            current = self._read_record_by_id(batch_id)
            if current is None:
                raise FileNotFoundError(f"translation batch 不存在: {batch_id}")
            updated = self._updated_record(current, patch)
            self._write_record(updated)
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
        with record_lock(self.backend.document_jobs_dir / job_id / "job.lock"):
            job = self._read_job_unlocked(job_id)
            if job is None:
                raise FileNotFoundError(f"文档任务不存在: {job_id}")
            actual = self._list_records_unlocked(job_id, generation=generation)
            if job.retry_count != generation or job.status in {"failed", "succeeded", "canceled"}:
                return self._list_records_unlocked(job_id, generation=job.retry_count)
            if not actual:
                if not expected_records:
                    return []
                for record in expected_records:
                    if record.job_id != job_id or record.generation != generation:
                        raise TranslationBatchTreeInvalidError("根计划与当前任务代次不一致。")
                    self._write_record(record)
                return expected_records
            validate_translation_batch_tree_or_raise(
                job_id=job_id,
                generation=generation,
                expected_plans=expected_plans,
                batches=actual,
            )
            return actual

    def get_translation_batch_snapshot(
        self,
        job_id: str,
        *,
        generation: int | None = None,
    ) -> tuple[DocumentJobRecord, list[DocumentJobTranslationBatchRecord]]:
        with record_lock(self.backend.document_jobs_dir / job_id / "job.lock"):
            job = self._read_job_unlocked(job_id)
            if job is None:
                raise FileNotFoundError(f"文档任务不存在: {job_id}")
            return job, self._list_records_unlocked(job_id, generation=generation)

    def enqueue_translation_batch(
        self,
        batch_id: str,
        *,
        expected_generation: int,
        expected_attempt_count: int,
        provider_call_budget: int,
        expected_plans: Sequence[Any],
    ) -> DocumentJobTranslationBatchRecord | None:
        existing = self.get_translation_batch(batch_id)
        if existing is None:
            raise FileNotFoundError(f"translation batch 不存在: {batch_id}")
        with record_lock(self.backend.document_jobs_dir / existing.job_id / "job.lock"):
            job = self._read_job_unlocked(existing.job_id)
            if job is None:
                raise FileNotFoundError(f"文档任务不存在: {existing.job_id}")
            batches = self._list_records_unlocked(existing.job_id, generation=expected_generation)
            if job.retry_count != expected_generation or job.status != "running" or job.stage != "translating":
                return None
            validate_translation_batch_tree_or_raise(
                job_id=existing.job_id, generation=expected_generation,
                expected_plans=expected_plans, batches=batches,
            )
            summary = reduce_translation_batch_generation(
                job=job, expected_plans=expected_plans, batches=batches,
                provider_call_budget=provider_call_budget, as_of=utc_now(),
            )
            if summary.outcome in {"failed", "completed", "canceled"}:
                return None
            current = self._read_record_by_id(batch_id)
            if current is None or current.status not in {"pending", "failed"}:
                return None
            if (
                current.attempt_count != expected_attempt_count
                or current.attempt_count >= current.max_attempts
                or (current.status == "failed" and not current.retryable)
                or sum(max(0, item.attempt_count) for item in batches) >= provider_call_budget
            ):
                return None
            updated = self._updated_record(current, {
                "status": "queued", "lease_owner": None, "leased_at": None,
                "lease_expires_at": None,
            })
            self._write_record(updated)
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
        existing = self.get_translation_batch(batch_id)
        if existing is None:
            raise FileNotFoundError(f"translation batch 不存在: {batch_id}")
        with record_lock(self.backend.document_jobs_dir / existing.job_id / "job.lock"):
            job = self._read_job_unlocked(existing.job_id)
            if job is None:
                raise FileNotFoundError(f"文档任务不存在: {existing.job_id}")
            batches = self._list_records_unlocked(existing.job_id, generation=expected_generation)
            if job.retry_count != expected_generation or job.status != "running" or job.stage != "translating":
                return None
            validate_translation_batch_tree_or_raise(
                job_id=existing.job_id,
                generation=expected_generation,
                expected_plans=expected_plans,
                batches=batches,
            )
            summary = reduce_translation_batch_generation(
                job=job, expected_plans=expected_plans, batches=batches,
                provider_call_budget=provider_call_budget, as_of=utc_now(),
            )
            if summary.outcome in {"failed", "completed", "canceled"}:
                return None
            current = self._read_record_by_id(batch_id)
            if current is None or current.generation != expected_generation:
                return None
            if current.status not in {"pending", "queued", "failed"}:
                return None
            if current.attempt_count != expected_attempt_count or current.attempt_count >= current.max_attempts:
                return None
            if current.status == "failed" and not current.retryable:
                return None
            used = sum(max(0, batch.attempt_count) for batch in batches)
            if used >= provider_call_budget:
                return None
            updated = self._updated_record(
                current,
                {
                    "status": "running",
                    "attempt_count": current.attempt_count + 1,
                    "lease_owner": lease_owner,
                    "leased_at": leased_at,
                    "lease_expires_at": lease_expires_at,
                    "error_code": None,
                    "error_message": None,
                    "retryable": False,
                },
            )
            self._write_record(updated)
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
        existing = self.get_translation_batch(batch_id)
        if existing is None:
            raise FileNotFoundError(f"translation batch 不存在: {batch_id}")
        with record_lock(self.backend.document_jobs_dir / existing.job_id / "job.lock"):
            job = self._read_job_unlocked(existing.job_id)
            current = self._read_record_by_id(batch_id)
            batches = self._list_records_unlocked(existing.job_id, generation=expected_generation)
            if (
                job is None
                or job.retry_count != expected_generation
                or job.status != "running"
                or job.stage != "translating"
            ):
                return None
            validate_translation_batch_tree_or_raise(
                job_id=existing.job_id,
                generation=expected_generation,
                expected_plans=expected_plans,
                batches=batches,
            )
            # 过期租约的自身回收是恢复动作，即使 reducer 将整代归约为失败也必须允许。
            reduce_translation_batch_generation(
                job=job, expected_plans=expected_plans, batches=batches,
                provider_call_budget=None, as_of=now,
            )
            if current is None or current.generation != expected_generation:
                return None
            expires = current.lease_expires_at
            now_utc = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
            if (
                current.status != "running"
                or current.attempt_count != expected_attempt_count
                or current.lease_owner != expected_lease_owner
                or expires is None
                or (expires if expires.tzinfo is not None else expires.replace(tzinfo=timezone.utc)) > now_utc
            ):
                return None
            updated = self._updated_record(
                current,
                {
                    "status": "failed",
                    "lease_owner": None,
                    "leased_at": None,
                    "lease_expires_at": None,
                    **patch,
                },
            )
            self._write_record(updated)
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
        existing = self.get_translation_batch(batch_id)
        if existing is None:
            raise FileNotFoundError(f"translation batch 不存在: {batch_id}")
        with record_lock(self.backend.document_jobs_dir / existing.job_id / "job.lock"):
            job = self._read_job_unlocked(existing.job_id)
            batches = self._list_records_unlocked(existing.job_id, generation=expected_generation)
            if (
                job is None
                or job.retry_count != expected_generation
                or job.status != "running"
                or job.stage != "translating"
            ):
                return None
            validate_translation_batch_tree_or_raise(
                job_id=existing.job_id,
                generation=expected_generation,
                expected_plans=expected_plans,
                batches=batches,
            )
            summary = reduce_translation_batch_generation(
                job=job, expected_plans=expected_plans, batches=batches,
                provider_call_budget=None, as_of=utc_now(),
            )
            parent = self._read_record_by_id(batch_id)
            if parent is None or parent.generation != expected_generation:
                return None
            if parent.status != "split" and reducer_blocks_result_promotion(summary):
                return None
            if parent.status == "split":
                stored = tuple(self._read_record_by_id(child.id) for child in children)
                if all(record is not None for record in stored):
                    return parent, tuple(record for record in stored if record is not None)
                raise TranslationBatchTreeInvalidError("split 父节点缺少已登记子节点。")
            if (
                parent.status != "running"
                or parent.attempt_count != expected_attempt_count
                or parent.lease_owner != expected_lease_owner
                or len(children) != 2
                or any(not child.item_ids for child in children)
            ):
                return None
            expected_ids = {
                f"{parent.id}_s{parent.split_level + 1}_01",
                f"{parent.id}_s{parent.split_level + 1}_02",
            }
            if {child.id for child in children} != expected_ids:
                raise TranslationBatchTreeInvalidError("split 子节点 ID 不符合确定性身份。")
            stored_children: list[DocumentJobTranslationBatchRecord] = []
            for child in children:
                if (
                    child.job_id != parent.job_id
                    or child.generation != parent.generation
                    or child.job_retry_count != parent.job_retry_count
                    or child.root_batch_id != parent.root_batch_id
                    or child.parent_batch_id != parent.id
                    or child.split_level != parent.split_level + 1
                    or child.item_count != len(child.item_ids)
                ):
                    raise TranslationBatchTreeInvalidError("split 子节点绑定或 item 计数不一致。")
                stored = self._read_record_by_id(child.id)
                if stored is not None and stored != child:
                    raise TranslationBatchTreeInvalidError("split 子节点 ID 已绑定其他内容。")
                stored_children.append(stored or child)
            updated_parent = self._updated_record(
                parent,
                {
                    "status": "split",
                    "lease_owner": None,
                    "leased_at": None,
                    "lease_expires_at": None,
                    "retryable": False,
                },
            )
            self._write_record(updated_parent)
            for child, stored in zip(children, stored_children):
                if self._read_record_by_id(child.id) is None:
                    self._write_record(child)
            return updated_parent, tuple(stored_children)

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
        existing = self.get_translation_batch(batch_id)
        if existing is None:
            raise FileNotFoundError(f"translation batch 不存在: {batch_id}")
        if expected_job_id is not None and existing.job_id != expected_job_id:
            return None
        with record_lock(self.backend.document_jobs_dir / existing.job_id / "job.lock"):
            current = self._read_record_by_id(batch_id)
            if current is None:
                raise FileNotFoundError(f"translation batch 不存在: {batch_id}")
            job = self._read_job_unlocked(current.job_id)
            if job is not None:
                if job.retry_count != expected_generation:
                    return None
                if expected_job_status is not None and job.status not in expected_job_status:
                    return None
                if expected_job_stages is not None and job.stage not in expected_job_stages:
                    return None
            if (
                current.generation != expected_generation
                or current.status not in allowed_statuses
                or (expected_attempt_count is not None and current.attempt_count != expected_attempt_count)
                or (expected_lease_owner is not None and current.lease_owner != expected_lease_owner)
            ):
                return None
            if expected_plans is not None:
                current_batches = self._list_records_unlocked(current.job_id, generation=expected_generation)
                validate_translation_batch_tree_or_raise(
                    job_id=current.job_id,
                    generation=expected_generation,
                    expected_plans=expected_plans,
                    batches=current_batches,
                )
                summary = reduce_translation_batch_generation(
                    job=job, expected_plans=expected_plans, batches=current_batches,
                    provider_call_budget=None, as_of=utc_now(),
                )
                if reducer_blocks_result_promotion(summary) and not (
                    current.status == "failed" and patch.get("status") == "failed"
                ):
                    return None
            updated = self._updated_record(current, patch)
            self._write_record(updated)
            return updated

    def _updated_record(
        self,
        existing: DocumentJobTranslationBatchRecord,
        patch: dict[str, Any],
    ) -> DocumentJobTranslationBatchRecord:
        return DocumentJobTranslationBatchRecord.model_validate(
            existing.model_copy(update=patch).model_dump(mode="python")
        )

    def _read_job_unlocked(self, job_id: str) -> DocumentJobRecord | None:
        path = self.backend.document_jobs_dir / job_id / "job.json"
        if not path.exists():
            return None
        return DocumentJobRecord.model_validate(self.backend.read_json(path, {}))

    def _read_record_by_id(self, batch_id: str) -> DocumentJobTranslationBatchRecord | None:
        path = self.backend.document_job_translation_batches_dir / f"{batch_id}.json"
        if not path.exists():
            return None
        return DocumentJobTranslationBatchRecord.model_validate(self.backend.read_json(path, {}))

    def _list_records_unlocked(
        self,
        job_id: str,
        *,
        generation: int | None = None,
    ) -> list[DocumentJobTranslationBatchRecord]:
        records = [
            self._read_record(path)
            for path in sorted(self.backend.document_job_translation_batches_dir.glob("*.json"))
        ]
        return sorted(
            [
                record for record in records
                if record.job_id == job_id and (generation is None or record.generation == generation)
            ],
            key=lambda item: (item.created_at, item.id),
        )

    def _write_record(self, record: DocumentJobTranslationBatchRecord) -> None:
        self.backend.write_json(
            self.backend.document_job_translation_batches_dir / f"{record.id}.json",
            record.model_dump(mode="json"),
        )

    def _read_record(self, path) -> DocumentJobTranslationBatchRecord:
        return DocumentJobTranslationBatchRecord.model_validate(self.backend.read_json(path, {}))
