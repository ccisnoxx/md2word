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
        source_term VARCHAR(255) NOT NULL,
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
        UNIQUE KEY uq_term_rules_source (term_rule_set_id, version, source_term),
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
        case_sensitive TINYINT(1) NOT NULL,
        status VARCHAR(32) NOT NULL,
        priority INT NOT NULL,
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
