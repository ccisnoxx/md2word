from __future__ import annotations

# app/repositories/mysql_job_repository.py: MySQL 业务 metadata store adapter。

import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from app.core.audit_models import AuditEvent
from app.core.job_models import (
    JobEvent,
    JobFile,
    JobRecord,
    JobStageMessage,
    sync_source_pdf_compatibility_fields,
)
from app.core.resource_models import ResourceType, ResourceVersionRecord, utc_now

try:  # pragma: no cover - optional runtime dependency is exercised via fake connections in tests.
    import pymysql
except ImportError:  # pragma: no cover
    pymysql = None  # type: ignore[assignment]


@dataclass(frozen=True, slots=True)
class MysqlJobRepositoryConfig:
    """MySQL connection settings for the jobs metadata adapter."""

    host: str
    port: int
    user: str
    password: str
    database: str
    charset: str = "utf8mb4"
    connect_timeout_seconds: int = 10


ConnectFactory = Callable[[], Any]


MYSQL_SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS jobs (
        job_id VARCHAR(128) PRIMARY KEY,
        payload LONGTEXT NOT NULL,
        created_at VARCHAR(40) NOT NULL,
        updated_at VARCHAR(40) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS job_events (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        job_id VARCHAR(128) NOT NULL,
        payload LONGTEXT NOT NULL,
        created_at VARCHAR(40) NOT NULL,
        KEY idx_job_events_job_id_id (job_id, id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS job_files (
        job_id VARCHAR(128) NOT NULL,
        file_type VARCHAR(64) NOT NULL,
        payload LONGTEXT NOT NULL,
        created_at VARCHAR(40) NOT NULL,
        PRIMARY KEY (job_id, file_type)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS stage_messages (
        message_id VARCHAR(128) PRIMARY KEY,
        job_id VARCHAR(128) NOT NULL,
        status VARCHAR(32) NOT NULL,
        payload LONGTEXT NOT NULL,
        created_at VARCHAR(40) NOT NULL,
        updated_at VARCHAR(40) NOT NULL,
        KEY idx_stage_messages_status_created_at (status, created_at, message_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS resource_versions (
        resource_type VARCHAR(64) NOT NULL,
        resource_id VARCHAR(128) NOT NULL,
        version VARCHAR(64) NOT NULL,
        status VARCHAR(32) NOT NULL,
        snapshot_hash VARCHAR(128) NOT NULL,
        payload_ref VARCHAR(512) NULL,
        payload LONGTEXT NULL,
        created_at VARCHAR(40) NOT NULL,
        updated_at VARCHAR(40) NOT NULL,
        PRIMARY KEY (resource_type, resource_id, version),
        KEY idx_resource_versions_status (resource_type, status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS resource_default_versions (
        resource_type VARCHAR(64) NOT NULL,
        resource_id VARCHAR(128) NOT NULL,
        version VARCHAR(64) NOT NULL,
        updated_at VARCHAR(40) NOT NULL,
        PRIMARY KEY (resource_type, resource_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_events (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        audit_id VARCHAR(128) NOT NULL,
        payload LONGTEXT NOT NULL,
        created_at VARCHAR(40) NOT NULL,
        KEY idx_audit_events_created_at (created_at, id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
)


class MysqlJobRepository:
    """用 MySQL 落实现有 job metadata 协议，不改变 artifact 二进制存储边界。"""

    def __init__(
        self,
        config: MysqlJobRepositoryConfig,
        *,
        connect_factory: ConnectFactory | None = None,
        initialize_schema: bool = True,
    ) -> None:
        self.config = config
        self._connect_factory = connect_factory or self._build_pymysql_connection
        if initialize_schema:
            self._initialize_schema()

    def _build_pymysql_connection(self) -> Any:
        if pymysql is None:
            raise RuntimeError("JOBS_REPOSITORY_BACKEND=mysql 需要安装 PyMySQL 依赖。")
        return pymysql.connect(
            host=self.config.host,
            port=self.config.port,
            user=self.config.user,
            password=self.config.password,
            database=self.config.database,
            charset=self.config.charset,
            connect_timeout=self.config.connect_timeout_seconds,
            autocommit=False,
            cursorclass=pymysql.cursors.DictCursor,
        )

    @contextmanager
    def _connect(self) -> Iterator[Any]:
        connection = self._connect_factory()
        try:
            yield connection
            connection.commit()
        except Exception:
            if hasattr(connection, "rollback"):
                connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize_schema(self) -> None:
        """创建 MySQL metadata foundation 需要的基础表。"""

        with self._connect() as connection:
            with connection.cursor() as cursor:
                for statement in MYSQL_SCHEMA_STATEMENTS:
                    cursor.execute(statement)

    def _dump_payload(self, model: Any) -> str:
        return json.dumps(model.model_dump(mode="json"), ensure_ascii=False)

    def create_job(self, job: JobRecord) -> None:
        storage_job = sync_source_pdf_compatibility_fields(job)
        with self._connect() as connection:
            self._upsert_job(connection, storage_job)

    def _upsert_job(self, connection: Any, job: JobRecord) -> None:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO jobs (job_id, payload, created_at, updated_at)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    payload = VALUES(payload),
                    created_at = VALUES(created_at),
                    updated_at = VALUES(updated_at)
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
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload FROM jobs WHERE job_id = %s", (job_id,))
                row = cursor.fetchone()
        if row is None:
            return None
        return JobRecord.model_validate_json(row["payload"])

    def list_jobs(self) -> list[JobRecord]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload FROM jobs ORDER BY created_at, job_id")
                rows = cursor.fetchall()
        return [JobRecord.model_validate_json(row["payload"]) for row in rows]

    def update_job(self, job_id: str, **patch: Any) -> JobRecord:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload FROM jobs WHERE job_id = %s", (job_id,))
                row = cursor.fetchone()
            if row is None:
                raise FileNotFoundError(f"任务不存在: {job_id}")
            existing = JobRecord.model_validate_json(row["payload"])
            updated = sync_source_pdf_compatibility_fields(existing.model_copy(update=patch))
            self._upsert_job(connection, updated)
        return updated

    def append_event(self, job_id: str, event: JobEvent) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO job_events (job_id, payload, created_at)
                    VALUES (%s, %s, %s)
                    """,
                    (job_id, self._dump_payload(event), event.created_at.isoformat()),
                )

    def list_events(self, job_id: str) -> list[JobEvent]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT payload FROM job_events WHERE job_id = %s ORDER BY id",
                    (job_id,),
                )
                rows = cursor.fetchall()
        return [JobEvent.model_validate_json(row["payload"]) for row in rows]

    def append_audit_event(self, event: AuditEvent) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO audit_events (audit_id, payload, created_at)
                    VALUES (%s, %s, %s)
                    """,
                    (event.audit_id, self._dump_payload(event), event.created_at.isoformat()),
                )

    def list_audit_events(self) -> list[AuditEvent]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload FROM audit_events ORDER BY created_at, id")
                rows = cursor.fetchall()
        return [AuditEvent.model_validate_json(row["payload"]) for row in rows]

    def upsert_file(self, job_id: str, file: JobFile) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO job_files (job_id, file_type, payload, created_at)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        payload = VALUES(payload),
                        created_at = VALUES(created_at)
                    """,
                    (job_id, file.file_type, self._dump_payload(file), file.created_at.isoformat()),
                )

    def list_files(self, job_id: str) -> list[JobFile]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT payload FROM job_files WHERE job_id = %s ORDER BY created_at, file_type",
                    (job_id,),
                )
                rows = cursor.fetchall()
        return [JobFile.model_validate_json(row["payload"]) for row in rows]

    def put_stage_message(self, message: JobStageMessage) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO stage_messages (message_id, job_id, status, payload, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        job_id = VALUES(job_id),
                        status = VALUES(status),
                        payload = VALUES(payload),
                        created_at = VALUES(created_at),
                        updated_at = VALUES(updated_at)
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
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT payload FROM stage_messages WHERE message_id = %s",
                    (message_id,),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return JobStageMessage.model_validate_json(row["payload"])

    def update_stage_message(self, message_id: str, **patch: Any) -> JobStageMessage:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT payload FROM stage_messages WHERE message_id = %s",
                    (message_id,),
                )
                row = cursor.fetchone()
            if row is None:
                raise FileNotFoundError(f"stage message 不存在: {message_id}")
            updated = JobStageMessage.model_validate_json(row["payload"]).model_copy(update=patch)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE stage_messages
                    SET job_id = %s, status = %s, payload = %s, created_at = %s, updated_at = %s
                    WHERE message_id = %s
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
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT payload FROM stage_messages
                    WHERE status IN ('pending', 'running')
                    ORDER BY created_at, message_id
                    """
                )
                rows = cursor.fetchall()
        return [JobStageMessage.model_validate_json(row["payload"]) for row in rows]

    def list_stage_messages(self) -> list[JobStageMessage]:
        """返回 MySQL metadata store 中的全量 stage message，供校验使用。"""

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT payload FROM stage_messages
                    ORDER BY created_at, message_id
                    """
                )
                rows = cursor.fetchall()
        return [JobStageMessage.model_validate_json(row["payload"]) for row in rows]

    def list_pending_stage_messages(self) -> list[JobStageMessage]:
        """兼容旧调用名；语义实际是 replayable，不包含 failed。"""

        return self.list_replayable_stage_messages()

    def count_stage_messages_by_status(self) -> dict[str, int]:
        """按 pending/running/failed 统计当前 MySQL stage spool 中的 message。"""

        counts = {"pending": 0, "running": 0, "failed": 0}
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT status, COUNT(*) AS count FROM stage_messages GROUP BY status")
                rows = cursor.fetchall()
        for row in rows:
            counts[row["status"]] = int(row["count"])
        return counts

    def delete_stage_message(self, message_id: str) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM stage_messages WHERE message_id = %s", (message_id,))

    def save_resource_version(self, record: ResourceVersionRecord) -> ResourceVersionRecord:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO resource_versions
                        (resource_type, resource_id, version, status, snapshot_hash, payload_ref, payload, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        status = VALUES(status),
                        snapshot_hash = VALUES(snapshot_hash),
                        payload_ref = VALUES(payload_ref),
                        payload = VALUES(payload),
                        created_at = VALUES(created_at),
                        updated_at = VALUES(updated_at)
                    """,
                    (
                        record.resource_type,
                        record.resource_id,
                        record.version,
                        record.status.value,
                        record.snapshot_hash,
                        record.payload_ref,
                        json.dumps(record.payload, ensure_ascii=False) if record.payload is not None else None,
                        record.created_at.isoformat(),
                        record.updated_at.isoformat(),
                    ),
                )
        return record

    def get_resource_version(
        self,
        resource_type: ResourceType,
        resource_id: str,
        version: str,
    ) -> ResourceVersionRecord | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT resource_type, resource_id, version, status, snapshot_hash, payload_ref, payload, created_at, updated_at
                    FROM resource_versions
                    WHERE resource_type = %s AND resource_id = %s AND version = %s
                    """,
                    (resource_type, resource_id, version),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return self._load_resource_version(row)

    def list_resource_versions(self, resource_type: ResourceType, resource_id: str) -> list[ResourceVersionRecord]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT resource_type, resource_id, version, status, snapshot_hash, payload_ref, payload, created_at, updated_at
                    FROM resource_versions
                    WHERE resource_type = %s AND resource_id = %s
                    ORDER BY created_at, version
                    """,
                    (resource_type, resource_id),
                )
                rows = cursor.fetchall()
        return [self._load_resource_version(row) for row in rows]

    def set_default_resource_version(self, resource_type: ResourceType, resource_id: str, version: str) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO resource_default_versions (resource_type, resource_id, version, updated_at)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        version = VALUES(version),
                        updated_at = VALUES(updated_at)
                    """,
                    (resource_type, resource_id, version, utc_now().isoformat()),
                )

    def get_default_resource_version(self, resource_type: ResourceType, resource_id: str) -> ResourceVersionRecord | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT rv.resource_type, rv.resource_id, rv.version, rv.status, rv.snapshot_hash,
                           rv.payload_ref, rv.payload, rv.created_at, rv.updated_at
                    FROM resource_default_versions rdv
                    JOIN resource_versions rv
                      ON rv.resource_type = rdv.resource_type
                     AND rv.resource_id = rdv.resource_id
                     AND rv.version = rdv.version
                    WHERE rdv.resource_type = %s AND rdv.resource_id = %s
                    """,
                    (resource_type, resource_id),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return self._load_resource_version(row)

    def _load_resource_version(self, row: dict[str, Any]) -> ResourceVersionRecord:
        payload = json.loads(row["payload"]) if row["payload"] is not None else None
        return ResourceVersionRecord(
            resource_type=row["resource_type"],
            resource_id=row["resource_id"],
            version=row["version"],
            status=row["status"],
            snapshot_hash=row["snapshot_hash"],
            payload_ref=row["payload_ref"],
            payload=payload,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
