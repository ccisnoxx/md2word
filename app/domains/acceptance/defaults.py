"""Default Acceptance Center summaries for deployments without imported runs."""

from __future__ import annotations

# File: app/domains/acceptance/defaults.py
# Purpose: Provide explicit starter summaries for P0/P1/P2 acceptance evidence.

from datetime import datetime

from app.domains.acceptance.models import AcceptanceRunRecord
from app.domains.resources.models import utc_now


def build_default_acceptance_runs(*, updated_at: datetime | None = None) -> list[AcceptanceRunRecord]:
    """Build non-passing starter summaries that point admins to current evidence sources."""

    now = updated_at or utc_now()
    return [
        AcceptanceRunRecord(
            id="acceptance_p0_golden_sample_current",
            title="P0 Golden Sample canonical suite",
            tier="P0",
            status="passed",
            environment="hostdzire",
            source="manual_summary:golden_sample_acceptance_report",
            report_path_or_url="docs/testing/pdf-to-word-golden-sample-acceptance-report.md",
            summary="The current Golden Sample report records the 2026-06-17 hostdzire admin signoff as the latest P0 fact.",
            blockers=[],
            warnings=["manual_summary_replace_with_latest_run_report_after_next_release"],
            updated_at=now,
        ),
        AcceptanceRunRecord(
            id="acceptance_p1_translation_current",
            title="P1 en2zh translation beta gate",
            tier="P1",
            status="unknown",
            environment="hostdzire",
            source="manual_summary:p1_translation_samples",
            report_path_or_url="tests/fixtures/p1_translation_samples/README.md",
            summary="No formal P1 translation beta run is recorded in Acceptance Center metadata yet.",
            blockers=[
                "p1_formal_regression_not_recorded",
                "p1_manual_signoff_pending",
            ],
            warnings=["requires_P1_TRANSLATION_FORMAL=1"],
            updated_at=now,
        ),
        AcceptanceRunRecord(
            id="acceptance_p2_online_gate_current",
            title="P2 internal online gate",
            tier="P2",
            status="unknown",
            environment="hostdzire",
            source="manual_summary:online_first_validation_workflow",
            report_path_or_url="docs/deploy/online-first-validation-workflow.md",
            summary="No P2 online gate report is recorded in Acceptance Center metadata yet.",
            blockers=["p2_online_gate_not_recorded"],
            warnings=["aggregates_release_check_p0_p1_preflights"],
            updated_at=now,
        ),
    ]
