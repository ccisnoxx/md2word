from __future__ import annotations

# File: scripts/ops/repair_term_rule_draft_from_default.py
# Purpose: Safely rebuild a Term Rule Set draft from its default version and remove smoke-test proposal residue.

import argparse
import json
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.runtime import AppRuntime
from app.domains.audit.models import ActorContext
from app.domains.term_rules.models import TermRuleProposalStatus, TermRulesStore, utc_now
from app.domains.term_rules.versioning_service import DEFAULT_TERM_RULE_SET_ID
from app.main import build_runtime


@dataclass(slots=True)
class TermRuleDraftRepairReport:
    set_id: str
    applied: bool
    default_version: str | None
    before_draft_snapshot_hash: str | None
    expected_draft_hash: str | None
    before_draft_rule_count: int
    before_draft_enabled_rule_count: int
    default_rule_count: int
    default_enabled_rule_count: int
    before_diff_removed: int
    before_diff_added: int
    before_diff_updated: int
    approved_unpublished_count: int
    smoke_proposal_ids: list[str]
    preserved_proposal_ids: list[str]
    after_draft_snapshot_hash: str | None = None
    after_draft_rule_count: int | None = None
    after_draft_enabled_rule_count: int | None = None
    after_diff_removed: int | None = None
    after_diff_added: int | None = None
    after_diff_updated: int | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.warnings and (
            not self.applied
            or (
                self.after_draft_rule_count == self.default_rule_count
                and self.after_draft_enabled_rule_count == self.default_enabled_rule_count
                and self.after_diff_removed == 0
                and self.after_diff_added == 0
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "set_id": self.set_id,
            "applied": self.applied,
            "ok": self.ok,
            "default_version": self.default_version,
            "before_draft_snapshot_hash": self.before_draft_snapshot_hash,
            "expected_draft_hash": self.expected_draft_hash,
            "before_draft_rule_count": self.before_draft_rule_count,
            "before_draft_enabled_rule_count": self.before_draft_enabled_rule_count,
            "default_rule_count": self.default_rule_count,
            "default_enabled_rule_count": self.default_enabled_rule_count,
            "before_diff_removed": self.before_diff_removed,
            "before_diff_added": self.before_diff_added,
            "before_diff_updated": self.before_diff_updated,
            "approved_unpublished_count": self.approved_unpublished_count,
            "smoke_proposal_ids": self.smoke_proposal_ids,
            "preserved_proposal_ids": self.preserved_proposal_ids,
            "after_draft_snapshot_hash": self.after_draft_snapshot_hash,
            "after_draft_rule_count": self.after_draft_rule_count,
            "after_draft_enabled_rule_count": self.after_draft_enabled_rule_count,
            "after_diff_removed": self.after_diff_removed,
            "after_diff_added": self.after_diff_added,
            "after_diff_updated": self.after_diff_updated,
            "warnings": self.warnings,
        }


def repair_term_rule_draft_from_default(
    runtime: AppRuntime,
    *,
    set_id: str = DEFAULT_TERM_RULE_SET_ID,
    drop_source_prefix: str = "SMOKE_TR_",
    expected_draft_hash: str | None = None,
    apply: bool = False,
    actor_id: str = "ops:repair_term_rule_draft",
    trace_id: str = "ops-repair-term-rule-draft",
) -> TermRuleDraftRepairReport:
    """Rebuild the editable draft from the default version, optionally cleaning smoke proposals."""

    version_service = runtime.term_rule_set_version_service
    proposal_service = runtime.term_rule_proposal_service
    if version_service is None or proposal_service is None:
        raise RuntimeError("Term Rule Set draft repair requires JOBS_REPOSITORY_BACKEND=mysql.")

    detail = version_service.get_set_detail(set_id)
    draft = version_service.get_draft(set_id)
    before_diff = version_service.build_diff(set_id)
    default_store = _default_store(version_service, set_id)
    default_rule_count, default_enabled_rule_count = version_service._count_rules(default_store)
    approved = proposal_service.list_approved_unpublished_proposals(set_id)
    smoke = [item for item in approved if item.source_term.startswith(drop_source_prefix)]
    preserved = [item for item in approved if item not in smoke]
    warnings: list[str] = []
    if preserved:
        warnings.append(
            f"{len(preserved)} approved unpublished proposal(s) do not match prefix {drop_source_prefix!r} and will be preserved."
        )

    report = TermRuleDraftRepairReport(
        set_id=set_id,
        applied=False,
        default_version=detail.default_version,
        before_draft_snapshot_hash=draft.snapshot_hash,
        expected_draft_hash=expected_draft_hash,
        before_draft_rule_count=draft.rule_count,
        before_draft_enabled_rule_count=draft.enabled_rule_count,
        default_rule_count=default_rule_count,
        default_enabled_rule_count=default_enabled_rule_count,
        before_diff_removed=before_diff.summary.removed,
        before_diff_added=before_diff.summary.added,
        before_diff_updated=before_diff.summary.updated,
        approved_unpublished_count=len(approved),
        smoke_proposal_ids=[item.id for item in smoke],
        preserved_proposal_ids=[item.id for item in preserved],
        warnings=warnings,
    )
    if not apply:
        return report

    if not expected_draft_hash:
        raise ValueError("--expected-draft-hash is required when --apply is used.")
    if draft.snapshot_hash != expected_draft_hash:
        raise ValueError(
            f"Draft snapshot changed; expected {expected_draft_hash}, got {draft.snapshot_hash}. Re-run dry-run first."
        )

    updated_draft = version_service.update_draft(
        set_id,
        default_store,
        expected_snapshot_hash=expected_draft_hash,
    )
    _reject_smoke_proposals(
        runtime,
        smoke,
        actor_id=actor_id,
        drop_source_prefix=drop_source_prefix,
        trace_id=trace_id,
    )
    _record_draft_repair_audit(
        runtime,
        set_id=set_id,
        actor_id=actor_id,
        trace_id=trace_id,
        cleaned_smoke_proposal_count=len(smoke),
        before_snapshot_hash=draft.snapshot_hash,
        after_snapshot_hash=updated_draft.snapshot_hash,
    )
    after_diff = version_service.build_diff(set_id)
    return replace(
        report,
        applied=True,
        after_draft_snapshot_hash=updated_draft.snapshot_hash,
        after_draft_rule_count=updated_draft.rule_count,
        after_draft_enabled_rule_count=updated_draft.enabled_rule_count,
        after_diff_removed=after_diff.summary.removed,
        after_diff_added=after_diff.summary.added,
        after_diff_updated=after_diff.summary.updated,
    )


def _default_store(version_service: Any, set_id: str) -> TermRulesStore:
    default_record = version_service._default_record(set_id)
    if default_record is None:
        raise FileNotFoundError(f"Term Rule Set has no default version: {set_id}")
    return version_service._store_from_record(default_record)


def _reject_smoke_proposals(
    runtime: AppRuntime,
    proposals: list[Any],
    *,
    actor_id: str,
    drop_source_prefix: str,
    trace_id: str,
) -> None:
    if not proposals or runtime.term_rule_proposal_service is None:
        return
    now = utc_now()
    reason = f"ops cleanup: remove approved smoke proposals with prefix {drop_source_prefix}"
    for proposal in proposals:
        updated = proposal.model_copy(
            update={
                "status": TermRuleProposalStatus.REJECTED,
                "reviewed_by": actor_id,
                "reviewed_at": now,
                "review_comment": reason,
                "merged_term_rule_set_id": None,
                "merged_draft_snapshot_hash": None,
                "updated_at": now,
            }
        )
        runtime.term_rule_proposal_service.repository.save_proposal(updated)
    if runtime.audit_service is not None:
        runtime.audit_service.record(
            actor=ActorContext(actor_id=actor_id, actor_role="admin", source="open"),
            action="term_rule_proposal.cleanup_smoke",
            target_type="term_rule_proposal",
            target_id=",".join(proposal.id for proposal in proposals),
            trace_id=trace_id,
            reason=reason,
            details={
                "count": len(proposals),
                "source_prefix": drop_source_prefix,
                "proposal_ids": [proposal.id for proposal in proposals],
            },
        )


def _record_draft_repair_audit(
    runtime: AppRuntime,
    *,
    set_id: str,
    actor_id: str,
    trace_id: str,
    cleaned_smoke_proposal_count: int,
    before_snapshot_hash: str | None,
    after_snapshot_hash: str | None,
) -> None:
    if runtime.audit_service is None:
        return
    runtime.audit_service.record(
        actor=ActorContext(actor_id=actor_id, actor_role="admin", source="open"),
        action="term_rule_set.repair_draft_from_default",
        target_type="term_rule_set",
        target_id=set_id,
        trace_id=trace_id,
        reason="ops repair: rebuild draft from current default version",
        details={
            "cleaned_smoke_proposal_count": cleaned_smoke_proposal_count,
            "before_snapshot_hash": before_snapshot_hash,
            "after_snapshot_hash": after_snapshot_hash,
        },
    )


def format_pretty_report(report: TermRuleDraftRepairReport) -> str:
    lines = [
        "Term Rule Set draft repair report",
        f"set_id: {report.set_id}",
        f"applied: {report.applied}",
        f"ok: {report.ok}",
        f"default_version: {report.default_version or '-'}",
        f"before_draft_snapshot_hash: {report.before_draft_snapshot_hash or '-'}",
        f"expected_draft_hash: {report.expected_draft_hash or '-'}",
        f"before_draft_rule_count: {report.before_draft_rule_count}",
        f"before_draft_enabled_rule_count: {report.before_draft_enabled_rule_count}",
        f"default_rule_count: {report.default_rule_count}",
        f"default_enabled_rule_count: {report.default_enabled_rule_count}",
        f"before_diff: added={report.before_diff_added} updated={report.before_diff_updated} removed={report.before_diff_removed}",
        f"approved_unpublished_count: {report.approved_unpublished_count}",
        f"smoke_proposal_ids: {', '.join(report.smoke_proposal_ids) or '-'}",
        f"preserved_proposal_ids: {', '.join(report.preserved_proposal_ids) or '-'}",
    ]
    if report.after_draft_snapshot_hash is not None:
        lines.extend(
            [
                f"after_draft_snapshot_hash: {report.after_draft_snapshot_hash}",
                f"after_draft_rule_count: {report.after_draft_rule_count}",
                f"after_draft_enabled_rule_count: {report.after_draft_enabled_rule_count}",
                f"after_diff: added={report.after_diff_added} updated={report.after_diff_updated} removed={report.after_diff_removed}",
            ]
        )
    if report.warnings:
        lines.append("warnings:")
        lines.extend(f"  - {warning}" for warning in report.warnings)
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rebuild a Term Rule Set draft from the current default version and clean smoke proposal residue."
    )
    parser.add_argument("--set-id", default=DEFAULT_TERM_RULE_SET_ID)
    parser.add_argument("--drop-source-prefix", default="SMOKE_TR_")
    parser.add_argument("--expected-draft-hash", default=None)
    parser.add_argument("--actor-id", default="ops:repair_term_rule_draft")
    parser.add_argument("--trace-id", default="ops-repair-term-rule-draft")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--format", choices=("pretty", "json"), default="pretty")
    args = parser.parse_args()
    if args.apply and args.dry_run:
        parser.error("--apply and --dry-run cannot be used together.")

    report = repair_term_rule_draft_from_default(
        build_runtime(),
        set_id=args.set_id,
        drop_source_prefix=args.drop_source_prefix,
        expected_draft_hash=args.expected_draft_hash,
        apply=args.apply,
        actor_id=args.actor_id,
        trace_id=args.trace_id,
    )
    if args.format == "json":
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(format_pretty_report(report))
    raise SystemExit(0 if report.ok else 1)


if __name__ == "__main__":
    main()
