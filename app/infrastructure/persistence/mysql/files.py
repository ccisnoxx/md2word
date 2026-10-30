from __future__ import annotations

# app/infrastructure/persistence/mysql/files.py: MySQL backend 的 job files 和 document files adapter。

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
import json
from typing import Any

from app.domains.jobs.models import JobFile
from app.domains.files.models import DocumentFileRecord
from app.domains.document_jobs.list_query import document_file_review_projection_from_raw
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend
from app.domains.files.result_registration import (
    expired_file, materialized_file, patched_file, ensure_file_mutation_allowed,
    reserved_file_deletion, finished_file_deletion, ensure_new_file_identity, ensure_result_descriptor_matches,
)


class MysqlJobFileRepository:
    """用 MySQL backend 读写 JobFile artifact metadata。"""

    def __init__(self, backend: MysqlPersistenceBackend) -> None:
        self.backend = backend

    def upsert_file(self, job_id: str, file: JobFile) -> None:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO job_files (job_id, file_type, payload, created_at)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        payload = VALUES(payload),
                        created_at = VALUES(created_at)
                    """,
                    (job_id, file.file_type, self.backend.dump_payload(file), file.created_at.isoformat()),
                )

    def list_files(self, job_id: str) -> list[JobFile]:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT payload FROM job_files WHERE job_id = %s ORDER BY created_at, file_type",
                    (job_id,),
                )
                rows = cursor.fetchall()
        return [JobFile.model_validate_json(row["payload"]) for row in rows]


class MysqlDocumentFileRepository:
    """在同一文件序列化点维护候选身份、物化和不可逆生命周期。"""

    def __init__(self, backend: MysqlPersistenceBackend) -> None:
        self.backend = backend

    @contextmanager
    def _locked_file(self, file_id: str) -> Iterator[tuple[Any, DocumentFileRecord | None]]:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload FROM document_files WHERE file_id = %s FOR UPDATE", (file_id,))
                row = cursor.fetchone()
            record = DocumentFileRecord.model_validate_json(row["payload"]) if row is not None else None
            if record is not None and record.id != file_id:
                raise ValueError("文件寻址与 payload 的 id 不一致。")
            yield connection, record

    def _write_file(self, connection: Any, record: DocumentFileRecord, *, create: bool = False) -> None:
        payload = self.backend.dump_payload(record)
        projection = json.dumps(document_file_review_projection_from_raw(payload), ensure_ascii=False)
        if create:
            query = "INSERT INTO document_files (file_id, payload, created_at, updated_at, review_query_json) VALUES (%s, %s, %s, %s, %s)"
            params = (record.id, payload, record.created_at.isoformat(), record.updated_at.isoformat(), projection)
        else:
            query = "UPDATE document_files SET payload = %s, created_at = %s, updated_at = %s, review_query_json = %s WHERE file_id = %s"
            params = (payload, record.created_at.isoformat(), record.updated_at.isoformat(), projection, record.id)
        with connection.cursor() as cursor:
            cursor.execute(query, params)

    def is_document_file_protected(self, file_id: str) -> bool:
        with self.backend.connect() as connection:
            return self._is_protected(connection, file_id)

    def _is_protected(self, connection: Any, file_id: str) -> bool:
        # 调用者已持有文件行锁；这是本短事务的首个一致读，不能移到取锁之前。
        with connection.cursor() as cursor:
            cursor.execute("SELECT protected_file_ids FROM document_job_publications")
            rows = cursor.fetchall()
        return any(file_id in json.loads(row["protected_file_ids"]) for row in rows)

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
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload FROM document_files WHERE file_id = %s", (file_id,))
                row = cursor.fetchone()
        if row is None:
            return None
        record = DocumentFileRecord.model_validate_json(row["payload"])
        if record.id != file_id:
            raise ValueError("文件寻址与 payload 的 id 不一致。")
        return record

    def list_document_files(self) -> list[DocumentFileRecord]:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload FROM document_files ORDER BY created_at, file_id")
                rows = cursor.fetchall()
        return [DocumentFileRecord.model_validate_json(row["payload"]) for row in rows]

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
