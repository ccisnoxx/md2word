# 文件：app/infrastructure/persistence/mysql/schema.py
# 用途：定义 MySQL metadata backend 的 schema bootstrap SQL。

from __future__ import annotations

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
    CREATE TABLE IF NOT EXISTS resource_version_sequences (
        resource_type VARCHAR(64) NOT NULL,
        resource_id VARCHAR(128) NOT NULL,
        next_version BIGINT UNSIGNED NOT NULL,
        updated_at VARCHAR(40) NOT NULL,
        PRIMARY KEY (resource_type, resource_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS term_rule_proposals (
        id VARCHAR(128) PRIMARY KEY,
        status VARCHAR(32) NOT NULL,
        intent VARCHAR(32) NOT NULL,
        created_by VARCHAR(128) NOT NULL,
        payload LONGTEXT NOT NULL,
        created_at VARCHAR(40) NOT NULL,
        updated_at VARCHAR(40) NOT NULL,
        KEY idx_term_rule_proposals_status_created_at (status, created_at, id),
        KEY idx_term_rule_proposals_created_by (created_by, created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS term_rule_categories (
        term_rule_set_id VARCHAR(128) NOT NULL,
        version VARCHAR(64) NOT NULL,
        category_id VARCHAR(128) NOT NULL,
        code VARCHAR(128) NOT NULL,
        name VARCHAR(255) NOT NULL,
        priority INT NOT NULL,
        enabled TINYINT(1) NOT NULL,
        description TEXT NOT NULL,
        created_at VARCHAR(40) NOT NULL,
        updated_at VARCHAR(40) NOT NULL,
        PRIMARY KEY (term_rule_set_id, version, category_id),
        KEY idx_term_rule_categories_code (term_rule_set_id, version, code)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS term_rules (
        term_rule_set_id VARCHAR(128) NOT NULL,
        version VARCHAR(64) NOT NULL,
        rule_id VARCHAR(128) NOT NULL,
        category_id VARCHAR(128) NOT NULL,
        source_term VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
        normalized_term VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
        scope_type VARCHAR(32) NOT NULL DEFAULT 'global',
        scope_id VARCHAR(128) NULL,
        scope_key VARCHAR(128) NOT NULL DEFAULT '',
        current_version INT NOT NULL DEFAULT 1,
        active TINYINT(1) NOT NULL DEFAULT 1,
        rule_mode VARCHAR(32) NOT NULL,
        apply_scope VARCHAR(32) NOT NULL,
        case_sensitive TINYINT(1) NOT NULL,
        enabled TINYINT(1) NOT NULL,
        priority INT NOT NULL,
        custom_html TEXT NULL,
        custom_markdown TEXT NULL,
        notes TEXT NOT NULL,
        created_at VARCHAR(40) NOT NULL,
        updated_at VARCHAR(40) NOT NULL,
        PRIMARY KEY (term_rule_set_id, version, rule_id),
        KEY idx_term_rules_scoped_source (term_rule_set_id, version, scope_type, scope_key, normalized_term),
        KEY idx_term_rules_category (term_rule_set_id, version, category_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS term_rule_segments (
        term_rule_set_id VARCHAR(128) NOT NULL,
        version VARCHAR(64) NOT NULL,
        rule_id VARCHAR(128) NOT NULL,
        seq INT NOT NULL,
        segment_text TEXT NOT NULL,
        render_type VARCHAR(32) NOT NULL,
        PRIMARY KEY (term_rule_set_id, version, rule_id, seq)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS term_rule_review_batches (
        id VARCHAR(128) PRIMARY KEY,
        submitted_by VARCHAR(128) NOT NULL,
        submitter_department_id VARCHAR(128) NOT NULL,
        payload LONGTEXT NOT NULL,
        created_at VARCHAR(40) NOT NULL,
        updated_at VARCHAR(40) NOT NULL,
        KEY idx_term_rule_review_batches_submitter (submitted_by, created_at, id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS term_rule_review_items (
        id VARCHAR(128) PRIMARY KEY,
        batch_id VARCHAR(128) NOT NULL,
        seq INT NOT NULL,
        status VARCHAR(32) NOT NULL,
        action VARCHAR(32) NOT NULL,
        scope_type VARCHAR(32) NOT NULL,
        scope_id VARCHAR(128) NULL,
        normalized_term VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
        payload LONGTEXT NOT NULL,
        created_at VARCHAR(40) NOT NULL,
        updated_at VARCHAR(40) NOT NULL,
        KEY idx_term_rule_review_items_batch (batch_id, seq),
        KEY idx_term_rule_review_items_status (status, created_at, id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS term_rule_versions (
        id VARCHAR(128) PRIMARY KEY,
        rule_id VARCHAR(128) NOT NULL,
        version INT NOT NULL,
        action VARCHAR(32) NOT NULL,
        scope_type VARCHAR(32) NOT NULL,
        scope_id VARCHAR(128) NULL,
        normalized_term VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
        review_item_id VARCHAR(128) NULL,
        payload LONGTEXT NOT NULL,
        created_at VARCHAR(40) NOT NULL,
        UNIQUE KEY uq_term_rule_versions_rule_version (rule_id, version),
        KEY idx_term_rule_versions_rule (rule_id, created_at, id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS translation_term_sets (
        set_id VARCHAR(128) PRIMARY KEY,
        language_pair VARCHAR(32) NOT NULL,
        default_version VARCHAR(64) NULL,
        draft_version VARCHAR(64) NULL,
        created_at VARCHAR(40) NOT NULL,
        updated_at VARCHAR(40) NOT NULL,
        UNIQUE KEY uq_translation_term_sets_language_pair (language_pair)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS translation_term_versions (
        set_id VARCHAR(128) NOT NULL,
        language_pair VARCHAR(32) NOT NULL,
        version VARCHAR(64) NOT NULL,
        status VARCHAR(32) NOT NULL,
        snapshot_hash VARCHAR(128) NOT NULL,
        term_count INT NOT NULL,
        published_by VARCHAR(128) NULL,
        published_at VARCHAR(40) NULL,
        release_note TEXT NULL,
        created_at VARCHAR(40) NOT NULL,
        updated_at VARCHAR(40) NOT NULL,
        PRIMARY KEY (set_id, version),
        KEY idx_translation_term_versions_language_pair (language_pair, status, version)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS translation_terms (
        set_id VARCHAR(128) NOT NULL,
        language_pair VARCHAR(32) NOT NULL,
        version VARCHAR(64) NOT NULL,
        seq INT NOT NULL,
        source_term VARCHAR(512) NOT NULL,
        normalized_source_term VARCHAR(512) NOT NULL,
        target_term VARCHAR(512) NOT NULL,
        recommended_translations LONGTEXT NOT NULL,
        forbidden_translations LONGTEXT NOT NULL,
        synonyms LONGTEXT NOT NULL,
        case_sensitive TINYINT(1) NOT NULL,
        status VARCHAR(32) NOT NULL,
        priority INT NOT NULL,
        project VARCHAR(128) NULL,
        content_type VARCHAR(128) NULL,
        tags LONGTEXT NOT NULL,
        maintainer VARCHAR(128) NULL,
        domain VARCHAR(128) NULL,
        category VARCHAR(128) NULL,
        note TEXT NOT NULL,
        created_at VARCHAR(40) NOT NULL,
        updated_at VARCHAR(40) NOT NULL,
        PRIMARY KEY (set_id, version, seq),
        UNIQUE KEY uq_translation_terms_normalized (set_id, version, normalized_source_term),
        KEY idx_translation_terms_source (set_id, version, source_term),
        KEY idx_translation_terms_language_pair (language_pair, version)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS terminology_releases (
        release_id VARCHAR(128) NOT NULL,
        version VARCHAR(64) NOT NULL,
        status VARCHAR(32) NOT NULL,
        project VARCHAR(128) NOT NULL,
        language_pair VARCHAR(32) NOT NULL,
        content_type VARCHAR(128) NOT NULL,
        payload LONGTEXT NOT NULL,
        created_at VARCHAR(40) NOT NULL,
        updated_at VARCHAR(40) NOT NULL,
        PRIMARY KEY (release_id, version),
        KEY idx_terminology_releases_scope_status (status, project, language_pair, content_type)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS translation_term_proposals (
        id VARCHAR(128) PRIMARY KEY,
        status VARCHAR(32) NOT NULL,
        submitted_by VARCHAR(128) NOT NULL,
        source_job_id VARCHAR(128) NULL,
        source_file_id VARCHAR(128) NULL,
        observed_translation_term_set_id VARCHAR(128) NULL,
        observed_translation_term_version VARCHAR(64) NULL,
        reviewed_by VARCHAR(128) NULL,
        reviewed_at VARCHAR(40) NULL,
        review_note TEXT NULL,
        published_translation_term_set_id VARCHAR(128) NULL,
        published_translation_term_version VARCHAR(64) NULL,
        published_at VARCHAR(40) NULL,
        created_at VARCHAR(40) NOT NULL,
        updated_at VARCHAR(40) NOT NULL,
        KEY idx_translation_term_proposals_status_created_at (status, created_at, id),
        KEY idx_translation_term_proposals_submitted_by (submitted_by, created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS translation_term_proposal_changes (
        proposal_id VARCHAR(128) NOT NULL,
        seq INT NOT NULL,
        action VARCHAR(32) NOT NULL,
        source_term VARCHAR(512) NOT NULL,
        normalized_source_term VARCHAR(512) NOT NULL,
        target_term VARCHAR(512) NULL,
        case_sensitive TINYINT(1) NULL,
        term_status VARCHAR(32) NULL,
        priority INT NULL,
        domain VARCHAR(128) NULL,
        category VARCHAR(128) NULL,
        note TEXT NULL,
        created_at VARCHAR(40) NOT NULL,
        updated_at VARCHAR(40) NOT NULL,
        PRIMARY KEY (proposal_id, seq),
        KEY idx_translation_term_proposal_changes_key (normalized_source_term)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS translation_term_match_traces (
        id VARCHAR(128) PRIMARY KEY,
        job_id VARCHAR(128) NOT NULL,
        segment_id VARCHAR(128) NULL,
        batch_id VARCHAR(128) NULL,
        translation_term_set_id VARCHAR(128) NOT NULL,
        translation_term_version VARCHAR(64) NOT NULL,
        source_term VARCHAR(512) NOT NULL,
        target_term VARCHAR(512) NOT NULL,
        match_start INT NULL,
        match_end INT NULL,
        context_snippet TEXT NULL,
        injected_to_glossary TINYINT(1) NOT NULL,
        provider_trace_id VARCHAR(128) NULL,
        created_at VARCHAR(40) NOT NULL,
        KEY idx_translation_term_match_traces_job (job_id, created_at, id)
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
    CREATE TABLE IF NOT EXISTS internal_users (
        user_id VARCHAR(128) PRIMARY KEY,
        normalized_username VARCHAR(255) NOT NULL,
        role VARCHAR(32) NOT NULL,
        status VARCHAR(32) NOT NULL,
        payload LONGTEXT NOT NULL,
        created_at VARCHAR(40) NOT NULL,
        updated_at VARCHAR(40) NOT NULL,
        UNIQUE KEY uq_internal_users_normalized_username (normalized_username),
        KEY idx_internal_users_role_status (role, status, normalized_username)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS acceptance_runs (
        run_id VARCHAR(128) PRIMARY KEY,
        tier VARCHAR(8) NOT NULL,
        status VARCHAR(32) NOT NULL,
        decision VARCHAR(32) NULL,
        payload LONGTEXT NOT NULL,
        started_at VARCHAR(40) NULL,
        finished_at VARCHAR(40) NULL,
        updated_at VARCHAR(40) NOT NULL,
        KEY idx_acceptance_runs_tier_status_updated (tier, status, updated_at, run_id)
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
    CREATE TABLE IF NOT EXISTS file_retention_policies (
        policy_id VARCHAR(128) PRIMARY KEY,
        payload LONGTEXT NOT NULL,
        created_at VARCHAR(40) NOT NULL,
        updated_at VARCHAR(40) NOT NULL,
        KEY idx_file_retention_policies_created_at (created_at, policy_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS file_retention_cleanup_runs (
        run_id VARCHAR(128) PRIMARY KEY,
        status VARCHAR(32) NOT NULL,
        payload LONGTEXT NOT NULL,
        created_at VARCHAR(40) NOT NULL,
        updated_at VARCHAR(40) NOT NULL,
        KEY idx_file_retention_cleanup_runs_updated_at (updated_at, run_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS file_retention_cleanup_locks (
        lock_name VARCHAR(128) PRIMARY KEY,
        status VARCHAR(32) NOT NULL,
        owner_id VARCHAR(255) NOT NULL,
        fencing_token BIGINT NOT NULL,
        expires_at VARCHAR(40) NOT NULL,
        payload LONGTEXT NOT NULL,
        updated_at VARCHAR(40) NOT NULL,
        KEY idx_file_retention_cleanup_locks_status_expires (status, expires_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS document_jobs (
        job_id VARCHAR(128) PRIMARY KEY,
        payload LONGTEXT NOT NULL,
        created_at VARCHAR(40) NOT NULL,
        updated_at VARCHAR(40) NOT NULL,
        quality_status VARCHAR(32) NOT NULL DEFAULT 'pending',
        review_status VARCHAR(32) NOT NULL DEFAULT 'unreviewed',
        delivery_status VARCHAR(32) NOT NULL DEFAULT 'internal_draft',
        quality_summary_json LONGTEXT NULL,
        KEY idx_document_jobs_created_at (created_at, job_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS document_job_callback_messages (
        message_id VARCHAR(128) PRIMARY KEY,
        job_id VARCHAR(128) NOT NULL,
        status VARCHAR(32) NOT NULL,
        dedupe_key VARCHAR(128) NOT NULL,
        payload LONGTEXT NOT NULL,
        created_at VARCHAR(40) NOT NULL,
        updated_at VARCHAR(40) NOT NULL,
        UNIQUE KEY uniq_document_job_callback_messages_dedupe_key (dedupe_key),
        KEY idx_document_job_callback_messages_status_created_at (status, created_at, message_id),
        KEY idx_document_job_callback_messages_job_id (job_id, status, created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS document_job_translation_batches (
        batch_id VARCHAR(128) PRIMARY KEY,
        job_id VARCHAR(128) NOT NULL,
        generation INT NOT NULL,
        status VARCHAR(32) NOT NULL,
        payload LONGTEXT NOT NULL,
        created_at VARCHAR(40) NOT NULL,
        updated_at VARCHAR(40) NOT NULL,
        KEY idx_document_job_translation_batches_job_generation (job_id, generation, status, created_at, batch_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS saved_views (
        view_id VARCHAR(128) PRIMARY KEY,
        tenant_id VARCHAR(128) NOT NULL,
        company_id VARCHAR(128) NOT NULL,
        owner_user_id VARCHAR(128) NOT NULL,
        page_key VARCHAR(64) NOT NULL,
        position INT NOT NULL,
        is_default TINYINT(1) NOT NULL,
        payload LONGTEXT NOT NULL,
        created_at VARCHAR(40) NOT NULL,
        updated_at VARCHAR(40) NOT NULL,
        KEY idx_saved_views_owner_page_position (tenant_id, company_id, owner_user_id, page_key, position, view_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
)

MYSQL_SCHEMA_MAINTENANCE_STATEMENTS: tuple[str, ...] = (
    """
    ALTER TABLE term_rules
    MODIFY source_term VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL
    """,
)

MYSQL_SCHEMA_POST_COLUMN_MAINTENANCE_STATEMENTS: tuple[str, ...] = (
    """
    UPDATE term_rules
    SET normalized_term = source_term
    WHERE normalized_term = ''
    """,
    """
    UPDATE term_rules
    SET scope_key = COALESCE(scope_id, '')
    WHERE scope_key = ''
    """,
)

MYSQL_SCHEMA_COLUMN_MAINTENANCE: tuple[tuple[str, str, str], ...] = (
    ("document_jobs", "quality_status", "quality_status VARCHAR(32) NOT NULL DEFAULT 'pending'"),
    ("document_jobs", "review_status", "review_status VARCHAR(32) NOT NULL DEFAULT 'unreviewed'"),
    ("document_jobs", "delivery_status", "delivery_status VARCHAR(32) NOT NULL DEFAULT 'internal_draft'"),
    ("document_jobs", "quality_summary_json", "quality_summary_json LONGTEXT NULL"),
    ("term_rules", "normalized_term", "normalized_term VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL DEFAULT ''"),
    ("term_rules", "scope_type", "scope_type VARCHAR(32) NOT NULL DEFAULT 'global'"),
    ("term_rules", "scope_id", "scope_id VARCHAR(128) NULL"),
    ("term_rules", "scope_key", "scope_key VARCHAR(128) NOT NULL DEFAULT ''"),
    ("term_rules", "current_version", "current_version INT NOT NULL DEFAULT 1"),
    ("term_rules", "active", "active TINYINT(1) NOT NULL DEFAULT 1"),
    ("translation_terms", "recommended_translations", "recommended_translations LONGTEXT NULL"),
    ("translation_terms", "forbidden_translations", "forbidden_translations LONGTEXT NULL"),
    ("translation_terms", "synonyms", "synonyms LONGTEXT NULL"),
    ("translation_terms", "project", "project VARCHAR(128) NULL"),
    ("translation_terms", "content_type", "content_type VARCHAR(128) NULL"),
    ("translation_terms", "tags", "tags LONGTEXT NULL"),
    ("translation_terms", "maintainer", "maintainer VARCHAR(128) NULL"),
)

MYSQL_SCHEMA_INDEX_DROP_MAINTENANCE: tuple[tuple[str, str], ...] = (
    ("term_rules", "uq_term_rules_source"),
    ("term_rules", "uq_term_rules_scoped_source"),
)

MYSQL_SCHEMA_INDEX_MAINTENANCE: tuple[tuple[str, str, str], ...] = (
    (
        "term_rules",
        "idx_term_rules_scoped_source",
        "ALTER TABLE term_rules ADD KEY idx_term_rules_scoped_source "
        "(term_rule_set_id, version, scope_type, scope_key, normalized_term)",
    ),
)


def initialize_schema(connection: Any) -> None:
    """创建 MySQL metadata backend 当前需要的表。"""

    with connection.cursor() as cursor:
        for statement in MYSQL_SCHEMA_STATEMENTS:
            cursor.execute(statement)
        for statement in MYSQL_SCHEMA_MAINTENANCE_STATEMENTS:
            cursor.execute(statement)
        for table_name, column_name, column_definition in MYSQL_SCHEMA_COLUMN_MAINTENANCE:
            _ensure_column(cursor, table_name, column_name, column_definition)
        for statement in MYSQL_SCHEMA_POST_COLUMN_MAINTENANCE_STATEMENTS:
            cursor.execute(statement)
        for table_name, index_name in MYSQL_SCHEMA_INDEX_DROP_MAINTENANCE:
            _drop_index_if_exists(cursor, table_name, index_name)
        for table_name, index_name, statement in MYSQL_SCHEMA_INDEX_MAINTENANCE:
            _ensure_index(cursor, table_name, index_name, statement)


def _ensure_column(cursor: Any, table_name: str, column_name: str, column_definition: str) -> None:
    """MySQL 版本差异下用 information_schema 保持列级 schema maintenance 幂等。"""

    cursor.execute(
        """
        SELECT COUNT(*) AS column_count
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND COLUMN_NAME = %s
        """,
        (table_name, column_name),
    )
    row = cursor.fetchone()
    if _column_count(row) > 0:
        return
    cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_definition}")


def _drop_index_if_exists(cursor: Any, table_name: str, index_name: str) -> None:
    if not _index_exists(cursor, table_name, index_name):
        return
    cursor.execute(f"ALTER TABLE {table_name} DROP INDEX {index_name}")


def _ensure_index(cursor: Any, table_name: str, index_name: str, statement: str) -> None:
    if _index_exists(cursor, table_name, index_name):
        return
    cursor.execute(statement)


def _index_exists(cursor: Any, table_name: str, index_name: str) -> bool:
    cursor.execute(
        """
        SELECT COUNT(*) AS index_count
        FROM INFORMATION_SCHEMA.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND INDEX_NAME = %s
        """,
        (table_name, index_name),
    )
    return _count(row=cursor.fetchone(), key="index_count") > 0


def _column_count(row: Any) -> int:
    return _count(row=row, key="column_count")


def _count(*, row: Any, key: str) -> int:
    if row is None:
        return 0
    if isinstance(row, dict):
        return int(row.get(key) or 0)
    if isinstance(row, (list, tuple)) and row:
        return int(row[0] or 0)
    return int(row or 0)
