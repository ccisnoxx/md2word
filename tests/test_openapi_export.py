from __future__ import annotations

# tests/test_openapi_export.py: 覆盖 OpenAPI 快照导出和发布前一致性检查。

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from scripts.ops.export_openapi import check_openapi_export, export_openapi
from scripts.ops.check_release import check_release, format_release_report


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
