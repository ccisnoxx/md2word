from __future__ import annotations

# tests/test_p1_translation_sample_manifest.py: 校验 P1 翻译验收样本清单的基础合同。

from pathlib import Path
from unittest import TestCase

import yaml


MANIFEST_PATH = Path("tests/fixtures/p1_translation_samples/manifest.yaml")


class P1TranslationSampleManifestTests(TestCase):
    def test_manifest_defines_translation_acceptance_contract(self):
        manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
        samples = manifest["samples"]
        all_tags = {tag for sample in samples for tag in sample.get("tags", [])}

        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["default_mode"], "en2zh_pdf_to_word")
        self.assertEqual(manifest["default_document_language"], "en")
        self.assertEqual(manifest["default_term_version_id"], "en2zh@v1")
        self.assertEqual(manifest["term_file"], "resources/term_rules/translation_terms.csv")
        self.assertGreaterEqual(len(samples), 1)
        self.assertLessEqual(len(samples), 3)
        self.assertIn("datasheet", all_tags)
        self.assertIn("parameter_table", all_tags)

    def test_manifest_filenames_are_unique_and_available_samples_exist(self):
        manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
        sample_root = Path(manifest["sample_root"])
        filenames = [sample["filename"] for sample in manifest["samples"]]

        self.assertEqual(len(filenames), len(set(filenames)))
        for filename in filenames:
            self.assertEqual(Path(filename).name, filename)
        available_samples = [sample for sample in manifest["samples"] if sample["source_status"] == "available"]
        self.assertGreaterEqual(len(available_samples), 1)
        for sample in available_samples:
            pdf_path = sample_root / sample["filename"]
            self.assertTrue(pdf_path.exists())
            self.assertTrue(pdf_path.read_bytes().startswith(b"%PDF-"))
