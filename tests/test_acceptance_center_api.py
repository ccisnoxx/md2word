"""Tests for Acceptance Center admin APIs and persistence."""

from __future__ import annotations

# File: tests/test_acceptance_center_api.py
# Purpose: Cover Acceptance Center list/detail/review APIs, permissions, audit, and file persistence.

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.domains.acceptance.models import AcceptanceRunRecord
from app.domains.resources.models import utc_now
from app.infrastructure.persistence import build_file_persistence_adapters
from app.main import build_runtime, create_app
from tests.test_fastapi_jobs_backend import build_auth_header, build_auth_users_json, build_test_runtime


class AcceptanceCenterApiTests(TestCase):
    def test_runtime_bootstraps_non_passing_acceptance_summaries_when_empty(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = Settings(
                _env_file=None,
                data_dir=str(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            runtime = build_runtime(settings)
            seeded = runtime.acceptance_run_repository.list_acceptance_runs()
            build_runtime(settings)
            reloaded = build_file_persistence_adapters(Path(temp_dir)).acceptance_run_repository.list_acceptance_runs()

        self.assertEqual({record.tier for record in seeded}, {"P0", "P1", "P2"})
        self.assertNotIn("passed", {record.status for record in seeded})
        self.assertEqual(len(seeded), 3)
        self.assertEqual(len(reloaded), 3)
        p2_run = next(record for record in reloaded if record.tier == "P2")
        self.assertIn("p2_online_gate_not_recorded", p2_run.blockers)

    def test_admin_lists_details_reviews_and_audits_acceptance_runs(self) -> None:
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            runtime = build_test_runtime(
                data_dir,
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            base_time = utc_now()
            runtime.acceptance_run_repository.save_acceptance_run(
                AcceptanceRunRecord(
                    id="acceptance_p0_unknown",
                    title="P0 Golden Sample",
                    tier="P0",
                    status="unknown",
                    environment="hostdzire",
                    source="golden_sample",
                    report_path_or_url="tests/tmp/golden_sample_runs/run-1/report.md",
                    summary="等待管理员验收。",
                    blockers=["admin_manual_review_pending"],
                    warnings=["report_pending"],
                    updated_at=base_time,
                )
            )
            runtime.acceptance_run_repository.save_acceptance_run(
                AcceptanceRunRecord(
                    id="acceptance_p2_passed",
                    title="P2 Online Gate",
                    tier="P2",
                    status="passed",
                    environment="hostdzire",
                    source="p2_online_gate",
                    report_path_or_url="tests/tmp/p2_online_runs/run-1/report.md",
                    summary="线上门禁通过。",
                    updated_at=base_time,
                )
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                operator_headers = build_auth_header(client, username="operator", password="operator-pass")

                unauthenticated_list = client.get("/api/v1/acceptance/runs")
                operator_forbidden = client.get("/api/v1/acceptance/runs", headers=operator_headers)
                list_response = client.get("/api/v1/acceptance/runs", headers=admin_headers)
                filtered_response = client.get(
                    "/api/v1/acceptance/runs",
                    headers=admin_headers,
                    params={"status": "unknown"},
                )
                detail_response = client.get("/api/v1/acceptance/runs/acceptance_p0_unknown", headers=admin_headers)
                missing_detail = client.get("/api/v1/acceptance/runs/missing_run", headers=admin_headers)
                review_response = client.post(
                    "/api/v1/acceptance/runs/acceptance_p0_unknown/review",
                    headers=admin_headers,
                    json={"decision": "approved", "review_note": "证据暂为 unknown，先按需补变更。"},
                )
                missing_review = client.post(
                    "/api/v1/acceptance/runs/missing_run/review",
                    headers=admin_headers,
                    json={"decision": "rejected", "review_note": "missing"},
                )

            persisted = build_file_persistence_adapters(data_dir).acceptance_run_repository.get_acceptance_run(
                "acceptance_p0_unknown"
            )
            events = runtime.audit_event_repository.list_audit_events()

        self.assertEqual(unauthenticated_list.status_code, 401)
        self.assertEqual(operator_forbidden.status_code, 403)
        self.assertEqual(operator_forbidden.json()["error_code"], "role_forbidden")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["total"], 2)
        self.assertEqual({item["id"] for item in list_response.json()["items"]}, {"acceptance_p0_unknown", "acceptance_p2_passed"})
        self.assertEqual(filtered_response.status_code, 200)
        self.assertEqual([item["id"] for item in filtered_response.json()["items"]], ["acceptance_p0_unknown"])
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["status"], "unknown")
        self.assertEqual(detail_response.json()["blockers"], ["admin_manual_review_pending"])
        self.assertEqual(missing_detail.status_code, 404)
        self.assertEqual(missing_detail.json()["error_code"], "not_found")
        self.assertEqual(review_response.status_code, 200)
        self.assertEqual(review_response.json()["status"], "unknown")
        self.assertEqual(review_response.json()["decision"], "approved")
        self.assertEqual(review_response.json()["reviewer"], "user_admin")
        self.assertEqual(missing_review.status_code, 404)
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted.status, "unknown")
        self.assertEqual(persisted.decision, "approved")
        review_events = [event for event in events if event.action == "acceptance_run.review"]
        self.assertEqual(len(review_events), 1)
        self.assertEqual(review_events[0].target_id, "acceptance_p0_unknown")
        self.assertEqual(review_events[0].details["decision"], "approved")
        self.assertEqual(review_events[0].details["run_status"], "unknown")
