# File: tests/test_database_job_repository.py
# Purpose: 校验 file/sqlite/MySQL metadata adapter 的协议行为一致。
from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.domains.acceptance.models import AcceptanceRunRecord
from app.domains.document_jobs.models import DocumentJobCallbackMessage, DocumentJobEventRecord, DocumentJobRecord
from app.domains.saved_views.models import SavedViewRecord
from app.domains.saved_views.repository import SavedViewScope
from app.domains.jobs.models import (
    JobEvent,
    JobFile,
    JobRecord,
    JobStageMessage,
    SourcePdfJobContext,
    build_source_pdf_context_patch,
    utc_now,
)
from app.domains.audit.models import AuditEvent
from app.core.config import Settings
from app.domains.files.cleanup_history import FileRetentionCleanupRunHistoryRecord, FileRetentionSignedCleanupPlan
from app.domains.files.cleanup_lock import FileRetentionCleanupLockConflict, FileRetentionCleanupLockService
from app.domains.files.models import DocumentFileRecord
from app.domains.translation.models import (
    TranslationTermEntry,
    TranslationTermMatchTraceRecord,
    TranslationTermProposalChangeRecord,
    TranslationTermProposalRecord,
)
from app.domains.users.models import InternalUserRecord
from app.infrastructure.persistence import (
    PersistenceAdapters,
    build_file_persistence_adapters,
    build_mysql_persistence_adapters,
    build_sqlite_persistence_adapters,
)
from app.services.auth import hash_password
from app.infrastructure.persistence.file import FileJobSnapshotRepository
from app.infrastructure.persistence.mysql import MysqlJobSnapshotRepository, MysqlPersistenceConfig
from app.infrastructure.persistence.sqlite import SqliteJobSnapshotRepository
from app.main import build_runtime, create_app
from app.domains.jobs.query import JobQueryService
from tests.test_fastapi_jobs_backend import (
    build_callback_checksum,
    build_callback_payload,
    build_test_runtime,
    make_zip_bytes,
    publish_default_job_resources,
)


def _mysql_config() -> MysqlPersistenceConfig:
    return MysqlPersistenceConfig(
        host="127.0.0.1",
        port=3306,
        user="md2word",
        password="",
        database="md2word_test",
    )


_CURRENT_TRANSLATION_TERM_COLUMNS = {
    "set_id",
    "language_pair",
    "version",
    "seq",
    "source_term",
    "normalized_source_term",
    "target_term",
    "recommended_translations",
    "forbidden_translations",
    "synonyms",
    "case_sensitive",
    "status",
    "priority",
    "project",
    "content_type",
    "tags",
    "maintainer",
    "domain",
    "category",
    "note",
    "created_at",
    "updated_at",
}

_TRANSLATION_TERM_MAINTAINED_COLUMNS = {
    "recommended_translations",
    "forbidden_translations",
    "synonyms",
    "project",
    "content_type",
    "tags",
    "maintainer",
}


_CURRENT_TERM_RULE_COLUMNS = {
    "term_rule_set_id",
    "version",
    "rule_id",
    "category_id",
    "source_term",
    "normalized_term",
    "scope_type",
    "scope_id",
    "scope_key",
    "current_version",
    "active",
    "rule_mode",
    "apply_scope",
    "case_sensitive",
    "enabled",
    "priority",
    "custom_html",
    "custom_markdown",
    "notes",
    "created_at",
    "updated_at",
}

_CURRENT_TERM_RULE_INDEXES = {
    "primary",
    "idx_term_rules_scoped_source",
    "idx_term_rules_category",
}


class _FakeMysqlDatabase:
    def __init__(self) -> None:
        self.jobs: dict[str, dict[str, Any]] = {}
        self.job_events: list[dict[str, Any]] = []
        self.audit_events: list[dict[str, Any]] = []
        self.acceptance_runs: dict[str, dict[str, Any]] = {}
        self.internal_users: dict[str, dict[str, Any]] = {}
        self.document_files: dict[str, dict[str, Any]] = {}
        self.file_retention_policies: dict[str, dict[str, Any]] = {}
        self.file_retention_cleanup_locks: dict[str, dict[str, Any]] = {}
        self.file_retention_cleanup_runs: dict[str, dict[str, Any]] = {}
        self.document_jobs: dict[str, dict[str, Any]] = {}
        self.document_job_callback_messages: dict[str, dict[str, Any]] = {}
        self.job_files: dict[tuple[str, str], dict[str, Any]] = {}
        self.stage_messages: dict[str, dict[str, Any]] = {}
        self.saved_views: dict[str, dict[str, Any]] = {}
        self.resource_versions: dict[tuple[str, str, str], dict[str, Any]] = {}
        self.resource_default_versions: dict[tuple[str, str], dict[str, Any]] = {}
        self.term_rule_proposals: dict[str, dict[str, Any]] = {}
        self.term_rule_categories: dict[tuple[str, str, str], dict[str, Any]] = {}
        self.term_rules: dict[tuple[str, str, str], dict[str, Any]] = {}
        self.term_rule_segments: dict[tuple[str, str, str, int], dict[str, Any]] = {}
        self.translation_term_sets: dict[str, dict[str, Any]] = {}
        self.translation_term_versions: dict[tuple[str, str], dict[str, Any]] = {}
        self.translation_terms: dict[tuple[str, str, int], dict[str, Any]] = {}
        self.translation_term_proposals: dict[str, dict[str, Any]] = {}
        self.translation_term_proposal_changes: dict[tuple[str, int], dict[str, Any]] = {}
        self.translation_term_match_traces: dict[str, dict[str, Any]] = {}
        self.next_event_id = 1
        self.created_tables: set[str] = set()
        self.table_columns: dict[str, set[str]] = {}
        self.table_indexes: dict[str, set[str]] = {}
        self.executed_sql: list[str] = []

    def connect(self) -> "_FakeMysqlConnection":
        return _FakeMysqlConnection(self)


class _FakeMysqlConnection:
    def __init__(self, database: _FakeMysqlDatabase) -> None:
        self.database = database

    def cursor(self) -> "_FakeMysqlCursor":
        return _FakeMysqlCursor(self.database)

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        pass


