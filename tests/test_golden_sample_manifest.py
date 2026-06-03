from __future__ import annotations

# tests/test_golden_sample_manifest.py: 校验 P0 Golden Sample 清单和回归脚本基础合同。

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

import yaml

from scripts.ops.run_golden_sample_regression import (
    DEFAULT_MANIFEST_PATH,
    RegressionConfig,
    SampleInventory,
    SampleResult,
    build_report,
    build_sample_inventory,
    format_markdown_report,
    load_manifest,
    resolve_sample_root,
)


class GoldenSampleManifestTests(TestCase):
    def test_manifest_defines_required_sample_coverage(self):
        manifest = load_manifest(DEFAULT_MANIFEST_PATH)
        samples = manifest["samples"]
        all_tags = {tag for sample in samples for tag in sample.get("tags", [])}

        self.assertGreaterEqual(len(samples), 10)
        self.assertLessEqual(len(samples), 20)
        self.assertIn("single_column", all_tags)
        self.assertIn("double_column", all_tags)
        self.assertIn("headings", all_tags)
        self.assertIn("parameter_table", all_tags)
        self.assertIn("images", all_tags)

    def test_manifest_filenames_are_unique_and_under_sample_root(self):
        manifest = load_manifest(DEFAULT_MANIFEST_PATH)
        sample_root = resolve_sample_root(DEFAULT_MANIFEST_PATH, manifest)
        filenames = [sample["filename"] for sample in manifest["samples"]]

        self.assertEqual(len(filenames), len(set(filenames)))
        self.assertTrue(sample_root.is_absolute())
        for filename in filenames:
            self.assertEqual(Path(filename).name, filename)

    def test_manifest_is_plain_yaml_file(self):
        raw_manifest = DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8")
        decoded = yaml.safe_load(raw_manifest)

        self.assertEqual(decoded["schema_version"], 1)
        self.assertEqual(decoded["target_success_rate"], 0.9)

    def test_current_sample_inventory_reports_four_runnable_samples(self):
        manifest = load_manifest(DEFAULT_MANIFEST_PATH)
        sample_root = resolve_sample_root(DEFAULT_MANIFEST_PATH, manifest)
        samples = [item for item in manifest["samples"] if item.get("enabled", True)]

        inventory = build_sample_inventory(sample_root, samples, manifest["samples"])

        self.assertEqual(inventory.manifest_samples, 12)
        self.assertEqual(
            inventory.manifest_matched_pdf_files,
            ["OPA228_P1.pdf", "OPA228_P2.pdf", "OPA228_P6.pdf", "OPA228_P7.pdf"],
        )
        self.assertEqual(len(inventory.missing_pdf_files), 8)
        self.assertEqual(inventory.orphan_pdf_files, [])

    def test_inventory_does_not_count_orphan_pdf_as_runnable(self):
        with TemporaryDirectory() as tmp_dir:
            sample_root = Path(tmp_dir)
            (sample_root / "expected.pdf").write_bytes(b"%PDF-1.4\n")
            (sample_root / "orphan.pdf").write_bytes(b"%PDF-1.4\n")
            samples = [
                {"id": "gs-a", "filename": "expected.pdf"},
                {"id": "gs-b", "filename": "missing.pdf"},
            ]

            inventory = build_sample_inventory(sample_root, samples, samples)

        self.assertEqual(inventory.manifest_matched_pdf_files, ["expected.pdf"])
        self.assertEqual(inventory.missing_pdf_files, ["missing.pdf"])
        self.assertEqual(inventory.orphan_pdf_files, ["orphan.pdf"])

    def test_report_summary_includes_inventory_fields(self):
        with TemporaryDirectory() as tmp_dir:
            run_dir = Path(tmp_dir)
            config = RegressionConfig(runs_dir=run_dir)
            inventory = SampleInventory(
                manifest_samples=1,
                manifest_matched_pdf_files=[],
                missing_pdf_files=["missing.pdf"],
                orphan_pdf_files=["orphan.pdf"],
            )
            report = build_report(
                config,
                {"target_success_rate": 0.9},
                run_dir,
                [
                    SampleResult(
                        sample_id="gs-a",
                        filename="missing.pdf",
                        title="Missing sample",
                        tags=[],
                        status="missing_pdf",
                    )
                ],
                inventory,
            )

        summary = report["summary"]
        self.assertEqual(summary["manifest_samples"], 1)
        self.assertEqual(summary["manifest_matched_pdfs"], 0)
        self.assertEqual(summary["runnable_samples"], 0)
        self.assertEqual(summary["missing_pdf_samples"], 1)
        self.assertEqual(summary["orphan_pdf_count"], 1)
        self.assertEqual(summary["orphan_pdf_files"], ["orphan.pdf"])
        self.assertFalse(summary["met_target"])
        self.assertIn("Manifest 外 PDF: `orphan.pdf`", format_markdown_report(report))
