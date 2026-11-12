"""验证原生表格分数、来源 Grid 诊断和单元格 Token 各自的口径。"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from docx import Document

from app.services.document_ir.integrity import DocumentIntegrityError
from app.services.renderer.docx_quality import analyze_docx_quality_bytes
from scripts.dev.run_datasheet_quality_baseline import observation, sha256, table_and_token_observations


class DatasheetQualityCollectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = Document()
        table = self.document.add_table(rows=1, cols=2)
        table.cell(0, 0).text = "PIN"
        table.cell(0, 1).text = "12"
        content = BytesIO()
        self.document.save(content)
        self.annotation = {
            "id": "pin-table", "source_pointers": ["/0/0"], "rows": 1, "columns": 2,
            "header_rows": [], "merges": [], "tokens": [[0, 1, "number", "12"]],
        }
        self.result = SimpleNamespace(
            docx_quality=analyze_docx_quality_bytes(content.getvalue()),
            renderer_metadata={
                "table_rendering": {"tables": [{
                    "output_table_index": 0,
                    "logical_group_id": "pin-table",
                    "fragments": [{"source_span": {"json_pointer": "/0/0"}}],
                }]},
                "table_evidence": {"tables": [{
                    "logical_group_id": "pin-table",
                    "source_grid": {"rows": 1, "columns": 2, "header_rows": [0]},
                    "validation": {"cells": []},
                }]},
            },
        )

    def test_native_accuracy_scores_word_and_preserves_grid_difference(self) -> None:
        table, tokens = table_and_token_observations([self.annotation], self.document, self.result)

        self.assertEqual(table["matched"], 1)
        self.assertEqual(table["reasons"], [])
        self.assertEqual(table["source_grid_differences"], [{
            "id": "pin-table", "actual_rows": 1, "actual_columns": 2, "actual_header_rows": [0],
        }])
        self.assertEqual(tokens["matched"], {"number": 1})

    def test_word_header_mismatch_still_fails_native_accuracy(self) -> None:
        expected = {**self.annotation, "header_rows": [0]}
        table, tokens = table_and_token_observations([expected], self.document, self.result)

        self.assertEqual(table["matched"], 0)
        self.assertEqual(table["reasons"][0]["reason"], "header_rows")
        self.assertEqual(tokens["matched"], {"number": 1})

    def test_same_word_table_cannot_match_multiple_annotations(self) -> None:
        duplicate_annotation = {**self.annotation, "id": "another-table"}
        table, tokens = table_and_token_observations(
            [self.annotation, duplicate_annotation], self.document, self.result,
        )

        self.assertEqual(table["matched"], 0)
        self.assertEqual([reason["reason"] for reason in table["reasons"]],
                         ["native_table_claimed_by_multiple_annotations"] * 2)
        self.assertEqual(tokens["matched"], {})

    def test_observation_keeps_safe_conformance_for_success_and_failure(self) -> None:
        summary = {
            "schema_version": "template-conformance/v1", "mode": "preserve_template",
            "broken_relationship_count": 0, "blocking_flags": [], "template_docx_sha256": "a" * 64,
        }
        blocker = "template_conformance:header_media_missing"
        with TemporaryDirectory() as temporary:
            package = Path(temporary)
            source = package / "sample_origin.pdf"
            source.write_bytes(b"PDF fixture")
            layout = package / "sample_content_list_v2.json"
            layout.write_bytes(b"[]")
            sample = {"sample_id": "sample", "pdf_sha256": sha256(source), "content_list_v2_sha256": sha256(layout)}

            def convert(**kwargs):
                self.document.save(kwargs["output_path"])
                return SimpleNamespace(pages=1, quality_flags=[], renderer_metadata={
                    "template_conformance": summary, "table_evidence": {"tables": [], "status": "pass"},
                    "mineru_validation": {"package_sha256": "fixture"},
                })

            with patch("scripts.dev.run_datasheet_quality_baseline.run_conversion", side_effect=convert):
                passed = observation(sample, package, package)
            self.assertEqual(passed["template_conformance"]["status"], "passed")
            self.assertNotIn("template_docx_sha256", passed["template_conformance"])

            error = DocumentIntegrityError("DocumentIR→DOCX", {
                "blocking_quality_flags": [blocker], "template_conformance": {**summary, "blocking_flags": [blocker]},
            })
            with patch("scripts.dev.run_datasheet_quality_baseline.run_conversion", side_effect=error):
                blocked = observation(sample, package, package)
            self.assertEqual(blocked["conversion"]["status"], "failed")
            self.assertEqual(blocked["template_conformance"]["status"], "blocked")
