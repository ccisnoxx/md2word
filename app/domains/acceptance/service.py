"""Business service for Acceptance Center run review."""

from __future__ import annotations

# File: app/domains/acceptance/service.py
# Purpose: Enforce Acceptance Center lookup and review invariants.

from fastapi import status as http_status

from app.domains.acceptance.defaults import build_default_acceptance_runs
from app.core.errors import ApiError
from app.domains.acceptance.models import (
    AcceptanceReviewDecision,
    AcceptanceRunRecord,
    AcceptanceRunStatus,
    AcceptanceRunTier,
)
from app.domains.acceptance.repository import AcceptanceRunRepositoryProtocol
from app.domains.resources.models import utc_now


class AcceptanceRunService:
    """Read acceptance run metadata and record admin review decisions."""

    def __init__(self, repository: AcceptanceRunRepositoryProtocol) -> None:
        self.repository = repository

    def list_runs(
        self,
        *,
        tier: AcceptanceRunTier | None = None,
        status: AcceptanceRunStatus | None = None,
        limit: int | None = None,
    ) -> list[AcceptanceRunRecord]:
        """Return recent acceptance runs without deriving success from missing evidence."""

        return self.repository.list_acceptance_runs(tier=tier, status=status, limit=limit)

    def get_run(self, run_id: str) -> AcceptanceRunRecord:
        """Return one acceptance run or raise a stable 404 API error."""

        record = self.repository.get_acceptance_run(run_id.strip())
        if record is None:
            raise ApiError(http_status.HTTP_404_NOT_FOUND, "not_found", "验收运行不存在。")
        return record

    def bootstrap_default_runs_if_empty(self) -> list[AcceptanceRunRecord]:
        """Seed explicit non-passing P0/P1/P2 summaries only when no runs exist."""

        if self.repository.list_acceptance_runs(limit=1):
            return []
        seeded: list[AcceptanceRunRecord] = []
        for record in build_default_acceptance_runs():
            seeded.append(self.repository.save_acceptance_run(record))
        return seeded

    def review_run(
        self,
        run_id: str,
        *,
        decision: AcceptanceReviewDecision,
        reviewer: str,
        review_note: str | None = None,
    ) -> AcceptanceRunRecord:
        """Persist a review decision without changing the evidence run status."""

        record = self.get_run(run_id)
        updated = record.model_copy(
            update={
                "reviewer": self._normalize_required_text(reviewer, "reviewer"),
                "decision": decision,
                "reviewed_at": utc_now(),
                "review_note": self._normalize_optional_text(review_note),
                "updated_at": utc_now(),
            }
        )
        normalized = AcceptanceRunRecord.model_validate(updated.model_dump(mode="python"))
        return self.repository.save_acceptance_run(normalized)

    def _normalize_required_text(self, value: str, field_name: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ApiError(http_status.HTTP_400_BAD_REQUEST, "invalid_request", f"{field_name} 不能为空。")
        return normalized

    def _normalize_optional_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None
