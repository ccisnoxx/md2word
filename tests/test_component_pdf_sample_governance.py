"""Validate component PDF sample governance manifest and local regression tools."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

import yaml

from scripts.dev import manage_component_pdf_samples, run_component_pdf_regression


MANIFEST_PATH = Path("tests/fixtures/component_pdf_samples/manifest.yaml")


class ComponentPdfSampleManifestTests(TestCase):
    def test_manifest_defines_brand_category_component_contract(self) -> None:
        manifest = manage_component_pdf_samples.load_manifest(MANIFEST_PATH)
        report = manage_component_pdf_samples.validate_manifest(MANIFEST_PATH)
        samples = manifest["samples"]
        first_sample = samples[0]

        self.assertTrue(report.ok)
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["default_document_language"], "en")
        self.assertEqual(manifest["default_translation_mode"], "direct")
        self.assertGreaterEqual(len(samples), 1)
        self.assertEqual(first_sample["brand"], "texas-instruments")
        self.assertEqual(first_sample["category"], "op-amp")
        self.assertEqual(first_sample["product"], "OPA228")
        self.assertIn("op_amp", first_sample["tags"])

    def test_manifest_package_paths_are_under_brand_category_directories(self) -> None:
        manifest = manage_component_pdf_samples.load_manifest(MANIFEST_PATH)
        sample_root = manage_component_pdf_samples.resolve_sample_root(MANIFEST_PATH, manifest)

        for sample in manifest["samples"]:
            package_path = manage_component_pdf_samples.sample_package_path(sample_root, sample)
            relative_path = package_path.relative_to(sample_root)
            self.assertEqual(relative_path.parts[0], sample["brand"])
            self.assertEqual(relative_path.parts[1], sample["category"])
            self.assertEqual(relative_path.parts[2], sample["id"])
            self.assertTrue(package_path.exists())

    def test_disabled_placeholder_sample_may_lack_local_mineru_package(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manifest_path = root / "manifest.yaml"
            manifest_path.write_text(
                yaml.safe_dump(
                    {
                        "schema_version": 1,
                        "sample_root": "samples",
                        "samples": [
                            {
                                "id": "ti-opamp-placeholder",
                                "brand": "texas-instruments",
                                "category": "op-amp",
                                "product": "OPA999",
                                "title": "Placeholder",
                                "source_pdf": {"reference": "external:OPA999.pdf"},
                                "mineru": {"package_path": "texas-instruments/op-amp/ti-opamp-placeholder/mineru"},
                                "tags": ["placeholder"],
                                "acceptance_focus": ["Future sample"],
                                "regression": {"enabled": False},
                            }
                        ],
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            report = manage_component_pdf_samples.validate_manifest(manifest_path)

        self.assertTrue(report.ok)
        self.assertEqual(report.enabled_count, 0)
        self.assertEqual(report.runnable_count, 0)

    def test_manifest_validation_rejects_missing_required_review_metadata(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manifest_path = root / "manifest.yaml"
            source_package = root / "samples" / "texas-instruments" / "op-amp" / "ti-opamp-metadata-gap" / "mineru"
            source_package.mkdir(parents=True)
            (source_package / "abc_content_list_v2.json").write_text("[[]]\n", encoding="utf-8")
            manifest_path.write_text(
                yaml.safe_dump(
                    {
                        "schema_version": 1,
                        "sample_root": "samples",
                        "samples": [
                            {
                                "id": "ti-opamp-metadata-gap",
                                "brand": "texas-instruments",
                                "category": "op-amp",
                                "product": "OPA123",
                                "title": "Metadata gap",
                                "source_pdf": {"reference": "external:OPA123.pdf"},
                                "mineru": {"package_path": "texas-instruments/op-amp/ti-opamp-metadata-gap/mineru"},
                                "acceptance_focus": ["Future sample"],
                            }
                        ],
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            report = manage_component_pdf_samples.validate_manifest(manifest_path)

        self.assertFalse(report.ok)
        issue_codes = {issue.code for issue in report.issues}
        self.assertIn("missing_tags", issue_codes)
        self.assertIn("missing_regression_enabled", issue_codes)


class ComponentPdfSampleManagementTests(TestCase):
    def test_add_mineru_sample_copies_package_and_appends_manifest(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            sample_root = root / "samples"
            manifest_path = root / "manifest.yaml"
            manifest_path.write_text(
                yaml.safe_dump(
                    {
                        "schema_version": 1,
                        "sample_root": "samples",
                        "default_document_language": "en",
                        "default_translation_mode": "direct",
                        "samples": [],
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            source_package = root / "source_package"
            source_package.mkdir()
            (source_package / "abc_content_list_v2.json").write_text("[[]]\n", encoding="utf-8")

            result = manage_component_pdf_samples.add_mineru_sample(
                manifest_path=manifest_path,
                sample_id="adi-opamp-ad8676-smoke",
                brand="analog-devices",
                category="op-amp",
                product="AD8676",
                title="AD8676 smoke",
                source_pdf="external:AD8676.pdf",
                mineru_package=source_package,
                tags=["datasheet", "op_amp"],
                acceptance_focus=["Parameter table stays editable"],
                document_language="en",
                translation_mode="direct",
                apply=True,
            )
            updated_manifest = manage_component_pdf_samples.load_manifest(manifest_path)

            self.assertTrue(result.manifest_updated)
            self.assertTrue((sample_root / "analog-devices" / "op-amp" / "adi-opamp-ad8676-smoke" / "mineru" / "abc_content_list_v2.json").exists())
            self.assertEqual(updated_manifest["samples"][0]["id"], "adi-opamp-ad8676-smoke")
            self.assertEqual(updated_manifest["samples"][0]["mineru"]["package_path"], "analog-devices/op-amp/adi-opamp-ad8676-smoke/mineru")


class ComponentPdfRegressionRunnerTests(TestCase):
    def test_regression_runner_converts_committed_minimal_mineru_sample(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            report = run_component_pdf_regression.run_regression(
                run_component_pdf_regression.ComponentRegressionConfig(
                    manifest_path=MANIFEST_PATH,
                    output_dir=output_dir,
                    sample_ids=("ti-opamp-opa228-p1-smoke",),
                    timestamped=False,
                )
            )

            result = report["results"][0]
            self.assertTrue(report["summary"]["ok"])
            self.assertEqual(result["status"], "succeeded")
            self.assertTrue(result["docx_openable"])
            self.assertTrue(Path(result["output_path"]).exists())
            self.assertTrue((output_dir / "report.json").exists())
            self.assertTrue((output_dir / "report.md").exists())