class _FakeMysqlCursor:
    def __init__(self, database: _FakeMysqlDatabase) -> None:
        self.database = database
        self._rows: list[dict[str, Any]] = []
        self.rowcount = 0

    def __enter__(self) -> "_FakeMysqlCursor":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        normalized = " ".join(sql.lower().split())
        self.database.executed_sql.append(normalized)
        self.rowcount = 0
        if normalized.startswith("create table"):
            for table in (
                "jobs",
                "job_events",
                "job_files",
                "stage_messages",
                "saved_views",
                "resource_versions",
                "resource_default_versions",
                "term_rule_proposals",
                "term_rule_categories",
                "term_rules",
                "term_rule_segments",
                "term_rule_review_batches",
                "term_rule_review_items",
                "term_rule_versions",
                "translation_term_sets",
                "translation_term_versions",
                "translation_terms",
                "translation_term_proposals",
                "translation_term_proposal_changes",
                "translation_term_match_traces",
                "terminology_releases",
                "audit_events",
                "acceptance_runs",
                "internal_users",
                "document_files",
                "file_retention_policies",
                "file_retention_cleanup_locks",
                "file_retention_cleanup_runs",
                "document_jobs",
                "document_job_callback_messages",
            ):
                if f" {table} " in normalized:
                    self.database.created_tables.add(table)
                    if table == "translation_terms" and table not in self.database.table_columns:
                        self.database.table_columns[table] = set(_CURRENT_TRANSLATION_TERM_COLUMNS)
                    if table == "term_rules" and table not in self.database.table_columns:
                        self.database.table_columns[table] = set(_CURRENT_TERM_RULE_COLUMNS)
                        self.database.table_indexes[table] = set(_CURRENT_TERM_RULE_INDEXES)
            self._rows = []
            return
        if normalized.startswith("select count(*) as column_count from information_schema.columns"):
            table_name, column_name = params
            existing_columns = self.database.table_columns.get(str(table_name), set())
            self._rows = [{"column_count": int(str(column_name) in existing_columns)}]
            return
        if normalized.startswith("select count(*) as index_count from information_schema.statistics"):
            table_name, index_name = params
            existing_indexes = self.database.table_indexes.get(str(table_name), set())
            self._rows = [{"index_count": int(str(index_name).lower() in existing_indexes or str(index_name) in existing_indexes)}]
            return
        if normalized.startswith("alter table term_rules modify source_term"):
            self._rows = []
            return
        if normalized.startswith("alter table term_rules add column"):
            column_name = normalized.split()[5]
            self.database.table_columns.setdefault("term_rules", set()).add(column_name)
            self._rows = []
            return
        if normalized.startswith("update term_rules set normalized_term"):
            for row in self.database.term_rules.values():
                if not row.get("normalized_term"):
                    row["normalized_term"] = row["source_term"]
            self._rows = []
            return
        if normalized.startswith("update term_rules set scope_key"):
            for row in self.database.term_rules.values():
                if not row.get("scope_key"):
                    row["scope_key"] = row.get("scope_id") or ""
            self._rows = []
            return
        if normalized.startswith("alter table term_rules drop index"):
            index_name = normalized.split()[-1]
            self.database.table_indexes.setdefault("term_rules", set()).discard(index_name)
            self._rows = []
            return
        if normalized.startswith("alter table term_rules add unique key"):
            index_name = normalized.split()[6]
            self.database.table_indexes.setdefault("term_rules", set()).add(index_name)
            self._rows = []
            return
        if normalized.startswith("alter table translation_terms add column"):
            if " if not exists " in f" {normalized} ":
                raise AssertionError("MySQL fake does not support ADD COLUMN IF NOT EXISTS")
            column_name = normalized.split()[5]
            self.database.table_columns.setdefault("translation_terms", set()).add(column_name)
            self._rows = []
            return
        if normalized.startswith("insert into jobs"):
            job_id, payload, created_at, updated_at = params
            self.database.jobs[job_id] = {
                "job_id": job_id,
                "payload": payload,
                "created_at": created_at,
                "updated_at": updated_at,
            }
            self._rows = []
            return
        if normalized.startswith("select payload from jobs where job_id"):
            row = self.database.jobs.get(params[0])
            self._rows = [{"payload": row["payload"]}] if row is not None else []
            return
        if normalized.startswith("select payload from jobs order by"):
            self._rows = [
                {"payload": row["payload"]}
                for row in sorted(self.database.jobs.values(), key=lambda item: (item["created_at"], item["job_id"]))
            ]
            return
        if normalized.startswith("insert into job_events"):
            job_id, payload, created_at = params
            self.database.job_events.append(
                {
                    "id": self.database.next_event_id,
                    "job_id": job_id,
                    "payload": payload,
                    "created_at": created_at,
                }
            )
            self.database.next_event_id += 1
            self._rows = []
            return
        if normalized.startswith("select payload from job_events where job_id"):
            rows = [row for row in self.database.job_events if row["job_id"] == params[0]]
            self._rows = [{"payload": row["payload"]} for row in sorted(rows, key=lambda item: item["id"])]
            return
        if normalized.startswith("insert into audit_events"):
            audit_id, payload, created_at = params
            self.database.audit_events.append(
                {
                    "id": self.database.next_event_id,
                    "audit_id": audit_id,
                    "payload": payload,
                    "created_at": created_at,
                }
            )
            self.database.next_event_id += 1
            self._rows = []
            return
        if normalized.startswith("select payload from audit_events order by"):
            self._rows = [
                {"payload": row["payload"]}
                for row in sorted(self.database.audit_events, key=lambda item: (item["created_at"], item["id"]))
            ]
            return
        if normalized.startswith("insert into acceptance_runs"):
            run_id, tier, run_status, decision, payload, started_at, finished_at, updated_at = params
            self.database.acceptance_runs[run_id] = {
                "run_id": run_id,
                "tier": tier,
                "status": run_status,
                "decision": decision,
                "payload": payload,
                "started_at": started_at,
                "finished_at": finished_at,
                "updated_at": updated_at,
            }
            self._rows = []
            return
        if normalized.startswith("update acceptance_runs"):
            tier, run_status, decision, payload, started_at, finished_at, updated_at, run_id = params
            self.database.acceptance_runs[run_id] = {
                "run_id": run_id,
                "tier": tier,
                "status": run_status,
                "decision": decision,
                "payload": payload,
                "started_at": started_at,
                "finished_at": finished_at,
                "updated_at": updated_at,
            }
            self._rows = []
            return
        if normalized.startswith("select payload from acceptance_runs where run_id"):
            row = self.database.acceptance_runs.get(params[0])
            self._rows = [{"payload": row["payload"]}] if row is not None else []
            return
        if normalized.startswith("select payload from acceptance_runs"):
            rows = list(self.database.acceptance_runs.values())
            param_index = 0
            if "where tier" in normalized:
                tier = params[param_index]
                param_index += 1
                rows = [row for row in rows if row["tier"] == tier]
            if "status" in normalized:
                run_status = params[param_index]
                param_index += 1
                rows = [row for row in rows if row["status"] == run_status]
            rows = sorted(rows, key=lambda item: (item["updated_at"], item["run_id"]), reverse=True)
            if " limit " in normalized:
                rows = rows[: int(params[-1])]
            self._rows = [{"payload": row["payload"]} for row in rows]
            return
        if normalized.startswith("select count(*) as count from internal_users"):
            self._rows = [{"count": len(self.database.internal_users)}]
            return
        if normalized.startswith("insert into internal_users"):
            user_id, normalized_username, user_role, user_status, payload, created_at, updated_at = params
            self.database.internal_users[user_id] = {
                "user_id": user_id,
                "normalized_username": normalized_username,
                "role": user_role,
                "status": user_status,
                "payload": payload,
                "created_at": created_at,
                "updated_at": updated_at,
            }
            self._rows = []
            return
        if normalized.startswith("update internal_users"):
            normalized_username, user_role, user_status, payload, updated_at, user_id = params
            existing = self.database.internal_users[user_id]
            self.database.internal_users[user_id] = {
                "user_id": user_id,
                "normalized_username": normalized_username,
                "role": user_role,
                "status": user_status,
                "payload": payload,
                "created_at": existing["created_at"],
                "updated_at": updated_at,
            }
            self._rows = []
            return
        if normalized.startswith("select payload from internal_users where user_id"):
            row = self.database.internal_users.get(params[0])
            self._rows = [{"payload": row["payload"]}] if row is not None else []
            return
        if normalized.startswith("select payload from internal_users where normalized_username"):
            normalized_username = params[0]
            row = next(
                (
                    item
                    for item in self.database.internal_users.values()
                    if item["normalized_username"] == normalized_username
                ),
                None,
            )
            self._rows = [{"payload": row["payload"]}] if row is not None else []
            return
        if normalized.startswith("select payload from internal_users"):
            rows = list(self.database.internal_users.values())
            if "where role" in normalized and "status" in normalized:
                user_role, user_status = params
                rows = [row for row in rows if row["role"] == user_role and row["status"] == user_status]
            elif "where role" in normalized:
                (user_role,) = params
                rows = [row for row in rows if row["role"] == user_role]
            elif "where status" in normalized:
                (user_status,) = params
                rows = [row for row in rows if row["status"] == user_status]
            self._rows = [
                {"payload": row["payload"]}
                for row in sorted(rows, key=lambda item: (item["created_at"], item["normalized_username"], item["user_id"]))
            ]
            return
        if normalized.startswith("insert into document_files"):
            file_id, payload, created_at, updated_at = params
            self.database.document_files[file_id] = {
                "file_id": file_id,
                "payload": payload,
                "created_at": created_at,
                "updated_at": updated_at,
            }
            self._rows = []
            return
        if normalized.startswith("select payload from document_files where file_id"):
            row = self.database.document_files.get(params[0])
            self._rows = [{"payload": row["payload"]}] if row is not None else []
            return
        if normalized.startswith("select payload from document_files order by"):
            self._rows = [
                {"payload": row["payload"]}
                for row in sorted(
                    self.database.document_files.values(),
                    key=lambda item: (item["created_at"], item["file_id"]),
                )
            ]
            return
        if normalized.startswith("insert into file_retention_policies"):
            policy_id, payload, created_at, updated_at = params
            self.database.file_retention_policies[policy_id] = {
                "policy_id": policy_id,
                "payload": payload,
                "created_at": created_at,
                "updated_at": updated_at,
            }
            self._rows = []
            return
        if normalized.startswith("select payload from file_retention_policies where policy_id"):
            row = self.database.file_retention_policies.get(params[0])
            self._rows = [{"payload": row["payload"]}] if row is not None else []
            return
        if normalized.startswith("select payload from file_retention_policies order by"):
            self._rows = [
                {"payload": row["payload"]}
                for row in sorted(
                    self.database.file_retention_policies.values(),
                    key=lambda item: (item["created_at"], item["policy_id"]),
                )
            ]
            return
        if normalized.startswith("insert into file_retention_cleanup_runs"):
            run_id, status, payload, created_at, updated_at = params
            self.database.file_retention_cleanup_runs[run_id] = {
                "run_id": run_id,
                "status": status,
                "payload": payload,
                "created_at": created_at,
                "updated_at": updated_at,
            }
            self._rows = []
            return
        if normalized.startswith("select payload from file_retention_cleanup_runs where run_id"):
            row = self.database.file_retention_cleanup_runs.get(params[0])
            self._rows = [{"payload": row["payload"]}] if row is not None else []
            return
        if normalized.startswith("select payload from file_retention_cleanup_runs order by"):
            self._rows = [
                {"payload": row["payload"]}
                for row in sorted(
                    self.database.file_retention_cleanup_runs.values(),
                    key=lambda item: (item["updated_at"], item["run_id"]),
                    reverse=True,
                )
            ]
            return
        if normalized.startswith("insert into file_retention_cleanup_locks"):
            lock_name, status, owner_id, fencing_token, expires_at, payload, updated_at = params
            self.database.file_retention_cleanup_locks[lock_name] = {
                "lock_name": lock_name,
                "status": status,
                "owner_id": owner_id,
                "fencing_token": fencing_token,
                "expires_at": expires_at,
                "payload": payload,
                "updated_at": updated_at,
            }
            self._rows = []
            return
        if normalized.startswith("select payload from file_retention_cleanup_locks where lock_name"):
            row = self.database.file_retention_cleanup_locks.get(params[0])
            self._rows = [{"payload": row["payload"]}] if row is not None else []
            return
        if normalized.startswith("insert into document_jobs"):
            job_id, payload, created_at, updated_at = params
            self.database.document_jobs[job_id] = {
                "job_id": job_id,
                "payload": payload,
                "created_at": created_at,
                "updated_at": updated_at,
            }
            self._rows = []
            return
        if normalized.startswith("select payload from document_jobs where job_id"):
            row = self.database.document_jobs.get(params[0])
            self._rows = [{"payload": row["payload"]}] if row is not None else []
            return
        if normalized.startswith("select payload from document_jobs order by"):
            self._rows = [
                {"payload": row["payload"]}
                for row in sorted(
                    self.database.document_jobs.values(),
                    key=lambda item: (item["created_at"], item["job_id"]),
                )
            ]
            return
        if normalized.startswith("insert ignore into document_job_callback_messages"):
            message_id, job_id, status, dedupe_key, payload, created_at, updated_at = params
            existing = next(
                (
                    row
                    for row in self.database.document_job_callback_messages.values()
                    if row["dedupe_key"] == dedupe_key
                ),
                None,
            )
            if existing is None:
                self.database.document_job_callback_messages[message_id] = {
                    "message_id": message_id,
                    "job_id": job_id,
                    "status": status,
                    "dedupe_key": dedupe_key,
                    "payload": payload,
                    "created_at": created_at,
                    "updated_at": updated_at,
                }
                self.rowcount = 1
            self._rows = []
            return
        if normalized.startswith("select payload from document_job_callback_messages where dedupe_key"):
            dedupe_key = params[0]
            row = next(
                (
                    item
                    for item in self.database.document_job_callback_messages.values()
                    if item["dedupe_key"] == dedupe_key
                ),
                None,
            )
            self._rows = [{"payload": row["payload"]}] if row is not None else []
            return
        if normalized.startswith("select payload from document_job_callback_messages where message_id"):
            row = self.database.document_job_callback_messages.get(params[0])
            self._rows = [{"payload": row["payload"]}] if row is not None else []
            return
        if normalized.startswith("select payload from document_job_callback_messages where 1 = 1"):
            rows = list(self.database.document_job_callback_messages.values())
            param_index = 0
            if "and job_id" in normalized:
                job_id = params[param_index]
                param_index += 1
                rows = [row for row in rows if row["job_id"] == job_id]
            if "and status in" in normalized:
                status_params = list(params[param_index:])
                if " limit " in normalized and status_params:
                    status_params = status_params[:-1]
                statuses = set(status_params)
                rows = [row for row in rows if row["status"] in statuses]
            rows = sorted(rows, key=lambda item: (item["created_at"], item["message_id"]))
            if " limit " in normalized and params:
                rows = rows[: int(params[-1])]
            self._rows = [{"payload": row["payload"]} for row in rows]
            return
        if "from document_job_callback_messages where status in" in normalized:
            rows = [
                row
                for row in self.database.document_job_callback_messages.values()
                if row["status"] in {"pending", "running"}
            ]
            if "and job_id" in normalized:
                rows = [row for row in rows if row["job_id"] == params[0]]
            self._rows = [
                {"payload": row["payload"]}
                for row in sorted(rows, key=lambda item: (item["created_at"], item["message_id"]))
            ]
            return
        if normalized.startswith("update document_job_callback_messages"):
            job_id, status, dedupe_key, payload, created_at, updated_at, message_id = params
            self.database.document_job_callback_messages[message_id] = {
                "message_id": message_id,
                "job_id": job_id,
                "status": status,
                "dedupe_key": dedupe_key,
                "payload": payload,
                "created_at": created_at,
                "updated_at": updated_at,
            }
            self._rows = []
            return
        if normalized.startswith("select status, count(*) as count from document_job_callback_messages"):
            counts: dict[str, int] = {}
            rows = list(self.database.document_job_callback_messages.values())
            if "where job_id" in normalized:
                rows = [row for row in rows if row["job_id"] == params[0]]
            for row in rows:
                counts[row["status"]] = counts.get(row["status"], 0) + 1
            self._rows = [{"status": status, "count": count} for status, count in counts.items()]
            return
        if normalized.startswith("insert into job_files"):
            job_id, file_type, payload, created_at = params
            self.database.job_files[(job_id, file_type)] = {
                "job_id": job_id,
                "file_type": file_type,
                "payload": payload,
                "created_at": created_at,
            }
            self._rows = []
            return
        if normalized.startswith("select payload from job_files where job_id"):
            rows = [row for row in self.database.job_files.values() if row["job_id"] == params[0]]
            self._rows = [{"payload": row["payload"]} for row in sorted(rows, key=lambda item: (item["created_at"], item["file_type"]))]
            return
        if normalized.startswith("insert into stage_messages"):
            message_id, job_id, status, payload, created_at, updated_at = params
            self.database.stage_messages[message_id] = {
                "message_id": message_id,
                "job_id": job_id,
                "status": status,
                "payload": payload,
                "created_at": created_at,
                "updated_at": updated_at,
            }
            self._rows = []
            return
        if normalized.startswith("select payload from stage_messages where message_id"):
            row = self.database.stage_messages.get(params[0])
            self._rows = [{"payload": row["payload"]}] if row is not None else []
            return
        if normalized.startswith("update stage_messages"):
            job_id, status, payload, created_at, updated_at, message_id = params
            self.database.stage_messages[message_id] = {
                "message_id": message_id,
                "job_id": job_id,
                "status": status,
                "payload": payload,
                "created_at": created_at,
                "updated_at": updated_at,
            }
            self._rows = []
            return
        if "from stage_messages where status in" in normalized:
            rows = [
                row
                for row in self.database.stage_messages.values()
                if row["status"] in {"pending", "running"}
            ]
            self._rows = [{"payload": row["payload"]} for row in sorted(rows, key=lambda item: (item["created_at"], item["message_id"]))]
            return
        if normalized.startswith("select payload from stage_messages order by"):
            self._rows = [
                {"payload": row["payload"]}
                for row in sorted(self.database.stage_messages.values(), key=lambda item: (item["created_at"], item["message_id"]))
            ]
            return
        if normalized.startswith("select status, count(*) as count from stage_messages"):
            counts: dict[str, int] = {}
            for row in self.database.stage_messages.values():
                counts[row["status"]] = counts.get(row["status"], 0) + 1
            self._rows = [{"status": status, "count": count} for status, count in counts.items()]
            return
        if normalized.startswith("delete from stage_messages"):
            self.database.stage_messages.pop(params[0], None)
            self._rows = []
            return
        if normalized.startswith("insert into resource_versions"):
            resource_type, resource_id, version, status, snapshot_hash, payload_ref, payload, created_at, updated_at = params
            self.database.resource_versions[(resource_type, resource_id, version)] = {
                "resource_type": resource_type,
                "resource_id": resource_id,
                "version": version,
                "status": status,
                "snapshot_hash": snapshot_hash,
                "payload_ref": payload_ref,
                "payload": payload,
                "created_at": created_at,
                "updated_at": updated_at,
            }
            self._rows = []
            return
        if "from resource_versions where resource_type" in normalized and "and version" in normalized:
            resource_type, resource_id, version = params
            row = self.database.resource_versions.get((resource_type, resource_id, version))
            self._rows = [row] if row is not None else []
            return
        if "from resource_versions where resource_type" in normalized and "order by created_at" in normalized:
            resource_type, resource_id = params
            rows = [
                row
                for key, row in self.database.resource_versions.items()
                if key[0] == resource_type and key[1] == resource_id
            ]
            self._rows = sorted(rows, key=lambda item: (item["created_at"], item["version"]))
            return
        if normalized.startswith("insert into resource_default_versions"):
            resource_type, resource_id, version, updated_at = params
            self.database.resource_default_versions[(resource_type, resource_id)] = {
                "resource_type": resource_type,
                "resource_id": resource_id,
                "version": version,
                "updated_at": updated_at,
            }
            self._rows = []
            return
        if "from resource_default_versions" in normalized and "join resource_versions" in normalized:
            resource_type, resource_id = params
            pointer = self.database.resource_default_versions.get((resource_type, resource_id))
            row = None
            if pointer is not None:
                row = self.database.resource_versions.get((resource_type, resource_id, pointer["version"]))
            self._rows = [row] if row is not None else []
            return
        if normalized.startswith("insert into term_rule_proposals"):
            proposal_id, proposal_status, intent, created_by, payload, created_at, updated_at = params
            self.database.term_rule_proposals[proposal_id] = {
                "id": proposal_id,
                "status": proposal_status,
                "intent": intent,
                "created_by": created_by,
                "payload": payload,
                "created_at": created_at,
                "updated_at": updated_at,
            }
            self._rows = []
            return
        if "from term_rule_proposals where id" in normalized:
            row = self.database.term_rule_proposals.get(params[0])
            self._rows = [row] if row is not None else []
            return
        if "from term_rule_proposals" in normalized:
            rows = list(self.database.term_rule_proposals.values())
            if "where status" in normalized and "created_by" in normalized:
                proposal_status, created_by = params
                rows = [row for row in rows if row["status"] == proposal_status and row["created_by"] == created_by]
            elif "where status" in normalized:
                (proposal_status,) = params
                rows = [row for row in rows if row["status"] == proposal_status]
            elif "where created_by" in normalized:
                (created_by,) = params
                rows = [row for row in rows if row["created_by"] == created_by]
            self._rows = sorted(rows, key=lambda item: (item["created_at"], item["id"]), reverse=True)
            return
        if normalized.startswith("delete from term_rule_segments"):
            term_rule_set_id, version = params
            self.database.term_rule_segments = {
                key: row
                for key, row in self.database.term_rule_segments.items()
                if key[0] != term_rule_set_id or key[1] != version
            }
            self._rows = []
            return
        if normalized.startswith("delete from term_rules"):
            term_rule_set_id, version = params
            self.database.term_rules = {
                key: row
                for key, row in self.database.term_rules.items()
                if key[0] != term_rule_set_id or key[1] != version
            }
            self._rows = []
            return
        if normalized.startswith("delete from term_rule_categories"):
            term_rule_set_id, version = params
            self.database.term_rule_categories = {
                key: row
                for key, row in self.database.term_rule_categories.items()
                if key[0] != term_rule_set_id or key[1] != version
            }
            self._rows = []
            return
        if normalized.startswith("insert into term_rule_categories"):
            term_rule_set_id, version, category_id, code, name, priority, enabled, description, created_at, updated_at = params
            self.database.term_rule_categories[(term_rule_set_id, version, category_id)] = {
                "term_rule_set_id": term_rule_set_id,
                "version": version,
                "category_id": category_id,
                "code": code,
                "name": name,
                "priority": priority,
                "enabled": enabled,
                "description": description,
                "created_at": created_at,
                "updated_at": updated_at,
            }
            self._rows = []
            return
        if normalized.startswith("insert into term_rules"):
            (
                term_rule_set_id,
                version,
                rule_id,
                category_id,
                source_term,
                normalized_term,
                scope_type,
                scope_id,
                scope_key,
                current_version,
                active,
                rule_mode,
                apply_scope,
                case_sensitive,
                enabled,
                priority,
                custom_html,
                custom_markdown,
                notes,
                created_at,
                updated_at,
            ) = params
            self.database.term_rules[(term_rule_set_id, version, rule_id)] = {
                "term_rule_set_id": term_rule_set_id,
                "version": version,
                "rule_id": rule_id,
                "category_id": category_id,
                "source_term": source_term,
                "normalized_term": normalized_term,
                "scope_type": scope_type,
                "scope_id": scope_id,
                "scope_key": scope_key,
                "current_version": current_version,
                "active": active,
                "rule_mode": rule_mode,
                "apply_scope": apply_scope,
                "case_sensitive": case_sensitive,
                "enabled": enabled,
                "priority": priority,
                "custom_html": custom_html,
                "custom_markdown": custom_markdown,
                "notes": notes,
                "created_at": created_at,
                "updated_at": updated_at,
            }
            self._rows = []
            return
        if normalized.startswith("insert into term_rule_segments"):
            term_rule_set_id, version, rule_id, seq, segment_text, render_type = params
            self.database.term_rule_segments[(term_rule_set_id, version, rule_id, seq)] = {
                "term_rule_set_id": term_rule_set_id,
                "version": version,
                "rule_id": rule_id,
                "seq": seq,
                "segment_text": segment_text,
                "render_type": render_type,
            }
            self._rows = []
            return
        if normalized.startswith("insert into translation_term_sets"):
            set_id, language_pair, default_version, draft_version, created_at, updated_at = params
            existing = self.database.translation_term_sets.get(set_id, {})
            self.database.translation_term_sets[set_id] = {
                "set_id": set_id,
                "language_pair": language_pair,
                "default_version": default_version,
                "draft_version": draft_version,
                "created_at": existing.get("created_at", created_at),
                "updated_at": updated_at,
            }
            self._rows = []
            return
        if "from translation_term_sets" in normalized and "order by language_pair" in normalized:
            self._rows = sorted(
                self.database.translation_term_sets.values(),
                key=lambda item: (item["language_pair"], item["set_id"]),
            )
            return
        if "from translation_term_sets" in normalized and "where set_id" in normalized:
            row = self.database.translation_term_sets.get(params[0])
            self._rows = [row] if row is not None else []
            return
        if "from translation_term_sets" in normalized and "where language_pair" in normalized:
            (language_pair,) = params
            row = next(
                (item for item in self.database.translation_term_sets.values() if item["language_pair"] == language_pair),
                None,
            )
            self._rows = [row] if row is not None else []
            return
        if normalized.startswith("insert into translation_term_versions"):
            (
                set_id,
                language_pair,
                version,
                version_status,
                snapshot_hash,
                term_count,
                published_by,
                published_at,
                release_note,
                created_at,
                updated_at,
            ) = params
            existing = self.database.translation_term_versions.get((set_id, version), {})
            self.database.translation_term_versions[(set_id, version)] = {
                "set_id": set_id,
                "language_pair": language_pair,
                "version": version,
                "status": version_status,
                "snapshot_hash": snapshot_hash,
                "term_count": term_count,
                "published_by": published_by,
                "published_at": published_at,
                "release_note": release_note,
                "created_at": existing.get("created_at", created_at),
                "updated_at": updated_at,
            }
            self._rows = []
            return
        if "from translation_term_versions" in normalized and "where set_id = %s" in normalized and "and version" not in normalized:
            (set_id,) = params
            rows = [
                row
                for key, row in self.database.translation_term_versions.items()
                if key[0] == set_id
            ]
            self._rows = sorted(rows, key=lambda item: (item["created_at"], item["version"]))
            return
        if "from translation_term_versions" in normalized:
            set_id, version = params
            row = self.database.translation_term_versions.get((set_id, version))
            self._rows = [row] if row is not None else []
            return
        if normalized.startswith("delete from translation_terms"):
            set_id, version = params
            self.database.translation_terms = {
                key: row
                for key, row in self.database.translation_terms.items()
                if key[0] != set_id or key[1] != version
            }
            self._rows = []
            return
        if normalized.startswith("insert into translation_terms"):
            (
                set_id,
                language_pair,
                version,
                seq,
                source_term,
                normalized_source_term,
                target_term,
                recommended_translations,
                forbidden_translations,
                synonyms,
                case_sensitive,
                term_status,
                priority,
                project,
                content_type,
                tags,
                maintainer,
                domain,
                category,
                note,
                created_at,
                updated_at,
            ) = params
            self.database.translation_terms[(set_id, version, seq)] = {
                "set_id": set_id,
                "language_pair": language_pair,
                "version": version,
                "seq": seq,
                "source_term": source_term,
                "normalized_source_term": normalized_source_term,
                "target_term": target_term,
                "recommended_translations": recommended_translations,
                "forbidden_translations": forbidden_translations,
                "synonyms": synonyms,
                "case_sensitive": case_sensitive,
                "status": term_status,
                "priority": priority,
                "project": project,
                "content_type": content_type,
                "tags": tags,
                "maintainer": maintainer,
                "domain": domain,
                "category": category,
                "note": note,
                "created_at": created_at,
                "updated_at": updated_at,
            }
            self._rows = []
            return
        if "from translation_terms" in normalized:
            set_id, version = params
            rows = [
                row
                for key, row in self.database.translation_terms.items()
                if key[0] == set_id and key[1] == version
            ]
            self._rows = sorted(rows, key=lambda item: item["seq"])
            return
        if normalized.startswith("insert into translation_term_proposals"):
            (
                proposal_id,
                proposal_status,
                submitted_by,
                source_job_id,
                source_file_id,
                observed_set_id,
                observed_version,
                reviewed_by,
                reviewed_at,
                review_note,
                published_set_id,
                published_version,
                published_at,
                created_at,
                updated_at,
            ) = params
            existing = self.database.translation_term_proposals.get(proposal_id, {})
            self.database.translation_term_proposals[proposal_id] = {
                "id": proposal_id,
                "status": proposal_status,
                "submitted_by": submitted_by,
                "source_job_id": source_job_id,
                "source_file_id": source_file_id,
                "observed_translation_term_set_id": observed_set_id,
                "observed_translation_term_version": observed_version,
                "reviewed_by": reviewed_by,
                "reviewed_at": reviewed_at,
                "review_note": review_note,
                "published_translation_term_set_id": published_set_id,
                "published_translation_term_version": published_version,
                "published_at": published_at,
                "created_at": existing.get("created_at", created_at),
                "updated_at": updated_at,
            }
            self._rows = []
            return
        if normalized.startswith("delete from translation_term_proposal_changes"):
            (proposal_id,) = params
            self.database.translation_term_proposal_changes = {
                key: row
                for key, row in self.database.translation_term_proposal_changes.items()
                if key[0] != proposal_id
            }
            self._rows = []
            return
        if normalized.startswith("insert into translation_term_proposal_changes"):
            (
                proposal_id,
                seq,
                action,
                source_term,
                normalized_source_term,
                target_term,
                case_sensitive,
                term_status,
                priority,
                domain,
                category,
                note,
                created_at,
                updated_at,
            ) = params
            self.database.translation_term_proposal_changes[(proposal_id, seq)] = {
                "proposal_id": proposal_id,
                "seq": seq,
                "action": action,
                "source_term": source_term,
                "normalized_source_term": normalized_source_term,
                "target_term": target_term,
                "case_sensitive": case_sensitive,
                "term_status": term_status,
                "priority": priority,
                "domain": domain,
                "category": category,
                "note": note,
                "created_at": created_at,
                "updated_at": updated_at,
            }
            self._rows = []
            return
        if "from translation_term_proposal_changes" in normalized:
            (proposal_id,) = params
            rows = [
                row
                for key, row in self.database.translation_term_proposal_changes.items()
                if key[0] == proposal_id
            ]
            self._rows = sorted(rows, key=lambda item: item["seq"])
            return
        if "from translation_term_proposals" in normalized:
            rows = list(self.database.translation_term_proposals.values())
            if "where id" in normalized:
                row = self.database.translation_term_proposals.get(params[0])
                self._rows = [row] if row is not None else []
                return
            if "where status" in normalized and "submitted_by" in normalized:
                proposal_status, submitted_by = params
                rows = [row for row in rows if row["status"] == proposal_status and row["submitted_by"] == submitted_by]
            elif "where status" in normalized:
                (proposal_status,) = params
                rows = [row for row in rows if row["status"] == proposal_status]
            elif "where submitted_by" in normalized:
                (submitted_by,) = params
                rows = [row for row in rows if row["submitted_by"] == submitted_by]
            self._rows = sorted(rows, key=lambda item: (item["created_at"], item["id"]), reverse=True)
            return
        if normalized.startswith("insert into translation_term_match_traces"):
            (
                trace_id,
                job_id,
                segment_id,
                batch_id,
                set_id,
                version,
                source_term,
                target_term,
                match_start,
                match_end,
                context_snippet,
                injected_to_glossary,
                provider_trace_id,
                created_at,
            ) = params
            self.database.translation_term_match_traces[trace_id] = {
                "id": trace_id,
                "job_id": job_id,
                "segment_id": segment_id,
                "batch_id": batch_id,
                "translation_term_set_id": set_id,
                "translation_term_version": version,
                "source_term": source_term,
                "target_term": target_term,
                "match_start": match_start,
                "match_end": match_end,
                "context_snippet": context_snippet,
                "injected_to_glossary": injected_to_glossary,
                "provider_trace_id": provider_trace_id,
                "created_at": created_at,
            }
            self._rows = []
            return
        if "from translation_term_match_traces" in normalized:
            (job_id,) = params
            rows = [
                row
                for row in self.database.translation_term_match_traces.values()
                if row["job_id"] == job_id
            ]
            self._rows = sorted(rows, key=lambda item: (item["created_at"], item["id"]))
            return
        if normalized.startswith("delete from saved_views"):
            tenant_id, company_id, owner_user_id, page_key = params
            self.database.saved_views = {
                view_id: row
                for view_id, row in self.database.saved_views.items()
                if not (
                    row["tenant_id"] == tenant_id
                    and row["company_id"] == company_id
                    and row["owner_user_id"] == owner_user_id
                    and row["page_key"] == page_key
                )
            }
            self._rows = []
            return
        if normalized.startswith("insert into saved_views"):
            view_id, tenant_id, company_id, owner_user_id, page_key, position, is_default, payload, created_at, updated_at = params
            self.database.saved_views[view_id] = {
                "view_id": view_id,
                "tenant_id": tenant_id,
                "company_id": company_id,
                "owner_user_id": owner_user_id,
                "page_key": page_key,
                "position": position,
                "is_default": is_default,
                "payload": payload,
                "created_at": created_at,
                "updated_at": updated_at,
            }
            self._rows = []
            return
        if "from saved_views" in normalized:
            rows = list(self.database.saved_views.values())
            if "and page_key" in normalized:
                tenant_id, company_id, owner_user_id, page_key = params
                rows = [
                    row
                    for row in rows
                    if row["tenant_id"] == tenant_id
                    and row["company_id"] == company_id
                    and row["owner_user_id"] == owner_user_id
                    and row["page_key"] == page_key
                ]
            else:
                tenant_id, company_id, owner_user_id = params
                rows = [
                    row
                    for row in rows
                    if row["tenant_id"] == tenant_id
                    and row["company_id"] == company_id
                    and row["owner_user_id"] == owner_user_id
                ]
            self._rows = [
                {"payload": row["payload"]}
                for row in sorted(rows, key=lambda item: (item["page_key"], item["position"], item["created_at"], item["view_id"]))
            ]
            if "order by position" in normalized:
                self._rows = [
                    {"payload": row["payload"]}
                    for row in sorted(rows, key=lambda item: (item["position"], item["created_at"], item["view_id"]))
                ]
            return
        raise AssertionError(f"Unexpected SQL: {sql}")

    def fetchone(self) -> dict[str, Any] | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[dict[str, Any]]:
        return list(self._rows)


