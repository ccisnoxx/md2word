from __future__ import annotations

# tests/test_golden_sample_manifest.py: 校验 P0 Golden Sample 清单和回归脚本基础合同。

from pathlib import Path
from unittest import TestCase

import yaml

from scripts.ops.run_golden_sample_regression import (
    DEFAULT_MANIFEST_PATH,
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
