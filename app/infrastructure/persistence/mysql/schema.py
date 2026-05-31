from __future__ import annotations

# app/infrastructure/persistence/mysql/schema.py: MySQL metadata backend 的 schema bootstrap。

from typing import Any


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
    """
    CREATE TABLE IF NOT EXISTS document_files (
        file_id VARCHAR(128) PRIMARY KEY,
        payload LONGTEXT NOT NULL,
        created_at VARCHAR(40) NOT NULL,
        updated_at VARCHAR(40) NOT NULL,
        KEY idx_document_files_created_at (created_at, file_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS document_jobs (
        job_id VARCHAR(128) PRIMARY KEY,
        payload LONGTEXT NOT NULL,
        created_at VARCHAR(40) NOT NULL,
        updated_at VARCHAR(40) NOT NULL,
        KEY idx_document_jobs_created_at (created_at, job_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
)


def initialize_schema(connection: Any) -> None:
    """创建 MySQL metadata backend 当前需要的表。"""

    with connection.cursor() as cursor:
        for statement in MYSQL_SCHEMA_STATEMENTS:
            cursor.execute(statement)
