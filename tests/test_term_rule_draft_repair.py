# File: tests/test_term_rule_draft_repair.py
# Purpose: 覆盖术语规则 draft 线上修复脚本的 dry-run、快照保护和 smoke proposal 清理行为。

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import TestCase

from fastapi.testclient import TestClient

from app.domains.term_rules.models import TermRuleProposalStatus
from app.domains.term_rules.versioning_service import DEFAULT_TERM_RULE_SET_ID
from app.infrastructure.persistence import build_mysql_persistence_adapters
from app.main import create_app
from scripts.ops.repair_term_rule_draft_from_default import repair_term_rule_draft_from_default
from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config
from tests.test_fastapi_jobs_backend import build_auth_header, build_auth_users_json, build_test_runtime


SEED_YAML = (
    "schema_version: 2\n"
    "categories:\n"
    "  voltage_terms:\n"
    "    name: 电压相关\n"
    "    priority: 10\n"
    "    enabled: true\n"
    "rules:\n"
    "  - source_term: VBASE\n"
    "    category: voltage_terms\n"
    "    segments:\n"
    "      - segment_text: V\n"
    "        render_type: plain\n"
    "      - segment_text: BASE\n"
    "        render_type: subscript\n"
    "    enabled: true\n"
)


class TermRuleDraftRepairTests(TestCase):
    def test_dry_run_reports_smoke_proposal_without_mutating_draft(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = self._build_runtime(Path(temp_dir))
            proposal_id, draft_hash = self._create_and_approve_smoke_proposal(runtime)

            report = repair_term_rule_draft_from_default(runtime, apply=False)

            draft_after = runtime.term_rule_set_version_service.get_draft(DEFAULT_TERM_RULE_SET_ID)
            proposal_after = runtime.term_rule_proposal_service.get_proposal(proposal_id)

        self.assertFalse(report.applied)
        self.assertEqual(report.before_draft_snapshot_hash, draft_hash)
        self.assertEqual(report.default_rule_count, 1)
        self.assertEqual(report.before_draft_rule_count, 2)
        self.assertEqual(report.before_diff_added, 1)
        self.assertEqual(report.smoke_proposal_ids, [proposal_id])
        self.assertEqual(report.preserved_proposal_ids, [])
        self.assertEqual(draft_after.snapshot_hash, draft_hash)
        self.assertIn("SMOKE_TR_TEMP", draft_after.yaml_text)
        self.assertEqual(proposal_after.status, TermRuleProposalStatus.APPROVED)
        self.assertEqual(proposal_after.merged_term_rule_set_id, DEFAULT_TERM_RULE_SET_ID)

    def test_apply_restores_default_draft_and_rejects_smoke_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = self._build_runtime(Path(temp_dir))
            proposal_id, _draft_hash = self._create_and_approve_smoke_proposal(runtime)
            dry_run = repair_term_rule_draft_from_default(runtime, apply=False)

            report = repair_term_rule_draft_from_default(
                runtime,
                apply=True,
                expected_draft_hash=dry_run.before_draft_snapshot_hash,
                actor_id="ops:test",
                trace_id="trace-test",
            )
            draft_after = runtime.term_rule_set_version_service.get_draft(DEFAULT_TERM_RULE_SET_ID)
            proposal_after = runtime.term_rule_proposal_service.get_proposal(proposal_id)
            approved_unpublished = runtime.term_rule_proposal_service.list_approved_unpublished_proposals(
                DEFAULT_TERM_RULE_SET_ID
            )
            audit_actions = [event.action for event in runtime.audit_event_repository.list_audit_events()]

        self.assertTrue(report.applied)
        self.assertTrue(report.ok)
        self.assertEqual(report.after_draft_rule_count, report.default_rule_count)
        self.assertEqual(report.after_diff_added, 0)
        self.assertEqual(report.after_diff_removed, 0)
        self.assertEqual(draft_after.rule_count, 1)
        self.assertIn("VBASE", draft_after.yaml_text)
        self.assertNotIn("SMOKE_TR_TEMP", draft_after.yaml_text)
        self.assertEqual(proposal_after.status, TermRuleProposalStatus.REJECTED)
        self.assertEqual(proposal_after.reviewed_by, "ops:test")
        self.assertIsNone(proposal_after.merged_term_rule_set_id)
        self.assertIsNone(proposal_after.merged_draft_snapshot_hash)
        self.assertEqual(approved_unpublished, [])
        self.assertIn("term_rule_proposal.cleanup_smoke", audit_actions)
        self.assertIn("term_rule_set.repair_draft_from_default", audit_actions)

    def test_apply_requires_current_draft_snapshot_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = self._build_runtime(Path(temp_dir))
            proposal_id, draft_hash = self._create_and_approve_smoke_proposal(runtime)

            with self.assertRaisesRegex(ValueError, "Draft snapshot changed"):
                repair_term_rule_draft_from_default(
                    runtime,
                    apply=True,
                    expected_draft_hash="sha256:stale",
                )
            draft_after = runtime.term_rule_set_version_service.get_draft(DEFAULT_TERM_RULE_SET_ID)
            proposal_after = runtime.term_rule_proposal_service.get_proposal(proposal_id)

        self.assertEqual(draft_after.snapshot_hash, draft_hash)
        self.assertIn("SMOKE_TR_TEMP", draft_after.yaml_text)
        self.assertEqual(proposal_after.status, TermRuleProposalStatus.APPROVED)

    def _build_runtime(self, temp_root: Path):
        seed_path = temp_root / "term_rules_seed.yaml"
        seed_path.write_text(SEED_YAML, encoding="utf-8")
        fake_mysql = _FakeMysqlDatabase()
        return build_test_runtime(
            temp_root,
            jobs_repository_backend="mysql",
            auth_jwt_secret_key="test-jwt-secret",
            auth_internal_users_json=build_auth_users_json(),
            repository_factory=lambda _data_dir: build_mysql_persistence_adapters(
                _mysql_config(),
                connect_factory=fake_mysql.connect,
            ),
            term_rules_seed_path=str(seed_path),
        )

    def _create_and_approve_smoke_proposal(self, runtime) -> tuple[str, str]:
        app = create_app(runtime)
        with TestClient(app) as client:
            operator_headers = build_auth_header(client)
            admin_headers = build_auth_header(client, username="admin", password="admin-pass")
            category_id = client.get("/api/v1/term-rule-categories", headers=admin_headers).json()["items"][0]["id"]
            create_response = client.post(
                "/api/v1/term-rule-proposals",
                headers=operator_headers,
                json={
                    "intent": "create",
                    "source_term": "SMOKE_TR_TEMP",
                    "category_id": category_id,
                    "segments": [
                        {"segment_text": "SMOKE", "render_type": "plain"},
                        {"segment_text": "TR", "render_type": "subscript"},
                    ],
                    "reason": "smoke proposal should be cleaned by ops repair",
                    "observed_term_rule_set_id": DEFAULT_TERM_RULE_SET_ID,
                    "observed_term_rule_version": "seed",
                },
            )
            self.assertEqual(create_response.status_code, 201)
            proposal_id = create_response.json()["id"]
            approve_response = client.post(
                f"/api/v1/term-rule-proposals/{proposal_id}/approve",
                headers=admin_headers,
                json={"review_comment": "approve smoke residue"},
            )
            self.assertEqual(approve_response.status_code, 200)
            draft_response = client.get(
                f"/api/v1/term-rule-sets/{DEFAULT_TERM_RULE_SET_ID}/draft",
                headers=admin_headers,
            )
            self.assertEqual(draft_response.status_code, 200)
            return proposal_id, draft_response.json()["snapshot_hash"]
