"""Business service for Acceptance Center run review."""

from __future__ import annotations

# File: app/domains/acceptance/service.py
# Purpose: Enforce Acceptance Center lookup and review invariants.

from datetime import datetime

from fastapi import status as http_status
from pydantic import ValidationError

from app.core.errors import ApiError
from app.domains.acceptance.defaults import build_default_acceptance_runs
from app.domains.acceptance.models import (
    AcceptanceLatestOverallStatus,
    AcceptanceLatestSummary,
    AcceptanceLatestTierSummary,
    AcceptanceReviewDecision,
    AcceptanceRunRiskLevel,
    AcceptanceRunRecord,
    AcceptanceRunStatus,
    AcceptanceRunTier,
)
from app.domains.acceptance.repository import AcceptanceRunRepositoryProtocol
from app.domains.resources.models import utc_now


class AcceptanceRunService:
    """Read acceptance run metadata and record admin review decisions."""

    TIER_ORDER: tuple[AcceptanceRunTier, ...] = ("P0", "P1", "P2")

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

    def upsert_run(
        self,
        *,
        run_id: str,
        title: str,
        tier: AcceptanceRunTier,
        status: AcceptanceRunStatus,
        environment: str,
        source: str,
        report_path_or_url: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        summary: str | None = None,
        blockers: list[str] | None = None,
        warnings: list[str] | None = None,
    ) -> AcceptanceRunRecord:
        """Persist a fresh evidence summary and clear review metadata from replaced runs."""

        try:
            record = AcceptanceRunRecord(
                id=run_id,
                title=title,
                tier=tier,
                status=status,
                environment=environment,
                source=source,
                report_path_or_url=report_path_or_url,
                started_at=started_at,
                finished_at=finished_at,
                summary=summary,
                blockers=blockers or [],
                warnings=warnings or [],
                updated_at=utc_now(),
            )
        except (ValidationError, ValueError) as exc:
            raise ApiError(http_status.HTTP_400_BAD_REQUEST, "invalid_request", str(exc)) from exc
        return self.repository.save_acceptance_run(record)

    def bootstrap_default_runs_if_empty(self) -> list[AcceptanceRunRecord]:
        """Seed explicit P0/P1/P2 starter summaries only when no runs exist."""

        if self.repository.list_acceptance_runs(limit=1):
            return []
        seeded: list[AcceptanceRunRecord] = []
        for record in build_default_acceptance_runs():
            seeded.append(self.repository.save_acceptance_run(record))
        return seeded

    def build_latest_summary(self) -> AcceptanceLatestSummary:
        """Derive a safe latest P0/P1/P2 summary without mutating evidence records."""

        records = self.repository.list_acceptance_runs()
        tiers: list[AcceptanceLatestTierSummary] = []
        missing_tiers: list[AcceptanceRunTier] = []
        blocker_count = 0
        warning_count = 0
        for tier in self.TIER_ORDER:
            latest = self._latest_run_for_tier(records, tier)
            if latest is None:
                missing_tiers.append(tier)
                tiers.append(
                    AcceptanceLatestTierSummary(
                        tier=tier,
                        run=None,
                        missing=True,
                        risk_level="unknown",
                        blockers=[f"{tier.lower()}_acceptance_evidence_missing"],
                    )
                )
                blocker_count += 1
                continue
            risk_level = self._risk_level(latest)
            blocker_count += len(latest.blockers) + (1 if latest.status == "failed" else 0)
            warning_count += len(latest.warnings) + (1 if latest.status == "unknown" else 0)
            tiers.append(
                AcceptanceLatestTierSummary(
                    tier=tier,
                    run=latest,
                    missing=False,
                    risk_level=risk_level,
                    blockers=list(latest.blockers),
                    warnings=list(latest.warnings),
                )
            )
        latest_reviewed_run = self._latest_reviewed_run(records)
        return AcceptanceLatestSummary(
            overall_status=self._overall_status(tiers),
            missing_tiers=missing_tiers,
            blocker_count=blocker_count,
            warning_count=warning_count,
            latest_reviewed_run=latest_reviewed_run,
            tiers=tiers,
        )

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

    def _latest_run_for_tier(
        self,
        records: list[AcceptanceRunRecord],
        tier: AcceptanceRunTier,
    ) -> AcceptanceRunRecord | None:
        candidates = [record for record in records if record.tier == tier]
        return sorted(candidates, key=self._run_timestamp, reverse=True)[0] if candidates else None

    def _latest_reviewed_run(self, records: list[AcceptanceRunRecord]) -> AcceptanceRunRecord | None:
        reviewed = [record for record in records if record.reviewed_at is not None]
        return sorted(reviewed, key=lambda record: record.reviewed_at or record.updated_at, reverse=True)[0] if reviewed else None

    def _run_timestamp(self, record: AcceptanceRunRecord) -> datetime:
        # Review actions update metadata, but evidence recency follows the run timeline.
        return record.finished_at or record.started_at or record.updated_at or utc_now()

    def _risk_level(self, record: AcceptanceRunRecord) -> AcceptanceRunRiskLevel:
        if record.blockers or record.status == "failed":
            return "danger"
        if record.warnings or record.status == "unknown":
            return "warning"
        return "success"

    def _overall_status(self, tiers: list[AcceptanceLatestTierSummary]) -> AcceptanceLatestOverallStatus:
        if any(tier.missing for tier in tiers):
            return "incomplete"
        if any(tier.risk_level == "danger" for tier in tiers):
            return "blocked"
        if any(tier.risk_level in {"warning", "unknown"} for tier in tiers):
            return "needs_attention"
        return "accepted"

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
