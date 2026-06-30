from __future__ import annotations

# tests/test_openapi_export.py: 覆盖 OpenAPI 快照导出和发布前一致性检查。

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from tempfile import TemporaryDirectory
from unittest import TestCase

from scripts.ops.export_openapi import check_openapi_export, export_openapi
from scripts.ops.check_release import (
    check_golden_sample_preflight,
    check_release,
    check_runtime_readiness,
    format_release_report,
)
from scripts.ops.run_golden_sample_regression import RegressionConfig
from scripts.ops.run_p2_online_gate import P2OnlineGateConfig, build_summary, run_p2_online_gate


class OpenAPIExportTests(TestCase):
    def test_export_openapi_writes_snapshot_and_check_passes(self):
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "openapi.json"

            export_report = export_openapi(output_path)
            check_report = check_openapi_export(output_path)
            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertTrue(export_report.ok)
        self.assertTrue(export_report.changed)
        self.assertTrue(check_report.ok)
        self.assertFalse(check_report.changed)
        self.assertNotIn("/api/v1/jobs", payload["paths"])
        self.assertNotIn("/api/v1/jobs/pdf", payload["paths"])
        self.assertIn("/api/v1/document-jobs", payload["paths"])
        self.assertIn("DocumentJobResponse", payload["components"]["schemas"])

    def test_check_openapi_export_fails_when_snapshot_is_stale(self):
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "openapi.json"
            export_openapi(output_path)
            output_path.write_text("{}\n", encoding="utf-8")

            report = check_openapi_export(output_path)

        self.assertFalse(report.ok)
        self.assertTrue(report.changed)
        self.assertIn("generated-openapi", report.diff)

    def test_check_release_aggregates_openapi_and_optional_unittest_targets(self):
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "openapi.json"
            export_openapi(output_path)

            report = check_release(output_path, unittest_targets=())
            formatted = format_release_report(report)

        self.assertTrue(report.ok)
        self.assertEqual([item.name for item in report.items], ["openapi", "frontend-contract", "frontend-smoke-mock"])
        self.assertIn("Release check report", formatted)
        self.assertIn("[openapi] ok: True", formatted)
        self.assertIn("[frontend-contract] ok: True", formatted)
        self.assertIn("[frontend-smoke-mock] ok: True", formatted)

    def test_check_runtime_readiness_requires_deployment_and_p0_gates(self):
        responses = {
            "/api/v1/health/ready": {
                "status": "ok",
                "dependency_checks": {
                    "deployment_init_ready": False,
                    "p0_document_jobs_ready": False,
                    "effective_repository_backend": "file",
                    "document_jobs_worker_backend": "disabled",
                    "readiness_blockers": ["document_jobs_worker_backend_disabled"],
                    "p0_document_jobs_blockers": ["document_jobs_worker_backend_disabled"],
                },
            }
        }

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                payload = responses.get(self.path)
                if payload is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                body = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):  # noqa: A002
                return

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base_url = f"http://127.0.0.1:{server.server_port}"
            failed_item = check_runtime_readiness(base_url)
            responses["/api/v1/health/ready"]["dependency_checks"] = {
                "deployment_init_ready": True,
                "p0_document_jobs_ready": True,
                "effective_repository_backend": "mysql",
                "document_jobs_worker_backend": "celery",
                "document_jobs_celery_queue": "document-jobs",
                "document_jobs_translation_batch_celery_queue": "document-translation-batches",
                "readiness_blockers": [],
                "p0_document_jobs_blockers": [],
            }
            passed_item = check_runtime_readiness(f"{base_url}/api/v1")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertFalse(failed_item.ok)
        self.assertIn("document_jobs_worker_backend_disabled", failed_item.details)
        self.assertTrue(passed_item.ok)

    def test_golden_sample_preflight_release_check_requires_admin_and_p0_runtime(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sample_root = root / "pdfs"
            sample_root.mkdir()
            (sample_root / "OPA228_P1.pdf").write_bytes(b"%PDF-1.4\n")
            manifest_path = root / "manifest.yaml"
            manifest_path.write_text(
                "\n".join(
                    [
                        "schema_version: 1",
                        "sample_root: pdfs",
                        "target_success_rate: 1.0",
                        "samples:",
                        "  - id: gs-003",
                        "    filename: OPA228_P1.pdf",
                        "    title: Datasheet page",
                        "    enabled: true",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            responses = {
                "/api/v1/health/ready": {
                    "status": "ok",
                    "dependency_checks": {
                        "deployment_init_ready": True,
                        "p0_document_jobs_ready": True,
                        "effective_repository_backend": "mysql",
                        "document_jobs_worker_backend": "celery",
                        "document_jobs_celery_queue": "document-jobs",
                        "document_jobs_translation_batch_celery_queue": "document-translation-batches",
                        "readiness_blockers": [],
                        "p0_document_jobs_blockers": [],
                    },
                },
                "/api/v1/auth/me": {
                    "username": "admin",
                    "role": "admin",
                },
            }

            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):  # noqa: N802
                    payload = responses.get(self.path)
                    if payload is None:
                        self.send_response(404)
                        self.end_headers()
                        return
                    body = json.dumps(payload).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

                def log_message(self, format, *args):  # noqa: A002
                    return

            server = HTTPServer(("127.0.0.1", 0), Handler)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                config = RegressionConfig(
                    base_url=f"http://127.0.0.1:{server.server_port}",
                    bearer_token="token",
                    required_role="admin",
                    manifest_path=manifest_path,
                )
                item = check_golden_sample_preflight(config=config)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

        self.assertTrue(item.ok)
        self.assertIn("[manifest] ok: True", item.details)
        self.assertIn("[auth] ok: True", item.details)
        self.assertIn("[runtime-readiness] ok: True", item.details)

    def test_p2_online_gate_collects_runtime_evidence(self):
        responses = {
            "/api/v1/health/live": {"status": "ok", "app_name": "md2word_file"},
            "/api/v1/health/ready": {
                "status": "ok",
                "app_name": "md2word_file",
                "deployment": {
                    "environment": "prod",
                    "public_deployment_mode": "internal",
                    "version": "2026.06.17-p2",
                    "deployment_id": "hostdzire-p2-test",
                    "started_at": "2026-06-17T00:00:00+00:00",
                },
                "dependency_checks": {
                    "deployment_init_ready": True,
                    "p0_document_jobs_ready": True,
                    "effective_repository_backend": "mysql",
                    "document_jobs_worker_backend": "celery",
                    "document_jobs_celery_queue": "document-jobs",
                    "document_jobs_translation_batch_celery_queue": "document-translation-batches",
                    "translation_available": True,
                    "readiness_blockers": [],
                    "readiness_warnings": [],
                    "p0_document_jobs_blockers": [],
                },
            },
            "/api/v1/health/metrics": {
                "status": "ok",
                "app_name": "md2word_file",
                "generated_at": "2026-06-17T00:00:01+00:00",
                "deployment": {
                    "environment": "prod",
                    "public_deployment_mode": "internal",
                    "version": "2026.06.17-p2",
                    "deployment_id": "hostdzire-p2-test",
                    "started_at": "2026-06-17T00:00:00+00:00",
                },
                "metadata_store": "mysql",
                "artifact_storage": "local_object",
                "worker_mode": "external",
                "stage_dispatcher": "external_worker",
                "jobs": {},
                "document_jobs": {},
                "stage_messages": {},
                "document_job_callback_messages": {},
                "resources": {},
                "audit_events": {"total": 1},
            },
            "/api/v1/health/ops-alerts": {
                "status": "ok",
                "app_name": "md2word_file",
                "generated_at": "2026-06-17T00:00:02+00:00",
                "summary": {},
                "alerts": [],
                "safety": {
                    "read_only": True,
                    "writes_performed": False,
                    "recovery_actions_executed": False,
                    "provider_calls_executed": False,
                    "notification_delivery_executed": False,
                    "audit_events_written": False,
                },
            },
        }

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                payload = responses.get(self.path)
                if payload is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                body = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):  # noqa: A002
                return

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with TemporaryDirectory() as temp_dir:
                base_url = f"http://127.0.0.1:{server.server_port}"
                report = run_p2_online_gate(
                    P2OnlineGateConfig(
                        base_url=base_url,
                        public_url=base_url,
                        bearer_token="test-token",
                        runs_dir=Path(temp_dir),
                        run_p0_preflight=False,
                        run_p1_preflight=False,
                    ),
                    release_check_unittest_targets=(),
                )
                report_path = Path(report["run_dir"]) / "report.json"
                report_exists = report_path.exists()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertTrue(report["summary"]["p2_online_gate_ready"])
        self.assertEqual(report["summary"]["deployment"]["deployment_id"], "hostdzire-p2-test")
        self.assertEqual(report["summary"]["runtime"]["effective_repository_backend"], "mysql")
        self.assertTrue(report["checks"]["release_check"]["ok"])
        self.assertTrue(report["checks"]["public"]["ok"])
        self.assertTrue(report_exists)

    def test_p2_online_gate_summary_tolerates_ops_alert_error_payload(self):
        summary = build_summary(
            checks=[{"name": "ops_alerts", "ok": False, "blockers": ["ops_alerts_http_401"]}],
            public_checks={"blockers": []},
            ready_payload={
                "dependency_checks": {
                    "document_jobs_translation_batch_celery_queue": "document-translation-batches",
                }
            },
            ops_alerts_payload={"detail": "unauthorized", "alerts": None},
        )

        self.assertFalse(summary["p2_online_gate_ready"])
        self.assertEqual(summary["blockers"], ["ops_alerts_http_401"])

    def test_p2_online_gate_syncs_acceptance_center_when_enabled(self):
        responses = {
            "/api/v1/health/live": {"status": "ok", "app_name": "md2word_file"},
            "/api/v1/health/ready": {
                "status": "ok",
                "app_name": "md2word_file",
                "deployment": {
                    "environment": "prod",
                    "public_deployment_mode": "internal",
                    "version": "2026.06.17-p2",
                    "deployment_id": "hostdzire-p2-test",
                    "started_at": "2026-06-17T00:00:00+00:00",
                },
                "dependency_checks": {
                    "deployment_init_ready": True,
                    "p0_document_jobs_ready": True,
                    "effective_repository_backend": "mysql",
                    "document_jobs_worker_backend": "celery",
                    "document_jobs_celery_queue": "document-jobs",
                    "document_jobs_translation_batch_celery_queue": "document-translation-batches",
                    "translation_available": True,
                    "readiness_blockers": [],
                    "readiness_warnings": [],
                    "p0_document_jobs_blockers": [],
                },
            },
            "/api/v1/health/metrics": {
                "status": "ok",
                "app_name": "md2word_file",
                "generated_at": "2026-06-17T00:00:01+00:00",
                "metadata_store": "mysql",
                "artifact_storage": "local_object",
                "worker_mode": "external",
                "stage_dispatcher": "external_worker",
                "jobs": {},
                "document_jobs": {},
                "stage_messages": {},
                "document_job_callback_messages": {},
                "resources": {},
                "audit_events": {"total": 1},
            },
            "/api/v1/health/ops-alerts": {
                "status": "ok",
                "app_name": "md2word_file",
                "generated_at": "2026-06-17T00:00:02+00:00",
                "summary": {},
                "alerts": [],
                "safety": {
                    "read_only": True,
                    "writes_performed": False,
                    "recovery_actions_executed": False,
                    "provider_calls_executed": False,
                    "notification_delivery_executed": False,
                    "audit_events_written": False,
                },
            },
        }
        posts = []
        admin_token_headers = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                if self.path == "/api/v1/health/ops-alerts":
                    admin_token_headers.append(self.headers.get("X-Admin-Token"))
                payload = responses.get(self.path)
                if payload is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                self._write_json(200, payload)

            def do_POST(self):  # noqa: N802
                admin_token_headers.append(self.headers.get("X-Admin-Token"))
                length = int(self.headers.get("Content-Length") or "0")
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                posts.append((self.path, payload))
                if self.path == "/api/v1/acceptance/runs":
                    self._write_json(200, {**payload, "updated_at": "2026-06-17T00:00:03+00:00"})
                    return
                if self.path == "/api/v1/acceptance/runs/acceptance_p2_online_gate_current/review":
                    self._write_json(
                        200,
                        {
                            **payload,
                            "id": "acceptance_p2_online_gate_current",
                            "tier": "P2",
                            "status": "passed",
                            "environment": "hostdzire",
                            "source": "manual_import:p2_online_gate",
                            "reviewer": "admin",
                            "reviewed_at": "2026-06-17T00:00:04+00:00",
                            "updated_at": "2026-06-17T00:00:04+00:00",
                        },
                    )
                    return
                self.send_response(404)
                self.end_headers()

            def _write_json(self, status_code, payload):
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status_code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):  # noqa: A002
                return

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with TemporaryDirectory() as temp_dir:
                base_url = f"http://127.0.0.1:{server.server_port}"
                report = run_p2_online_gate(
                    P2OnlineGateConfig(
                        base_url=base_url,
                        admin_token="test-admin-token",
                        runs_dir=Path(temp_dir),
                        run_release_check=False,
                        run_p0_preflight=False,
                        run_p1_preflight=False,
                        sync_acceptance=True,
                        acceptance_review_decision="approved",
                        acceptance_review_note="P2 online gate approved.",
                    ),
                    release_check_unittest_targets=(),
                )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertTrue(report["summary"]["p2_online_gate_ready"])
        self.assertTrue(report["acceptance_sync"]["ok"])
        self.assertEqual(admin_token_headers, ["test-admin-token", "test-admin-token", "test-admin-token"])
        self.assertEqual(posts[0][0], "/api/v1/acceptance/runs")
        self.assertEqual(posts[0][1]["id"], "acceptance_p2_online_gate_current")
        self.assertEqual(posts[0][1]["tier"], "P2")
        self.assertEqual(posts[0][1]["status"], "passed")
        self.assertEqual(posts[0][1]["blockers"], [])
        self.assertTrue(posts[0][1]["report_path_or_url"].endswith("/report.md"))
        self.assertIn("P2 internal online gate evidence", posts[0][1]["summary"])
        self.assertEqual(posts[1][0], "/api/v1/acceptance/runs/acceptance_p2_online_gate_current/review")
        self.assertEqual(posts[1][1]["decision"], "approved")
