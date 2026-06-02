from __future__ import annotations

# app/infrastructure/persistence/mysql/term_rule_proposals.py: MySQL backend 的术语建议审核流 adapter。

import json
from typing import Any

from app.domains.term_rules.models import TermRuleProposalRecord, TermRuleProposalStatus
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend


class MysqlTermRuleProposalRepository:
    """用 MySQL backend 持久化 Term Rule Proposal。"""

    def __init__(self, backend: MysqlPersistenceBackend) -> None:
        self.backend = backend

    def save_proposal(self, proposal: TermRuleProposalRecord) -> TermRuleProposalRecord:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO term_rule_proposals
                        (id, status, intent, created_by, payload, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        status = VALUES(status),
                        intent = VALUES(intent),
                        created_by = VALUES(created_by),
                        payload = VALUES(payload),
                        created_at = VALUES(created_at),
                        updated_at = VALUES(updated_at)
                    """,
                    (
                        proposal.id,
                        proposal.status.value,
                        proposal.intent.value,
                        proposal.created_by,
                        proposal.model_dump_json(),
                        proposal.created_at.isoformat(),
                        proposal.updated_at.isoformat(),
                    ),
                )
        return proposal

    def get_proposal(self, proposal_id: str) -> TermRuleProposalRecord | None:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT payload
                    FROM term_rule_proposals
                    WHERE id = %s
                    """,
                    (proposal_id,),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return self._load_proposal(row)

    def list_proposals(
        self,
        *,
        status: TermRuleProposalStatus | None = None,
        created_by: str | None = None,
    ) -> list[TermRuleProposalRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if status is not None:
            clauses.append("status = %s")
            params.append(status.value)
        if created_by is not None:
            clauses.append("created_by = %s")
            params.append(created_by)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT payload
                    FROM term_rule_proposals
                    {where_sql}
                    ORDER BY created_at DESC, id DESC
                    """,
                    tuple(params),
                )
                rows = cursor.fetchall()
        return [self._load_proposal(row) for row in rows]

    @staticmethod
    def _load_proposal(row: dict[str, Any]) -> TermRuleProposalRecord:
        return TermRuleProposalRecord.model_validate(json.loads(row["payload"]))
