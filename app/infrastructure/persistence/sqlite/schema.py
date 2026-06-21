# File: app/infrastructure/persistence/sqlite/schema.py
# Purpose: 定义 sqlite metadata backend 的 schema bootstrap SQL。

from __future__ import annotations

import sqlite3


SQLITE_SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS jobs (
        job_id TEXT PRIMARY KEY,
        payload TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS job_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT NOT NULL,
        payload TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_job_events_job_id_id
    ON job_events (job_id, id)
    """,
    """
    CREATE TABLE IF NOT EXISTS job_files (
        job_id TEXT NOT NULL,
        file_type TEXT NOT NULL,
        payload TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY (job_id, file_type)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS stage_messages (
        message_id TEXT PRIMARY KEY,
        job_id TEXT NOT NULL,
        status TEXT NOT NULL,
        payload TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_stage_messages_status_created_at
    ON stage_messages (status, created_at, message_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        audit_id TEXT NOT NULL,
        payload TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_audit_events_created_at
    ON audit_events (created_at, id)
    """,
    """
    CREATE TABLE IF NOT EXISTS internal_users (
        user_id TEXT PRIMARY KEY,
        normalized_username TEXT NOT NULL UNIQUE,
        role TEXT NOT NULL,
        status TEXT NOT NULL,
        payload TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_internal_users_role_status
    ON internal_users (role, status, normalized_username)
    """,
    """
    CREATE TABLE IF NOT EXISTS acceptance_runs (
        run_id TEXT PRIMARY KEY,
        tier TEXT NOT NULL,
        status TEXT NOT NULL,
        decision TEXT NULL,
        payload TEXT NOT NULL,
        started_at TEXT NULL,
        finished_at TEXT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_acceptance_runs_tier_status_updated
    ON acceptance_runs (tier, status, updated_at, run_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS document_files (
        file_id TEXT PRIMARY KEY,
        payload TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_document_files_created_at
    ON document_files (created_at, file_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS file_retention_policies (
        policy_id TEXT PRIMARY KEY,
        payload TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_file_retention_policies_created_at
    ON file_retention_policies (created_at, policy_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS file_retention_cleanup_runs (
        run_id TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        payload TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_file_retention_cleanup_runs_updated_at
    ON file_retention_cleanup_runs (updated_at, run_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS file_retention_cleanup_locks (
        lock_name TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        owner_id TEXT NOT NULL,
        fencing_token INTEGER NOT NULL,
        expires_at TEXT NOT NULL,
        payload TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_file_retention_cleanup_locks_status_expires
    ON file_retention_cleanup_locks (status, expires_at)
    """,
    """
    CREATE TABLE IF NOT EXISTS document_jobs (
        job_id TEXT PRIMARY KEY,
        payload TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_document_jobs_created_at
    ON document_jobs (created_at, job_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS document_job_callback_messages (
        message_id TEXT PRIMARY KEY,
        job_id TEXT NOT NULL,
        status TEXT NOT NULL,
        dedupe_key TEXT NOT NULL UNIQUE,
        payload TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_document_job_callback_messages_status_created_at
    ON document_job_callback_messages (status, created_at, message_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_document_job_callback_messages_job_id
    ON document_job_callback_messages (job_id, status, created_at)
    """,
    """
    CREATE TABLE IF NOT EXISTS saved_views (
        view_id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        company_id TEXT NOT NULL,
        owner_user_id TEXT NOT NULL,
        page_key TEXT NOT NULL,
        position INTEGER NOT NULL,
        is_default INTEGER NOT NULL,
        payload TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_saved_views_owner_page_position
    ON saved_views (tenant_id, company_id, owner_user_id, page_key, position, view_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS terminology_releases (
        release_id TEXT NOT NULL,
        version TEXT NOT NULL,
        status TEXT NOT NULL,
        project TEXT NOT NULL,
        language_pair TEXT NOT NULL,
        content_type TEXT NOT NULL,
        payload TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (release_id, version)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_terminology_releases_scope_status
    ON terminology_releases (status, project, language_pair, content_type)
    """,
)


def initialize_schema(connection: sqlite3.Connection) -> None:
    """创建 sqlite metadata backend 当前需要的表和索引。"""

    for statement in SQLITE_SCHEMA_STATEMENTS:
        connection.execute(statement)
