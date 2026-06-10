from __future__ import annotations

# tests/test_openapi_export.py: 覆盖 OpenAPI 快照导出和发布前一致性检查。

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from tempfile import TemporaryDirectory
from unittest import TestCase

from scripts.ops.export_openapi import check_openapi_export, export_openapi
from scripts.ops.check_release import check_release, check_runtime_readiness, format_release_report


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
        self.assertIn("/api/v1/jobs", payload["paths"])
        self.assertIn("JobDetailResponse", payload["components"]["schemas"])

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
        self.assertEqual([item.name for item in report.items], ["openapi"])
        self.assertIn("Release check report", formatted)
        self.assertIn("[openapi] ok: True", formatted)

    def test_check_runtime_readiness_requires_deployment_and_p0_gates(self):
        responses = {
            "/api/v1/health/ready": {
                "status": "ok",
                "dependency_checks": {
                    "deployment_init_ready": False,
                    "p0_document_jobs_ready": False,
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
