from __future__ import annotations

# File: app/infrastructure/persistence/mysql/term_rule_review.py
# Purpose: Persist term rule review batches, items, and effective-rule history in MySQL.

import json
from typing import Any

from app.domains.term_rules.models import (
    TermRuleReviewBatchRecord,
    TermRuleReviewItemRecord,
    TermRuleReviewItemStatus,
    TermRuleVersionRecord,
)
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend


class MysqlTermRuleReviewRepository:
    """MySQL adapter for the term-rule review MVP batch/item workflow."""

    def __init__(self, backend: MysqlPersistenceBackend) -> None:
        self.backend = backend

    def save_batch(self, batch: TermRuleReviewBatchRecord) -> TermRuleReviewBatchRecord:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO term_rule_review_batches
                        (id, submitted_by, submitter_department_id, payload, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        submitted_by = VALUES(submitted_by),
                        submitter_department_id = VALUES(submitter_department_id),
                        payload = VALUES(payload),
                        created_at = VALUES(created_at),
                        updated_at = VALUES(updated_at)
                    """,
                    (
                        batch.id,
                        batch.submitted_by,
                        batch.submitter_department_id,
                        batch.model_dump_json(),
                        batch.created_at.isoformat(),
                        batch.updated_at.isoformat(),
                    ),
                )
        return batch

    def get_batch(self, batch_id: str) -> TermRuleReviewBatchRecord | None:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload FROM term_rule_review_batches WHERE id = %s", (batch_id,))
                row = cursor.fetchone()
        return self._load_batch(row) if row is not None else None

    def list_batches(
        self,
        *,
        submitted_by: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[TermRuleReviewBatchRecord], int]:
        clauses: list[str] = []
        params: list[Any] = []
        if submitted_by is not None:
            clauses.append("submitted_by = %s")
            params.append(submitted_by)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        offset = (page - 1) * page_size
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT COUNT(*) AS total FROM term_rule_review_batches {where_sql}",
                    tuple(params),
                )
                total = self._count(cursor.fetchone())
                cursor.execute(
                    f"""
                    SELECT payload
                    FROM term_rule_review_batches
                    {where_sql}
                    ORDER BY created_at DESC, id DESC
                    LIMIT %s OFFSET %s
                    """,
                    tuple([*params, page_size, offset]),
                )
                rows = cursor.fetchall()
        return [self._load_batch(row) for row in rows], total

    def save_item(self, item: TermRuleReviewItemRecord) -> TermRuleReviewItemRecord:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO term_rule_review_items
                        (id, batch_id, seq, status, action, scope_type, scope_id, normalized_term, payload, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        batch_id = VALUES(batch_id),
                        seq = VALUES(seq),
                        status = VALUES(status),
                        action = VALUES(action),
                        scope_type = VALUES(scope_type),
                        scope_id = VALUES(scope_id),
                        normalized_term = VALUES(normalized_term),
                        payload = VALUES(payload),
                        created_at = VALUES(created_at),
                        updated_at = VALUES(updated_at)
                    """,
                    (
                        item.id,
                        item.batch_id,
                        item.seq,
                        item.status.value,
                        item.action.value,
                        item.scope_type.value,
                        item.scope_id,
                        item.normalized_term,
                        item.model_dump_json(),
                        item.created_at.isoformat(),
                        item.updated_at.isoformat(),
                    ),
                )
        return item

    def get_item(self, item_id: str) -> TermRuleReviewItemRecord | None:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload FROM term_rule_review_items WHERE id = %s", (item_id,))
                row = cursor.fetchone()
        return self._load_item(row) if row is not None else None

    def list_items(
        self,
        *,
        batch_id: str | None = None,
        status: TermRuleReviewItemStatus | None = None,
    ) -> list[TermRuleReviewItemRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if batch_id is not None:
            clauses.append("batch_id = %s")
            params.append(batch_id)
        if status is not None:
            clauses.append("status = %s")
            params.append(status.value)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT payload
                    FROM term_rule_review_items
                    {where_sql}
                    ORDER BY created_at DESC, batch_id DESC, seq ASC
                    """,
                    tuple(params),
                )
                rows = cursor.fetchall()
        return [self._load_item(row) for row in rows]

    def save_version(self, version: TermRuleVersionRecord) -> TermRuleVersionRecord:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO term_rule_versions
                        (id, rule_id, version, action, scope_type, scope_id, normalized_term,
                         review_item_id, payload, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        rule_id = VALUES(rule_id),
                        version = VALUES(version),
                        action = VALUES(action),
                        scope_type = VALUES(scope_type),
                        scope_id = VALUES(scope_id),
                        normalized_term = VALUES(normalized_term),
                        review_item_id = VALUES(review_item_id),
                        payload = VALUES(payload),
                        created_at = VALUES(created_at)
                    """,
                    (
                        version.id,
                        version.rule_id,
                        version.version,
                        version.action.value,
                        version.scope_type.value,
                        version.scope_id,
                        version.normalized_term,
                        version.review_item_id,
                        version.model_dump_json(),
                        version.created_at.isoformat(),
                    ),
                )
        return version

    def list_versions(self, *, rule_id: str | None = None) -> list[TermRuleVersionRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if rule_id is not None:
            clauses.append("rule_id = %s")
            params.append(rule_id)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT payload
                    FROM term_rule_versions
                    {where_sql}
                    ORDER BY created_at DESC, version DESC, id DESC
                    """,
                    tuple(params),
                )
                rows = cursor.fetchall()
        return [self._load_version(row) for row in rows]

    @staticmethod
    def _load_batch(row: dict[str, Any]) -> TermRuleReviewBatchRecord:
        return TermRuleReviewBatchRecord.model_validate(json.loads(row["payload"]))

    @staticmethod
    def _load_item(row: dict[str, Any]) -> TermRuleReviewItemRecord:
        return TermRuleReviewItemRecord.model_validate(json.loads(row["payload"]))

    @staticmethod
    def _load_version(row: dict[str, Any]) -> TermRuleVersionRecord:
        return TermRuleVersionRecord.model_validate(json.loads(row["payload"]))

    @staticmethod
    def _count(row: Any) -> int:
        if row is None:
            return 0
        if isinstance(row, dict):
            return int(row.get("total") or 0)
        if isinstance(row, (tuple, list)) and row:
            return int(row[0] or 0)
        return int(row or 0)
