"""覆盖常规回归采集、费用归因与七组指标出表。"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, Mock, patch
from zipfile import ZipFile

from docx import Document
import requests

from scripts.ops import run_golden_sample_regression as runner
from scripts.ops.datasheet_quality_metrics import build_report


class GoldenSampleMetricsIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.manifest_path = self.root / "manifest.json"
        self.cost_path = self.root / "cost.json"
        self.session = MagicMock()
        self.session.__enter__.return_value = self.session
        self.session.post.side_effect = self.submit
        self.session.get.side_effect = self.authorize
        self.document = io.BytesIO()
        docx = Document()
        docx.add_paragraph("Datasheet")
        docx.save(self.document)
        corrupt = io.BytesIO()
        with ZipFile(corrupt, "w") as archive:
            archive.writestr("[Content_Types].xml", "<malformed")
            archive.writestr("word/document.xml", "<malformed")
        self.corrupt = corrupt.getvalue()

    def config(self, **overrides) -> runner.RegressionConfig:
        values = {"manifest_path": self.manifest_path, "runs_dir": self.root / "runs",
                  "metrics_evidence_level": "local_http_fixture", "poll_interval_seconds": 2,
                  "manual_signoff_path": "", "cost_evidence_path": "", "download_outputs": True}
        return runner.RegressionConfig(**{**values, **overrides})

    def manifest(self, names: list[str]) -> bytes:
        samples = [{"id": name, "filename": f"{name}.pdf"} for name in names]
        for sample in samples:
            if sample["id"] != "missing":
                (self.root / sample["filename"]).write_bytes(b"%PDF-1.4\n")
        content = json.dumps({
            "schema_version": 1, "target_success_rate": 1.0,
            "sample_root": ".", "samples": samples,
        }).encode()
        self.manifest_path.write_bytes(content)
        return content

    @staticmethod
    def submit(_url, *, json, timeout):
        return Mock(json=Mock(return_value={"job": {"id": json["source_file_id"], "mode": json["mode"]}}))

    @staticmethod
    def authorize(url, *, timeout):
        job_id = url.split("/")[-2]
        payload = {"job_id": job_id, "file_id": f"word-{job_id}", "download_url": f"/word/{job_id}"}
        if job_id == "wrong_file":
            payload["file_id"] = "other-document"
        return Mock(json=Mock(return_value=payload))

    @staticmethod
    def terminal(_config, _session, job_id):
        if job_id == "timeout":
            raise TimeoutError("测试任务未进入终态")
        return {
            "id": "another-job" if job_id == "wrong_job" else job_id,
            "status": "succeeded", "mode": "direct_pdf_to_word", "retry_count": 2,
            "result_file_id": f"word-{job_id}",
        }

    def download(self, url, *, timeout):
        if url.endswith("/download_error"):
            response = requests.Response()
            response.status_code = 403
            raise requests.HTTPError("签名地址包含敏感签名", response=response)
        return Mock(content=self.corrupt if url.endswith("/bad") else self.document.getvalue())

    @staticmethod
    def receipt(job_id: str, *, generation: int = 2, complete: bool = True) -> dict:
        return {"job_id": job_id, "retry_count": generation, "cost": {
            "complete": complete, "currency": "USD", "basis": "actual", "reference": "测试凭证",
            "components": {"parser": 0.04, "translation": 0} if complete else {"parser": 0.02},
        }}

    def write_receipts(self, *receipts: dict) -> None:
        self.cost_path.write_text(json.dumps({
            "schema_version": runner.COST_EVIDENCE_VERSION, "receipts": receipts,
        }), encoding="utf-8")

    def run_fixture(self, config: runner.RegressionConfig):
        with (
            patch.object(runner, "build_authenticated_session", return_value=self.session),
            patch.object(runner, "upload_source_pdf", side_effect=lambda _config, _session, path: path.stem),
            patch.object(runner, "wait_for_terminal_job", side_effect=self.terminal),
            patch.object(runner.requests, "get", side_effect=self.download) as download,
            patch.object(runner.time, "monotonic", side_effect=range(100)),
        ):
            return runner.run_regression(config), download.call_count

    def test_run_emits_fixed_plan_download_and_bound_cost_evidence(self) -> None:
        manifest = self.manifest(["good", "bad", "timeout", "missing"])
        self.write_receipts(self.receipt("good"), self.receipt("bad", complete=False), self.receipt("timeout"))
        report, calls = self.run_fixture(self.config(cost_evidence_path=str(self.cost_path)))
        run_dir = Path(report["run_dir"])
        observation = json.loads((run_dir / "observations.json").read_text())
        metrics = json.loads((run_dir / "metrics.json").read_text())
        self.assertEqual(build_report(observation), metrics)
        self.assertEqual(observation["metadata"]["manifest_sha256"], hashlib.sha256(manifest).hexdigest())
        self.assertEqual(observation["metadata"]["cost_evidence_sha256"],
                         hashlib.sha256(self.cost_path.read_bytes()).hexdigest())
        self.assertEqual(metrics["groups"][0]["evidence_level"], "local_http_fixture")
        rows = {row["sample_id"]: row for row in metrics["samples"]}
        raw = {row["sample_id"]: row for row in observation["observations"]}
        self.assertEqual(metrics["groups"][0]["conversion_success"]["denominator"], 4)
        self.assertEqual(metrics["groups"][0]["conversion_success"]["numerator"], 1)
        self.assertEqual(report["summary"]["pass_rate"], 0.3333)
        self.assertEqual(report["summary"]["target_success_rate"], 1)
        self.assertEqual(calls, 2)
        self.assertTrue(rows["good"]["conversion"]["success"])
        self.assertEqual(rows["good"]["latency_seconds"]["value"], 1)
        self.assertEqual(rows["good"]["latency_seconds"]["poll_interval_seconds"], 2)
        self.assertEqual(raw["good"]["artifacts"]["docx_sha256"], hashlib.sha256(self.document.getvalue()).hexdigest())
        self.assertEqual(rows["good"]["cost"]["value"], 0.04)
        self.assertEqual(rows["bad"]["conversion"]["reason"], "docx_not_openable")
        self.assertEqual(rows["bad"]["latency_seconds"]["value"], 2)
        self.assertIsNone(rows["bad"]["cost"]["value"])
        self.assertEqual(rows["bad"]["cost"]["components"], {"parser": 0.02})
        self.assertEqual(rows["timeout"]["conversion"]["status"], "timeout")
        self.assertNotIn("retry_count", raw["timeout"]["execution"])
        self.assertIsNone(rows["timeout"]["cost"]["value"])
        self.assertEqual(rows["missing"]["latency_seconds"]["reason"], "job_not_submitted")

    def test_rejects_unbound_terminal_and_download_and_redacts_http_exception(self) -> None:
        self.manifest(["wrong_job", "wrong_file", "download_error"])
        self.write_receipts(self.receipt("wrong_job"), self.receipt("wrong_file", generation=0))
        report, calls = self.run_fixture(self.config(cost_evidence_path=str(self.cost_path)))
        run_dir = Path(report["run_dir"])
        observations = json.loads((run_dir / "observations.json").read_text())["observations"]
        rows = {row["sample_id"]: row for row in observations}
        self.assertEqual(rows["wrong_job"]["conversion"]["reason"], "job_identity_failed")
        self.assertNotIn("retry_count", rows["wrong_job"]["execution"])
        self.assertNotIn("cost", rows["wrong_job"])
        self.assertEqual(rows["wrong_file"]["conversion"]["reason"], "download_authorization_failed")
        self.assertEqual(rows["wrong_file"]["missing"]["cost"], "cost_evidence_generation_mismatch")
        self.assertEqual(rows["download_error"]["conversion"]["reason"], "download_failed")
        self.assertTrue(rows["download_error"]["execution"]["download_authorized"])
        self.assertEqual(calls, 1)
        self.assertNotIn("敏感签名", (run_dir / "report.json").read_text())

    def test_invalid_amount_keeps_conversion_observation(self) -> None:
        self.manifest(["good"])
        bad_receipt = self.receipt("good")
        bad_receipt["cost"]["components"]["parser"] = -0.01
        self.write_receipts(bad_receipt)
        report, _ = self.run_fixture(self.config(cost_evidence_path=str(self.cost_path)))
        run_dir = Path(report["run_dir"])
        metrics = json.loads((run_dir / "metrics.json").read_text())
        self.assertEqual(metrics["samples"][0]["cost"]["reason"], "cost_evidence_invalid")
        self.assertTrue(metrics["samples"][0]["conversion"]["success"])
        self.assertTrue((run_dir / "observations.json").is_file())

    def test_missing_signoff_still_saves_machine_observations(self) -> None:
        self.manifest(["good"])
        config = self.config(manual_signoff_path=str(self.root / "missing.yaml"))
        with self.assertRaises(FileNotFoundError):
            self.run_fixture(config)
        run_dir, = config.runs_dir.iterdir()
        metrics = json.loads((run_dir / "metrics.json").read_text())
        self.assertEqual(metrics["groups"][0]["conversion_success"]["numerator"], 1)
        self.assertTrue((run_dir / "observations.json").is_file())

    def test_auth_failure_keeps_all_planned_rows(self) -> None:
        self.manifest(["good", "missing"])
        config = self.config()
        with (
            patch.object(runner, "build_authenticated_session", side_effect=RuntimeError("测试认证失败")),
            self.assertRaisesRegex(RuntimeError, "测试认证失败"),
        ):
            runner.run_regression(config)
        run_dir, = config.runs_dir.iterdir()
        metrics = json.loads((run_dir / "metrics.json").read_text())
        summary = metrics["groups"][0]["conversion_success"]
        self.assertEqual((summary["numerator"], summary["denominator"], summary["assessed"]), (0, 2, 1))
        self.assertEqual(summary["failure_reasons"], {"authentication_failed": 1, "missing_pdf": 1})

    def test_download_disabled_leaves_latency_unmeasured(self) -> None:
        self.manifest(["good"])
        report, calls = self.run_fixture(self.config(download_outputs=False))
        run_dir = Path(report["run_dir"])
        metrics = json.loads((run_dir / "metrics.json").read_text())
        row, = metrics["samples"]
        self.assertEqual(calls, 0)
        self.assertEqual(row["conversion"]["reason"], "docx_download_disabled")
        self.assertEqual(row["latency_seconds"]["reason"], "docx_download_disabled")