class PersistenceAdapterTests(TestCase):
    def test_internal_user_repository_contract_matches_all_backends(self):
        for backend_name, build_adapters in (
            ("file", lambda path: build_file_persistence_adapters(path)),
            ("sqlite", lambda path: build_sqlite_persistence_adapters(path / "metadata.sqlite3")),
            (
                "mysql",
                lambda path: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=_FakeMysqlDatabase().connect,
                ),
            ),
        ):
            with self.subTest(backend=backend_name), TemporaryDirectory() as temp_dir:
                repository = build_adapters(Path(temp_dir)).internal_user_repository
                admin = InternalUserRecord(
                    id="user_admin",
                    username="Admin",
                    password_hash=hash_password("admin-pass", salt="admin-salt", iterations=1000),
                    role="admin",
                    status="active",
                    display_name="Admin User",
                )
                operator = InternalUserRecord(
                    id="user_operator",
                    username="operator",
                    password_hash=hash_password("operator-pass", salt="operator-salt", iterations=1000),
                    role="operator",
                    status="disabled",
                    display_name="Operator User",
                )

                repository.save_internal_user(admin)
                repository.save_internal_user(operator)
                admin.token_version += 1
                repository.save_internal_user(admin)

                self.assertEqual(repository.count_internal_users(), 2)
                self.assertEqual(repository.get_internal_user("user_admin").token_version, 2)
                self.assertEqual(repository.get_internal_user_by_username("admin").id, "user_admin")
                self.assertEqual([item.id for item in repository.list_internal_users(role="admin")], ["user_admin"])
                self.assertEqual([item.id for item in repository.list_internal_users(status="disabled")], ["user_operator"])

    def test_metadata_repository_contract_matches_file_backend(self):
        for repository_name, build_adapters in (
            ("file", lambda data_dir: build_file_persistence_adapters(data_dir / "file")),
            ("database", lambda data_dir: build_sqlite_persistence_adapters(data_dir / "metadata.sqlite3")),
            (
                "mysql",
                lambda data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=_FakeMysqlDatabase().connect,
                ),
            ),
        ):
            with self.subTest(repository=repository_name):
                with TemporaryDirectory() as temp_dir:
                    adapters = build_adapters(Path(temp_dir))

                    self._exercise_metadata_contract(adapters)

    def test_mysql_schema_bootstrap_includes_resource_versions(self):
        fake_mysql = _FakeMysqlDatabase()

        build_mysql_persistence_adapters(_mysql_config(), connect_factory=fake_mysql.connect)

        self.assertEqual(
            fake_mysql.created_tables,
            {
                "jobs",
                "job_events",
                "job_files",
                "stage_messages",
                "saved_views",
                "resource_versions",
                "resource_default_versions",
                "term_rule_proposals",
                "term_rule_categories",
                "term_rules",
                "term_rule_segments",
                "term_rule_review_batches",
                "term_rule_review_items",
                "term_rule_versions",
                "translation_term_sets",
                "translation_term_versions",
                "translation_terms",
                "translation_term_proposals",
                "translation_term_proposal_changes",
                "translation_term_match_traces",
                "terminology_releases",
                "audit_events",
                "acceptance_runs",
                "internal_users",
                "document_files",
                "file_retention_policies",
                "file_retention_cleanup_locks",
                "file_retention_cleanup_runs",
                "document_jobs",
                "document_job_callback_messages",
            },
        )

    def test_cleanup_lock_service_enforces_fencing_and_expiry(self):
        """验证 cleanup lock service 的 fencing token、过期接管和释放约束。"""

        with TemporaryDirectory() as temp_dir:
            adapters = build_file_persistence_adapters(Path(temp_dir) / "file")
            service = FileRetentionCleanupLockService(adapters.file_retention_cleanup_lock_repository)
            base_time = utc_now()

            first_lock = service.acquire(owner_id="owner-1", ttl_seconds=10, now=base_time)
            with self.assertRaises(FileRetentionCleanupLockConflict) as active_conflict:
                service.acquire(owner_id="owner-2", ttl_seconds=10, now=base_time + timedelta(seconds=5))

            second_lock = service.acquire(owner_id="owner-2", ttl_seconds=10, now=base_time + timedelta(seconds=11))
            with self.assertRaises(FileRetentionCleanupLockConflict) as refresh_conflict:
                service.refresh(
                    owner_id="owner-1",
                    fencing_token=first_lock.fencing_token,
                    ttl_seconds=10,
                    now=base_time + timedelta(seconds=12),
                )
            with self.assertRaises(FileRetentionCleanupLockConflict) as release_conflict:
                service.release(
                    owner_id="owner-1",
                    fencing_token=first_lock.fencing_token,
                    now=base_time + timedelta(seconds=12),
                )
            refreshed_lock = service.refresh(
                owner_id="owner-2",
                fencing_token=second_lock.fencing_token,
                ttl_seconds=20,
                now=base_time + timedelta(seconds=13),
            )
            released_lock = service.release(
                owner_id="owner-2",
                fencing_token=second_lock.fencing_token,
                now=base_time + timedelta(seconds=14),
            )
            third_lock = service.acquire(owner_id="owner-3", ttl_seconds=10, now=base_time + timedelta(seconds=15))

        self.assertEqual(first_lock.fencing_token, 1)
        self.assertEqual(active_conflict.exception.code, "cleanup_lock_already_held")
        self.assertEqual(second_lock.fencing_token, 2)
        self.assertEqual(refresh_conflict.exception.code, "cleanup_lock_fencing_token_mismatch")
        self.assertEqual(release_conflict.exception.code, "cleanup_lock_fencing_token_mismatch")
        self.assertEqual(refreshed_lock.owner_id, "owner-2")
        self.assertEqual(refreshed_lock.fencing_token, second_lock.fencing_token)
        self.assertEqual(released_lock.status, "released")
        self.assertEqual(third_lock.fencing_token, 3)

    def test_mysql_schema_maintenance_adds_missing_translation_term_columns_without_if_not_exists(self):
        fake_mysql = _FakeMysqlDatabase()
        fake_mysql.table_columns["translation_terms"] = (
            _CURRENT_TRANSLATION_TERM_COLUMNS - _TRANSLATION_TERM_MAINTAINED_COLUMNS
        )

        build_mysql_persistence_adapters(
            _mysql_config(),
            connect_factory=fake_mysql.connect,
        )

        self.assertTrue(_TRANSLATION_TERM_MAINTAINED_COLUMNS.issubset(fake_mysql.table_columns["translation_terms"]))
        translation_term_ddl = [
            statement
            for statement in fake_mysql.executed_sql
            if statement.startswith("alter table translation_terms add column")
        ]
        self.assertEqual(len(translation_term_ddl), len(_TRANSLATION_TERM_MAINTAINED_COLUMNS))
        self.assertTrue(all("if not exists" not in statement for statement in translation_term_ddl))
        self.assertTrue(
            any(
                statement.startswith("select count(*) as column_count from information_schema.columns")
                for statement in fake_mysql.executed_sql
            )
        )

    def test_mysql_runtime_bootstraps_term_assets_and_translation_terms(self):
        from app.main import build_runtime

        seed_yaml = (
            "schema_version: 2\n"
            "categories:\n"
            "  voltage_terms:\n"
            "    name: 电压相关\n"
            "    priority: 10\n"
            "    enabled: true\n"
            "rules:\n"
            "  - source_term: VOLD\n"
            "    category: voltage_terms\n"
            "    segments:\n"
            "      - segment_text: V\n"
            "        render_type: plain\n"
            "      - segment_text: OLD\n"
            "        render_type: subscript\n"
            "    enabled: true\n"
        )
        changed_seed_yaml = seed_yaml.replace("VOLD", "VCHANGED").replace("OLD", "CHANGED")
        terms_csv = (
            "language_pair,source_term,target_term,version\n"
            "en2zh,ADC,模数转换器,v1\n"
            "en2zh,DAC,数模转换器,v1\n"
        )
        expanded_terms_csv = (
            terms_csv
            + "ru2zh,Постоянное обратное напряжение диода,反向直流电压,v1\n"
            + "ru2zh,Постоянный обратный ток,反向漏电流,v1\n"
        )
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            seed_path = temp_root / "term_rules.v2.yaml"
            terms_path = temp_root / "translation_terms.csv"
            seed_path.write_text(seed_yaml, encoding="utf-8")
            terms_path.write_text(terms_csv, encoding="utf-8")
            fake_mysql = _FakeMysqlDatabase()
            settings = Settings(
                data_dir=temp_dir,
                jobs_repository_backend="mysql",
                term_rules_seed_path=str(seed_path),
                translation_terms_path=str(terms_path),
            )
            with patch(
                "app.main.build_persistence_adapters",
                lambda _settings: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
            ):
                runtime = build_runtime(settings)
                expected_term_rule_store = runtime.term_rule_service.repository.load()
                rogue_store = runtime.term_rule_set_version_service.yaml_codec.parse_yaml_text(changed_seed_yaml)
                runtime.term_rule_service.repository.save(rogue_store)
                seed_path.write_text(changed_seed_yaml, encoding="utf-8")
                terms_path.write_text(expanded_terms_csv, encoding="utf-8")
                fake_mysql.resource_default_versions.pop(("term_rule_set", "electronics-default"))
                fake_mysql.resource_default_versions.pop(("translation_profile", "electronics-ru2zh"))
                fake_mysql.resource_versions.pop(("translation_profile", "electronics-ru2zh", "seed"))
                restarted_runtime = build_runtime(settings)
                restarted_rule_terms = [rule.source_term for rule in restarted_runtime.term_rule_service.repository.load().rules]
                restarted_runtime_yaml_text = restarted_runtime.settings.term_rules_runtime_yaml_file.read_text(encoding="utf-8")
                snapshot = restarted_runtime.term_version_service.load_version("en2zh@v1", language_pair="en2zh")
                ru_snapshot = restarted_runtime.term_version_service.load_version("ru2zh@v1", language_pair="ru2zh")
                terms_path.unlink()
                final_runtime = build_runtime(settings)
                final_ru_snapshot = final_runtime.term_version_service.load_version("ru2zh@v1", language_pair="ru2zh")

        self.assertIsNotNone(runtime.term_rule_set_version_service)
        self.assertEqual(
            fake_mysql.resource_default_versions[("term_rule_set", "electronics-default")]["version"],
            "seed",
        )
        self.assertEqual(
            fake_mysql.resource_versions[("term_rule_set", "electronics-default", "seed")]["status"],
            "published",
        )
        self.assertEqual(len(fake_mysql.term_rule_categories), len(expected_term_rule_store.categories))
        self.assertEqual(len(fake_mysql.term_rules), len(expected_term_rule_store.rules))
        self.assertEqual(
            len(fake_mysql.term_rule_segments),
            sum(len(rule.segments) for rule in expected_term_rule_store.rules),
        )
        self.assertEqual(restarted_rule_terms, ["VOLD"])
        self.assertIn("VOLD", restarted_runtime_yaml_text)
        self.assertFalse(any(row["source_term"] == "VCHANGED" for row in fake_mysql.term_rules.values()))
        self.assertEqual(
            fake_mysql.translation_term_sets["translation-terms-en2zh"]["default_version"],
            "v1",
        )
        self.assertIn(("translation-terms-en2zh", "v1"), fake_mysql.translation_term_versions)
        self.assertEqual(len(fake_mysql.translation_terms), 4)
        self.assertEqual(len(snapshot.entries), 2)
        self.assertEqual([entry.source_term for entry in snapshot.entries], ["ADC", "DAC"])
        self.assertEqual(snapshot.entries[0].set_id, "translation-terms-en2zh")
        self.assertTrue(all(entry.normalized_source_term for entry in snapshot.entries))
        self.assertEqual(
            fake_mysql.translation_term_sets["translation-terms-ru2zh"]["default_version"],
            "v1",
        )
        self.assertIn(("translation-terms-ru2zh", "v1"), fake_mysql.translation_term_versions)
        self.assertEqual(
            [entry.source_term for entry in ru_snapshot.entries],
            ["Постоянное обратное напряжение диода", "Постоянный обратный ток"],
        )
        self.assertEqual([entry.target_term for entry in final_ru_snapshot.entries], ["反向直流电压", "反向漏电流"])
        self.assertEqual(
            fake_mysql.resource_default_versions[("translation_profile", "electronics-en2zh")]["version"],
            "seed",
        )
        self.assertEqual(
            fake_mysql.resource_default_versions[("translation_profile", "electronics-ru2zh")]["version"],
            "seed",
        )
        self.assertEqual(
            fake_mysql.resource_versions[("translation_profile", "electronics-ru2zh", "seed")]["status"],
            "published",
        )

    def test_mysql_translation_term_repository_supports_stage1_assets(self):
        fake_mysql = _FakeMysqlDatabase()
        adapters = build_mysql_persistence_adapters(
            _mysql_config(),
            connect_factory=fake_mysql.connect,
        )
        repository = adapters.translation_term_repository
        self.assertIsNotNone(repository)

        repository.replace_version(
            "en2zh",
            "v1",
            [
                TranslationTermEntry(
                    language_pair="en2zh",
                    source_term="High Speed ADC",
                    target_term="高速模数转换器",
                    version="v1",
                    priority=10,
                    domain="electronics",
                    category="converter",
                    note="seed",
                )
            ],
            "sha256:" + "a" * 64,
        )
        term_set = repository.get_set_by_language_pair("en2zh")
        version = repository.get_version("translation-terms-en2zh", "v1")
        entries = repository.load_version("en2zh", "v1")

        self.assertIsNotNone(term_set)
        self.assertEqual(term_set.set_id, "translation-terms-en2zh")
        self.assertEqual(term_set.default_version, "v1")
        self.assertIsNotNone(version)
        self.assertEqual(version.status, "published")
        self.assertEqual(version.term_count, 1)
        self.assertEqual(entries[0].normalized_source_term, "high speed adc")
        self.assertEqual(entries[0].priority, 10)

        proposal = TranslationTermProposalRecord(
            id="ttp_1",
            status="pending",
            submitted_by="operator",
            source_job_id="job_1",
            source_file_id="source_pdf",
            observed_translation_term_set_id="translation-terms-en2zh",
            observed_translation_term_version="v1",
            changes=(
                TranslationTermProposalChangeRecord(
                    proposal_id="ttp_1",
                    seq=1,
                    action="add",
                    source_term="FPGA",
                    target_term="现场可编程门阵列",
                    priority=5,
                ),
            ),
        )
        repository.save_proposal(proposal)
        loaded_proposal = repository.get_proposal("ttp_1")
        listed_proposals = repository.list_proposals(status="pending", submitted_by="operator")

        self.assertIsNotNone(loaded_proposal)
        self.assertEqual(loaded_proposal.changes[0].normalized_source_term, "fpga")
        self.assertEqual([item.id for item in listed_proposals], ["ttp_1"])

        repository.append_match_trace(
            TranslationTermMatchTraceRecord(
                id="ttmt_1",
                job_id="job_1",
                segment_id="seg_1",
                batch_id="batch_1",
                translation_term_set_id="translation-terms-en2zh",
                translation_term_version="v1",
                source_term="FPGA",
                target_term="现场可编程门阵列",
                match_start=3,
                match_end=7,
                context_snippet="use FPGA here",
                injected_to_glossary=True,
                provider_trace_id="provider_1",
            )
        )
        traces = repository.list_match_traces("job_1")

        self.assertEqual(len(traces), 1)
        self.assertTrue(traces[0].injected_to_glossary)
        self.assertEqual(traces[0].context_snippet, "use FPGA here")

    def test_document_job_status_machine_rejects_invalid_stage(self):
        with self.assertRaises(ValidationError):
            DocumentJobRecord(
                id="docjob_invalid",
                tenant_id="tenant_default",
                company_id="company_default",
                created_by="operator",
                source_file_id="file_invalid",
                template_version_id="default",
                status="succeeded",
                stage="uploaded",
            )

    def test_database_repository_persists_records_across_instances(self):
        with TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "metadata.sqlite3"
            first_adapters = build_sqlite_persistence_adapters(database_path)
            job = self._build_source_pdf_job("job_persisted")

            first_adapters.job_repository.create_job(job)
            first_adapters.job_event_repository.append_event(
                job.id,
                JobEvent(
                    stage="job_created",
                    message="created",
                    status="accepted",
                    trace_id="trace_persisted",
                ),
            )

            second_adapters = build_sqlite_persistence_adapters(database_path)
            persisted_job = second_adapters.job_repository.get_job(job.id)
            persisted_events = second_adapters.job_event_repository.list_events(job.id)

        self.assertIsNotNone(persisted_job)
        self.assertEqual(persisted_job.id, job.id)
        self.assertEqual([event.stage for event in persisted_events], ["job_created"])

    def test_jobs_api_pdf_callback_flow_uses_database_repository(self):
        with TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                mineru_api_token="token",
                mineru_callback_url="https://example.com/api/v1/mineru-callbacks/result",
                mineru_uid="mineru-user-1",
                jobs_repository_backend="database",
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("source.pdf", b"%PDF-1.4\n", "application/pdf")},
                )
                job_id = create_response.json()["job_id"]
                detail = client.get(f"/api/v1/jobs/{job_id}").json()
                callback_seed = runtime.job_repository.get_job(job_id).read_mineru_callback_seed()
                callback_payload, content = build_callback_payload(
                    batch_id="batch_test_001",
                    data_id=job_id,
                    state="done",
                    full_zip_url="https://mineru.net/result.zip",
                )
                callback_payload["checksum"] = build_callback_checksum(
                    uid="mineru-user-1",
                    seed=callback_seed,
                    content=content,
                )
                callback_response = client.post("/api/v1/mineru-callbacks/result", json=callback_payload)
                detail_response = client.get(f"/api/v1/jobs/{job_id}")

            persisted_job = runtime.job_repository.get_job(job_id)
            persisted_files = runtime.job_file_repository.list_files(job_id)
            replayable_messages = runtime.stage_message_store.list_replayable_stage_messages()

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(callback_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        self.assertIsInstance(runtime.job_repository, SqliteJobSnapshotRepository)
        self.assertIsNot(runtime.job_repository, runtime.stage_message_store)
        self.assertEqual(detail_response.json()["status"], "completed")
        self.assertEqual(persisted_job.status, "completed")
        self.assertEqual(
            {file.file_type for file in persisted_files},
            {"source_pdf", "parsed_result_package", "result_docx"},
        )
        self.assertEqual(replayable_messages, [])

    def test_jobs_api_pdf_callback_flow_uses_mysql_repository(self):
        with TemporaryDirectory() as temp_dir:
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                Path(temp_dir),
                mineru_api_token="token",
                mineru_callback_url="https://example.com/api/v1/mineru-callbacks/result",
                mineru_uid="mineru-user-1",
                jobs_repository_backend="mysql",
                repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
            )
            publish_default_job_resources(runtime)
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("source.pdf", b"%PDF-1.4\n", "application/pdf")},
                )
                job_id = create_response.json()["job_id"]
                detail = client.get(f"/api/v1/jobs/{job_id}").json()
                callback_seed = runtime.job_repository.get_job(job_id).read_mineru_callback_seed()
                callback_payload, content = build_callback_payload(
                    batch_id="batch_test_001",
                    data_id=job_id,
                    state="done",
                    full_zip_url="https://mineru.net/result.zip",
                )
                callback_payload["checksum"] = build_callback_checksum(
                    uid="mineru-user-1",
                    seed=callback_seed,
                    content=content,
                )
                callback_response = client.post("/api/v1/mineru-callbacks/result", json=callback_payload)
                detail_response = client.get(f"/api/v1/jobs/{job_id}")

            checks = runtime.health_service.build_dependency_checks()
            persisted_job = runtime.job_repository.get_job(job_id)
            persisted_files = runtime.job_file_repository.list_files(job_id)
            replayable_messages = runtime.stage_message_store.list_replayable_stage_messages()

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(callback_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        self.assertIsInstance(runtime.job_repository, MysqlJobSnapshotRepository)
        self.assertIsNot(runtime.job_repository, runtime.stage_message_store)
        self.assertEqual(detail_response.json()["status"], "completed")
        self.assertEqual(persisted_job.status, "completed")
        self.assertEqual(
            {file.file_type for file in persisted_files},
            {"source_pdf", "parsed_result_package", "result_docx"},
        )
        self.assertEqual(replayable_messages, [])
        self.assertEqual(checks["configured_repository_backend"], "mysql")
        self.assertEqual(checks["effective_repository_backend"], "mysql")
        self.assertEqual(checks["stage_message_store"], "mysql")
        self.assertTrue(checks["stage_spool_dir_exists"])

    def test_jobs_api_retry_flow_uses_database_repository(self):
        with TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_repository_backend="database",
                admin_token="secret-admin",
            )
            runtime.stage_service.conversion_entrypoint.raise_error = True
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs",
                    files={"package": ("mineru-output.zip", make_zip_bytes(), "application/zip")},
                )
                job_id = create_response.json()["job_id"]
                failed_detail = client.get(f"/api/v1/jobs/{job_id}").json()

                runtime.stage_service.conversion_entrypoint.raise_error = False
                retry_response = client.post(
                    f"/api/v1/jobs/{job_id}/retry",
                    data={"reason": "retry-database"},
                    headers={"X-Admin-Token": "secret-admin"},
                )
                completed_detail = client.get(f"/api/v1/jobs/{job_id}").json()

            persisted_job = runtime.job_repository.get_job(job_id)

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(failed_detail["status"], "failed")
        self.assertEqual(retry_response.status_code, 200)
        self.assertEqual(completed_detail["status"], "completed")
        self.assertEqual(persisted_job.status, "completed")

    def test_replay_pending_flow_uses_database_repository(self):
        with TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), jobs_repository_backend="database")
            job = JobRecord(
                id="job_database_replay",
                source_filename="source.pdf",
                status="queued",
                progress=10,
                source_kind="source_pdf",
                lifecycle_status="uploaded",
                execution_status="queued",
                source_pdf_context=SourcePdfJobContext(),
            )
            runtime.job_repository.create_job(job)
            for message in (
                JobStageMessage(
                    id="msg_database_pending",
                    job_id=job.id,
                    stage="submit_to_mineru",
                    trace_id="trace_database_pending",
                    status="pending",
                ),
                JobStageMessage(
                    id="msg_database_running",
                    job_id=job.id,
                    stage="process_callback",
                    trace_id="trace_database_running",
                    status="running",
                ),
                JobStageMessage(
                    id="msg_database_failed",
                    job_id=job.id,
                    stage="convert_package",
                    trace_id="trace_database_failed",
                    status="failed",
                ),
            ):
                runtime.stage_message_store.put_stage_message(message)
            dispatched: list[str] = []
            runtime.stage_service.dispatch_message = lambda message_id: dispatched.append(message_id)

            runtime.stage_dispatcher.replay_pending()

        self.assertEqual(dispatched, ["msg_database_pending", "msg_database_running"])

    def test_build_runtime_switches_to_database_repository_and_readiness(self):
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            settings = Settings(
                _env_file=None,
                data_dir=str(data_dir),
                jobs_repository_backend="database",
                jobs_metadata_database_path=str(data_dir / "metadata.sqlite3"),
            )
            runtime = build_runtime(settings)
            checks = runtime.health_service.build_dependency_checks()

        self.assertIsInstance(runtime.job_repository, SqliteJobSnapshotRepository)
        self.assertIsNot(runtime.job_repository, runtime.stage_message_store)
        self.assertEqual(checks["configured_repository_backend"], "database")
        self.assertEqual(checks["effective_repository_backend"], "database")
        self.assertEqual(checks["stage_message_store"], "database")
        self.assertEqual(checks["artifact_storage"], "local_file")
        self.assertTrue(checks["jobs_dir_exists"])
        self.assertTrue(checks["stage_spool_dir_exists"])

    def test_build_runtime_switches_to_mysql_repository_and_readiness(self):
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            fake_mysql = _FakeMysqlDatabase()
            settings = Settings(
                _env_file=None,
                data_dir=str(data_dir),
                jobs_repository_backend="mysql",
                jobs_mysql_database="md2word_test",
            )
            def build_fake_adapters(runtime_settings: Settings) -> PersistenceAdapters:
                runtime_settings.jobs_dir.mkdir(parents=True, exist_ok=True)
                runtime_settings.tmp_dir.mkdir(parents=True, exist_ok=True)
                return build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                )

            with patch(
                "app.main.build_persistence_adapters",
                build_fake_adapters,
            ):
                runtime = build_runtime(settings)
            checks = runtime.health_service.build_dependency_checks()

        self.assertIsInstance(runtime.job_repository, MysqlJobSnapshotRepository)
        self.assertIsNot(runtime.job_repository, runtime.stage_message_store)
        self.assertEqual(checks["configured_repository_backend"], "mysql")
        self.assertEqual(checks["effective_repository_backend"], "mysql")
        self.assertEqual(checks["stage_message_store"], "mysql")
        self.assertEqual(checks["artifact_storage"], "local_file")
        self.assertTrue(checks["jobs_dir_exists"])
        self.assertTrue(checks["stage_spool_dir_exists"])

    def test_build_runtime_keeps_file_repository_as_local_default(self):
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            settings = Settings(_env_file=None, data_dir=str(data_dir))
            runtime = build_runtime(settings)
            checks = runtime.health_service.build_dependency_checks()
            database_file_exists = settings.jobs_metadata_database_file.exists()

        self.assertEqual(settings.jobs_repository_backend, "file")
        self.assertIsInstance(runtime.job_repository, FileJobSnapshotRepository)
        self.assertEqual(checks["configured_repository_backend"], "file")
        self.assertEqual(checks["effective_repository_backend"], "file")
        self.assertEqual(checks["stage_message_store"], "file")
        self.assertFalse(database_file_exists)

    def _exercise_metadata_contract(self, adapters: PersistenceAdapters) -> None:
        job_repository = adapters.job_repository
        job_file_repository = adapters.job_file_repository
        job_event_repository = adapters.job_event_repository
        audit_event_repository = adapters.audit_event_repository
        acceptance_run_repository = adapters.acceptance_run_repository
        document_file_repository = adapters.document_file_repository
        cleanup_lock_repository = adapters.file_retention_cleanup_lock_repository
        cleanup_run_history_repository = adapters.file_retention_cleanup_run_history_repository
        document_job_repository = adapters.document_job_repository
        document_job_event_repository = adapters.document_job_event_repository
        document_job_callback_message_store = adapters.document_job_callback_message_store
        saved_view_repository = adapters.saved_view_repository
        stage_message_store = adapters.stage_message_store

        job = self._build_source_pdf_job("job_contract")
        job_repository.create_job(job)

        stored_job = job_repository.get_job(job.id)
        self.assertIsNotNone(stored_job)
        self.assertEqual(stored_job.read_mineru_batch_id(), "batch_1")
        self.assertEqual(stored_job.mineru_batch_id, "batch_1")

        updated_job = job_repository.update_job(
            job.id,
            status="parsed",
            lifecycle_status="parsed",
            **build_source_pdf_context_patch(stored_job, result_zip_url="https://mineru.net/result.zip"),
        )
        self.assertEqual(updated_job.status, "parsed")
        self.assertEqual(updated_job.read_mineru_result_zip_url(), "https://mineru.net/result.zip")
        self.assertEqual(job_repository.get_job(job.id).mineru_result_zip_url, "https://mineru.net/result.zip")

        job_file_repository.upsert_file(job.id, JobFile(file_type="source_pdf", path="input/source.pdf"))
        job_file_repository.upsert_file(job.id, JobFile(file_type="result_docx", path="output/result.docx"))
        job_file_repository.upsert_file(job.id, JobFile(file_type="source_pdf", path="input/replaced-source.pdf"))
        files_by_type = {file.file_type: file for file in job_file_repository.list_files(job.id)}
        self.assertEqual(set(files_by_type), {"source_pdf", "result_docx"})
        self.assertEqual(files_by_type["source_pdf"].path, "input/replaced-source.pdf")

        job_event_repository.append_event(
            job.id,
            JobEvent(
                stage="job_created",
                message="created",
                status="accepted",
                trace_id="trace_1",
            ),
        )
        job_event_repository.append_event(
            job.id,
            JobEvent(
                stage="translation_completed",
                message="completed",
                status="succeeded",
                trace_id="trace_2",
            ),
        )
        self.assertEqual(
            [event.stage for event in job_event_repository.list_events(job.id)],
            ["job_created", "translation_completed"],
        )

        audit_event_repository.append_audit_event(
            AuditEvent(
                audit_id="audit_contract",
                actor_id="admin",
                actor_role="admin",
                action="job.retry",
                target_type="job",
                target_id=job.id,
                reason="contract",
                details={"workflow": "retry", "attempt": 1},
                trace_id="trace_audit",
            )
        )
        audit_events = audit_event_repository.list_audit_events()
        self.assertEqual([event.action for event in audit_events], ["job.retry"])
        self.assertEqual(audit_events[0].reason, "contract")
        self.assertEqual(audit_events[0].details, {"workflow": "retry", "attempt": 1})

        acceptance_base_time = utc_now()
        unknown_acceptance_run = AcceptanceRunRecord(
            id="acceptance_p0_unknown",
            title="P0 Golden Sample",
            tier="P0",
            status="unknown",
            environment="hostdzire",
            source="golden_sample",
            report_path_or_url="tests/tmp/golden_sample_runs/run-1/report.md",
            summary="等待人工签字。",
            blockers=["admin_manual_review_pending"],
            updated_at=acceptance_base_time,
        )
        failed_acceptance_run = AcceptanceRunRecord(
            id="acceptance_p1_failed",
            title="P1 Translation",
            tier="P1",
            status="failed",
            environment="hostdzire",
            source="p1_translation",
            summary="翻译 beta gate 未通过。",
            warnings=["sample_count_low"],
            updated_at=acceptance_base_time + timedelta(seconds=1),
        )
        acceptance_run_repository.save_acceptance_run(unknown_acceptance_run)
        acceptance_run_repository.save_acceptance_run(failed_acceptance_run)
        reviewed_unknown_run = AcceptanceRunRecord.model_validate(
            unknown_acceptance_run.model_copy(
                update={
                    "reviewer": "user_admin",
                    "decision": "needs_changes",
                    "reviewed_at": acceptance_base_time + timedelta(seconds=2),
                    "review_note": "保留 unknown，等待补证据。",
                    "updated_at": acceptance_base_time + timedelta(seconds=2),
                }
            ).model_dump(mode="python")
        )
        acceptance_run_repository.save_acceptance_run(reviewed_unknown_run)
        self.assertEqual(acceptance_run_repository.get_acceptance_run("acceptance_p0_unknown").status, "unknown")
        self.assertEqual(acceptance_run_repository.get_acceptance_run("acceptance_p0_unknown").decision, "needs_changes")
        self.assertEqual(
            [record.id for record in acceptance_run_repository.list_acceptance_runs(limit=1)],
            ["acceptance_p0_unknown"],
        )
        self.assertEqual(
            [record.id for record in acceptance_run_repository.list_acceptance_runs(tier="P1")],
            ["acceptance_p1_failed"],
        )
        self.assertEqual(
            [record.id for record in acceptance_run_repository.list_acceptance_runs(status="unknown")],
            ["acceptance_p0_unknown"],
        )

        document_file = DocumentFileRecord(
            id="file_contract",
            tenant_id="tenant_default",
            company_id="company_default",
            job_id=job.id,
            file_type="source_pdf",
            storage_provider="local_object",
            bucket="local-object",
            object_key="document-files/tenant_default/file_contract/source.pdf",
            original_filename="source.pdf",
            mime_type="application/pdf",
            size_bytes=123,
            checksum_sha256="sha256:contract",
            expires_at=utc_now() + timedelta(days=90),
            created_by="operator",
        )
        document_file_repository.create_document_file(document_file)
        self.assertEqual(document_file_repository.get_document_file("file_contract").object_key, document_file.object_key)
        updated_document_file = document_file_repository.update_document_file(
            "file_contract",
            status="uploaded",
            etag="etag_contract",
        )
        self.assertEqual(updated_document_file.status, "uploaded")
        self.assertEqual(updated_document_file.etag, "etag_contract")
        self.assertEqual(
            [record.id for record in document_file_repository.list_document_files()],
            ["file_contract"],
        )

        cleanup_lock_service = FileRetentionCleanupLockService(cleanup_lock_repository)
        cleanup_lock_base_time = utc_now()
        cleanup_lock = cleanup_lock_service.acquire(
            owner_id="contract-owner",
            ttl_seconds=60,
            now=cleanup_lock_base_time,
            metadata={"source": "contract"},
        )
        refreshed_cleanup_lock = cleanup_lock_service.refresh(
            owner_id="contract-owner",
            fencing_token=cleanup_lock.fencing_token,
            ttl_seconds=90,
            now=cleanup_lock_base_time + timedelta(seconds=5),
        )
        released_cleanup_lock = cleanup_lock_service.release(
            owner_id="contract-owner",
            fencing_token=cleanup_lock.fencing_token,
            now=cleanup_lock_base_time + timedelta(seconds=10),
        )
        cleanup_lock_status = cleanup_lock_service.get_status(now=cleanup_lock_base_time + timedelta(seconds=11))
        self.assertEqual(cleanup_lock.fencing_token, 1)
        self.assertEqual(refreshed_cleanup_lock.owner_id, "contract-owner")
        self.assertEqual(released_cleanup_lock.status, "released")
        self.assertEqual(cleanup_lock_status.effective_status, "released")

        cleanup_plan = FileRetentionSignedCleanupPlan(
            plan_id="cleanup_plan_contract",
            run_id="cleanup_run_contract",
            preview_hash="sha256:preview",
            requested_file_ids=[document_file.id],
            max_files=50,
            created_at=utc_now(),
            expires_at=utc_now() + timedelta(minutes=30),
            signature="hmac-sha256:contract",
            signature_algorithm="hmac-sha256",
            safety={
                "scheduler_loop_executed": False,
                "provider_calls_executed": False,
                "s3_delete_executed": False,
                "physical_delete_executed": False,
                "physical_delete_contract_reused": True,
                "signed_plan_created": True,
            },
        )
        cleanup_run = FileRetentionCleanupRunHistoryRecord(
            run_id="cleanup_run_contract",
            status="previewed",
            action_mode="cleanup_preview",
            preview_hash="sha256:preview",
            requested_file_ids=[document_file.id],
            max_files=50,
            totals={"requested": 1, "deletable": 1},
            safety={
                "scheduler_loop_executed": False,
                "provider_calls_executed": False,
                "s3_delete_executed": False,
                "physical_delete_executed": False,
                "physical_delete_contract_reused": True,
                "audit_events_written": False,
                "history_recorded": True,
                "signed_plan_created": True,
                "signed_plan_verified": False,
            },
            cleanup_plan=cleanup_plan,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        cleanup_run_history_repository.save_run(cleanup_run)
        self.assertEqual(
            cleanup_run_history_repository.get_run("cleanup_run_contract").preview_hash,
            "sha256:preview",
        )
        self.assertEqual(
            cleanup_run_history_repository.get_run("cleanup_run_contract").cleanup_plan.plan_id,
            "cleanup_plan_contract",
        )
        executed_cleanup_run = cleanup_run.model_copy(
            update={
                "status": "executed",
                "action_mode": "cleanup_execute",
                "reason": "contract execute",
                "totals": {"requested": 1, "deleted": 1},
                "updated_at": utc_now(),
                "executed_at": utc_now(),
            }
        )
        cleanup_run_history_repository.save_run(executed_cleanup_run)
        self.assertEqual(
            cleanup_run_history_repository.get_run("cleanup_run_contract").status,
            "executed",
        )
        self.assertEqual(
            [record.run_id for record in cleanup_run_history_repository.list_runs()],
            ["cleanup_run_contract"],
        )

        document_job = DocumentJobRecord(
            id="docjob_contract",
            tenant_id="tenant_default",
            company_id="company_default",
            created_by="operator",
            source_file_id=document_file.id,
            mode="direct_pdf_to_word",
            document_language="auto",
            status="pending",
            stage="uploaded",
            progress=0,
            template_version_id="default",
            timeout_at=utc_now() + timedelta(seconds=1200),
        )
        document_job_repository.create_document_job(document_job)
        self.assertEqual(document_job_repository.get_document_job(document_job.id).source_file_id, document_file.id)
        updated_document_job = document_job_repository.update_document_job(
            document_job.id,
            status="queued",
            stage="uploaded",
            progress=0,
        )
        self.assertEqual(updated_document_job.status, "queued")
        running_document_job = document_job_repository.update_document_job_if_current(
            document_job.id,
            allowed_statuses={"queued"},
            allowed_stages={"uploaded"},
            expected_retry_count=0,
            status="running",
            stage="parsing",
            progress=10,
        )
        self.assertIsNotNone(running_document_job)
        self.assertEqual(running_document_job.stage, "parsing")
        canceled_document_job = document_job_repository.update_document_job(
            document_job.id,
            status="canceled",
            stage="canceled",
        )
        skipped_document_job_update = document_job_repository.update_document_job_if_current(
            document_job.id,
            allowed_statuses={"running"},
            allowed_stages={"parsing"},
            expected_retry_count=0,
            status="succeeded",
            stage="completed",
        )
        self.assertIsNone(skipped_document_job_update)
        self.assertEqual(canceled_document_job.status, "canceled")
        self.assertEqual(document_job_repository.get_document_job(document_job.id).status, "canceled")
        with self.assertRaises(ValidationError):
            document_job_repository.update_document_job(document_job.id, status="succeeded", stage="uploaded")
        self.assertEqual([record.id for record in document_job_repository.list_document_jobs()], [document_job.id])
        document_job_event_repository.append_document_job_event(
            document_job.id,
            DocumentJobEventRecord(
                id="event_docjob_contract",
                tenant_id="tenant_default",
                company_id="company_default",
                job_id=document_job.id,
                created_by="operator",
                stage="uploaded",
                event_type="job_created",
                message="created",
                trace_id="trace_docjob",
            ),
        )
        document_job_events = document_job_event_repository.list_document_job_events(document_job.id)
        self.assertEqual([event.event_type for event in document_job_events], ["job_created"])
        self.assertEqual(document_job_events[0].trace_id, "trace_docjob")

        callback_message = DocumentJobCallbackMessage(
            id="doccb_contract",
            job_id=document_job.id,
            job_retry_count=0,
            dedupe_key="dedupe_contract",
            payload={"state": "done", "full_zip_url": "https://mineru.net/result.zip"},
            trace_id="trace_callback",
        )
        stored_callback_message, callback_created = document_job_callback_message_store.put_or_get_callback_message(callback_message)
        duplicate_callback_message, duplicate_created = document_job_callback_message_store.put_or_get_callback_message(
            callback_message.model_copy(update={"id": "doccb_duplicate"})
        )
        self.assertTrue(callback_created)
        self.assertFalse(duplicate_created)
        self.assertEqual(duplicate_callback_message.id, stored_callback_message.id)
        self.assertEqual(
            [message.id for message in document_job_callback_message_store.list_callback_messages(document_job.id)],
            ["doccb_contract"],
        )
        self.assertEqual(document_job_callback_message_store.count_callback_messages_by_status(document_job.id)["pending"], 1)
        self.assertEqual(document_job_callback_message_store.count_callback_messages_by_status("docjob_missing")["pending"], 0)
        self.assertEqual(
            [message.id for message in document_job_callback_message_store.list_replayable_callback_messages(document_job.id)],
            ["doccb_contract"],
        )
        running_callback_message = document_job_callback_message_store.mark_callback_message_running(
            "doccb_contract",
            attempts=1,
            lease_owner="worker",
            leased_at=utc_now(),
            lease_expires_at=utc_now() + timedelta(seconds=60),
            updated_at=utc_now(),
        )
        self.assertIsNotNone(running_callback_message)
        self.assertEqual(running_callback_message.status, "running")
        processed_callback_message = document_job_callback_message_store.mark_callback_message_processed(
            "doccb_contract",
            updated_at=utc_now(),
        )
        self.assertEqual(processed_callback_message.status, "processed")
        self.assertEqual(document_job_callback_message_store.count_callback_messages_by_status()["processed"], 1)
        self.assertEqual(document_job_callback_message_store.list_replayable_callback_messages(document_job.id), [])

        pending = JobStageMessage(
            id="msg_pending",
            job_id=job.id,
            stage="convert_package",
            trace_id="trace_stage",
            status="pending",
        )
        running = JobStageMessage(
            id="msg_running",
            job_id=job.id,
            stage="submit_to_mineru",
            trace_id="trace_stage",
            status="running",
        )
        failed = JobStageMessage(
            id="msg_failed",
            job_id=job.id,
            stage="process_callback",
            trace_id="trace_stage",
            status="failed",
        )
        for message in (pending, running, failed):
            stage_message_store.put_stage_message(message)

        lease_expires_at = utc_now() + timedelta(seconds=900)
        updated_message = stage_message_store.update_stage_message(
            "msg_pending",
            status="running",
            attempts=1,
            lease_owner="in_process",
            leased_at=utc_now(),
            lease_expires_at=lease_expires_at,
        )
        self.assertEqual(updated_message.status, "running")
        self.assertEqual(updated_message.attempts, 1)
        self.assertEqual(updated_message.lease_owner, "in_process")
        self.assertEqual(updated_message.lease_expires_at, lease_expires_at)
        self.assertEqual(
            {message.id for message in stage_message_store.list_replayable_stage_messages()},
            {"msg_pending", "msg_running"},
        )
        self.assertEqual(stage_message_store.count_stage_messages_by_status(), {"pending": 0, "running": 2, "failed": 1})
        stage_message_store.delete_stage_message("msg_running")
        self.assertIsNone(stage_message_store.get_stage_message("msg_running"))
        self.assertEqual(stage_message_store.count_stage_messages_by_status(), {"pending": 0, "running": 1, "failed": 1})

        saved_view_scope = SavedViewScope(
            tenant_id="tenant_default",
            company_id="company_default",
            owner_user_id="operator",
        )
        saved_view_base_time = utc_now()
        first_saved_view = SavedViewRecord(
            view_id="savedview_jobs_first",
            tenant_id="tenant_default",
            company_id="company_default",
            owner_user_id="operator",
            page_key="jobs",
            name="Failed jobs",
            filters={"status": "failed"},
            sort="updated_at_desc",
            is_default=True,
            position=0,
            created_at=saved_view_base_time,
            updated_at=saved_view_base_time,
        )
        second_saved_view = first_saved_view.model_copy(
            update={
                "view_id": "savedview_jobs_second",
                "name": "Active jobs",
                "filters": {"status_group": "active"},
                "is_default": False,
                "position": 1,
                "created_at": saved_view_base_time + timedelta(seconds=1),
                "updated_at": saved_view_base_time + timedelta(seconds=1),
            }
        )
        qa_saved_view = first_saved_view.model_copy(
            update={
                "view_id": "savedview_qa",
                "page_key": "translation_qa",
                "name": "QA blocked",
                "filters": {"translation_qa_status": "blocked"},
                "sort": "created_at_desc",
                "is_default": False,
                "position": 0,
                "created_at": saved_view_base_time + timedelta(seconds=2),
                "updated_at": saved_view_base_time + timedelta(seconds=2),
            }
        )
        saved_view_repository.replace_saved_views_for_page(
            saved_view_scope,
            "jobs",
            [second_saved_view, first_saved_view],
        )
        saved_view_repository.replace_saved_views_for_page(saved_view_scope, "translation_qa", [qa_saved_view])
        self.assertEqual(
            [record.view_id for record in saved_view_repository.list_saved_views(saved_view_scope, "jobs")],
            ["savedview_jobs_first", "savedview_jobs_second"],
        )
        self.assertEqual(
            {record.view_id for record in saved_view_repository.list_all_saved_views(saved_view_scope)},
            {"savedview_jobs_first", "savedview_jobs_second", "savedview_qa"},
        )
        saved_view_repository.replace_saved_views_for_page(
            saved_view_scope,
            "jobs",
            [second_saved_view.model_copy(update={"position": 0})],
        )
        self.assertEqual(
            [record.view_id for record in saved_view_repository.list_saved_views(saved_view_scope, "jobs")],
            ["savedview_jobs_second"],
        )
        self.assertEqual(
            [record.view_id for record in saved_view_repository.list_saved_views(saved_view_scope, "translation_qa")],
            ["savedview_qa"],
        )

        query_service = JobQueryService(job_repository, job_file_repository, job_event_repository)
        detail_job, detail_files, detail_events = query_service.get_job_detail(job.id)
        listed_jobs, total, summary = query_service.list_jobs(
            page=1,
            page_size=10,
            status_filter="parsed",
            query_text="source",
            sort="updated_at_desc",
        )
        self.assertEqual(detail_job.id, job.id)
        self.assertEqual(len(detail_files), 2)
        self.assertEqual(len(detail_events), 2)
        self.assertEqual(total, 1)
        self.assertEqual([listed_job.id for listed_job in listed_jobs], [job.id])
        self.assertEqual(summary["parsed"], 1)

    def _build_source_pdf_job(self, job_id: str) -> JobRecord:
        return JobRecord(
            id=job_id,
            source_filename="source.pdf",
            status="uploaded",
            source_kind="source_pdf",
            lifecycle_status="uploaded",
            execution_status="idle",
            source_pdf_context=SourcePdfJobContext(batch_id="batch_1", data_id="data_1"),
        )
