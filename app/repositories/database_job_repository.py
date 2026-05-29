from __future__ import annotations

# app/repositories/database_job_repository.py: 数据库 metadata store 的最小 repository 落点。

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from app.core.audit_models import AuditEvent
from app.core.job_models import (
    JobEvent,
    JobFile,
    JobRecord,
    JobStageMessage,
    sync_source_pdf_compatibility_fields,
)


class DatabaseJobRepository:
    """用 sqlite3 落实现有 job metadata 协议；是否接入 runtime 由配置决定。"""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(str(self.database_path), timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize_schema(self) -> None:
        """创建协议需要的最小表结构，不改变现有 file backend 存储格式。"""

        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS job_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_job_events_job_id_id
                ON job_events (job_id, id)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS job_files (
                    job_id TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (job_id, file_type)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS stage_messages (
                    message_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_stage_messages_status_created_at
                ON stage_messages (status, created_at, message_id)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    audit_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_audit_events_created_at
                ON audit_events (created_at, id)
                """
            )

    def _dump_payload(self, model: Any) -> str:
        return json.dumps(model.model_dump(mode="json"), ensure_ascii=False)

    def create_job(self, job: JobRecord) -> None:
        # source_pdf_context -> mineru_* 兼容投影继续只在持久化边界同步。
        storage_job = sync_source_pdf_compatibility_fields(job)
        with self._connect() as connection:
            self._upsert_job(connection, storage_job)

    def _upsert_job(self, connection: sqlite3.Connection, job: JobRecord) -> None:
        connection.execute(
            """
            INSERT INTO jobs (job_id, payload, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                payload = excluded.payload,
                created_at = excluded.created_at,
                updated_at = excluded.updated_at
            """,
            (
                job.id,
                self._dump_payload(job),
                job.created_at.isoformat(),
                job.updated_at.isoformat(),
            ),
        )

    def get_job(self, job_id: str) -> JobRecord | None:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        return JobRecord.model_validate_json(row["payload"])

    def list_jobs(self) -> list[JobRecord]:
        with self._connect() as connection:
            rows = connection.execute("SELECT payload FROM jobs ORDER BY created_at, job_id").fetchall()
        return [JobRecord.model_validate_json(row["payload"]) for row in rows]

    def update_job(self, job_id: str, **patch: Any) -> JobRecord:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            if row is None:
                raise FileNotFoundError(f"任务不存在: {job_id}")
            existing = JobRecord.model_validate_json(row["payload"])
            updated = sync_source_pdf_compatibility_fields(existing.model_copy(update=patch))
            self._upsert_job(connection, updated)
        return updated

    def append_event(self, job_id: str, event: JobEvent) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO job_events (job_id, payload, created_at)
                VALUES (?, ?, ?)
                """,
                (job_id, self._dump_payload(event), event.created_at.isoformat()),
            )

    def list_events(self, job_id: str) -> list[JobEvent]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM job_events WHERE job_id = ? ORDER BY id",
                (job_id,),
            ).fetchall()
        return [JobEvent.model_validate_json(row["payload"]) for row in rows]

    def append_audit_event(self, event: AuditEvent) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO audit_events (audit_id, payload, created_at)
                VALUES (?, ?, ?)
                """,
                (event.audit_id, self._dump_payload(event), event.created_at.isoformat()),
            )

    def list_audit_events(self) -> list[AuditEvent]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM audit_events ORDER BY created_at, id"
            ).fetchall()
        return [AuditEvent.model_validate_json(row["payload"]) for row in rows]

    def upsert_file(self, job_id: str, file: JobFile) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO job_files (job_id, file_type, payload, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(job_id, file_type) DO UPDATE SET
                    payload = excluded.payload,
                    created_at = excluded.created_at
                """,
                (job_id, file.file_type, self._dump_payload(file), file.created_at.isoformat()),
            )

    def list_files(self, job_id: str) -> list[JobFile]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM job_files WHERE job_id = ? ORDER BY created_at, file_type",
                (job_id,),
            ).fetchall()
        return [JobFile.model_validate_json(row["payload"]) for row in rows]

    def put_stage_message(self, message: JobStageMessage) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO stage_messages (message_id, job_id, status, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(message_id) DO UPDATE SET
                    job_id = excluded.job_id,
                    status = excluded.status,
                    payload = excluded.payload,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                (
                    message.id,
                    message.job_id,
                    message.status,
                    self._dump_payload(message),
                    message.created_at.isoformat(),
                    message.updated_at.isoformat(),
                ),
            )

    def get_stage_message(self, message_id: str) -> JobStageMessage | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM stage_messages WHERE message_id = ?",
                (message_id,),
            ).fetchone()
        if row is None:
            return None
        return JobStageMessage.model_validate_json(row["payload"])

    def update_stage_message(self, message_id: str, **patch: Any) -> JobStageMessage:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM stage_messages WHERE message_id = ?",
                (message_id,),
            ).fetchone()
            if row is None:
                raise FileNotFoundError(f"stage message 不存在: {message_id}")
            updated = JobStageMessage.model_validate_json(row["payload"]).model_copy(update=patch)
            connection.execute(
                """
                UPDATE stage_messages
                SET job_id = ?, status = ?, payload = ?, created_at = ?, updated_at = ?
                WHERE message_id = ?
                """,
                (
                    updated.job_id,
                    updated.status,
                    self._dump_payload(updated),
                    updated.created_at.isoformat(),
                    updated.updated_at.isoformat(),
                    message_id,
                ),
            )
        return updated

    def list_replayable_stage_messages(self) -> list[JobStageMessage]:
        """返回可在启动恢复或显式调度时重放的 pending/running message。"""

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload FROM stage_messages
                WHERE status IN ('pending', 'running')
                ORDER BY created_at, message_id
                """
            ).fetchall()
        return [JobStageMessage.model_validate_json(row["payload"]) for row in rows]

    def list_stage_messages(self) -> list[JobStageMessage]:
        """返回 database metadata store 中的全量 stage message，供迁移校验使用。"""

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload FROM stage_messages
                ORDER BY created_at, message_id
                """
            ).fetchall()
        return [JobStageMessage.model_validate_json(row["payload"]) for row in rows]

    def list_pending_stage_messages(self) -> list[JobStageMessage]:
        """兼容旧调用名；语义实际是 replayable，不包含 failed。"""

        return self.list_replayable_stage_messages()

    def count_stage_messages_by_status(self) -> dict[str, int]:
        """按 pending/running/failed 统计当前 stage spool 中的 message。"""

        counts = {"pending": 0, "running": 0, "failed": 0}
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT status, COUNT(*) AS count FROM stage_messages GROUP BY status"
            ).fetchall()
        for row in rows:
            counts[row["status"]] = row["count"]
        return counts

    def delete_stage_message(self, message_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM stage_messages WHERE message_id = ?", (message_id,))
