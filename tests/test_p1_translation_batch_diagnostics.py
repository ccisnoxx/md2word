"""Tests for P1 translation regression provider batch diagnostics reporting."""

from pathlib import Path
from unittest import TestCase

from scripts.ops.run_p1_translation_regression import (
    P1RegressionConfig,
    P1SampleResult,
    build_report,
    build_translation_batch_diagnostics,
    format_markdown_report,
    record_translation_batch_diagnostics_unavailable,
    summarize_report_translation_batch_diagnostics,
)


class P1TranslationBatchDiagnosticsTests(TestCase):
    def test_summarizes_split_children_without_storing_ai_log_ids(self):
        diagnostics = build_translation_batch_diagnostics(
            {
                "generation": 1,
                "items": [
                    {
                        "batch_id": "batch_parent",
                        "root_batch_id": "batch_parent",
                        "status": "split",
                        "page_start": 1,
                        "page_end": 20,
                        "item_count": 8,
                        "char_count": 9000,
                        "attempt_count": 1,
                        "max_attempts": 2,
                        "split_level": 0,
                        "finish_reason": "length",
                        "truncation_retry": True,
                        "provider_call_budget": 12,
                        "deterministic_batch_count": 1,
                        "error_code": "translation_provider_truncated",
                        "error_message": "provider returned incomplete JSON",
                        "ai_call_log_file_ids": ["file_ai_parent"],
                        "updated_at": "2026-06-26T00:00:00Z",
                    },
                    {
                        "batch_id": "batch_child_1",
                        "root_batch_id": "batch_parent",
                        "parent_batch_id": "batch_parent",
                        "status": "succeeded",
                        "page_start": 1,
                        "page_end": 10,
                        "item_count": 4,
                        "char_count": 4500,
                        "attempt_count": 1,
                        "max_attempts": 2,
                        "split_level": 1,
                        "finish_reason": "stop",
                        "provider_call_budget": 12,
                        "deterministic_batch_count": 1,
                        "result_file_id": "file_result_1",
                        "ai_call_log_file_ids": ["file_ai_child_1"],
                    },
                    {
                        "batch_id": "batch_child_2",
                        "root_batch_id": "batch_parent",
                        "parent_batch_id": "batch_parent",
                        "status": "succeeded",
                        "page_start": 11,
                        "page_end": 20,
                        "item_count": 4,
                        "char_count": 4300,
                        "attempt_count": 1,
                        "max_attempts": 2,
                        "split_level": 1,
                        "finish_reason": "stop",
                        "provider_call_budget": 12,
                        "deterministic_batch_count": 1,
                        "result_file_id": "file_result_2",
                        "ai_call_log_file_ids": ["file_ai_child_2"],
                    },
                ],
            }
        )

        summary = diagnostics["summary"]
        self.assertEqual(diagnostics["generation"], 1)
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["split"], 1)
        self.assertEqual(summary["leaf_total"], 2)
        self.assertEqual(summary["leaf_succeeded"], 2)
        self.assertEqual(summary["ai_call_log_file_count"], 3)
        self.assertEqual(summary["provider_call_budget"], 12)
        self.assertTrue(summary["truncation_observed"])
        self.assertIn("translation_batch_truncation_observed", diagnostics["warnings"])
        self.assertEqual(diagnostics["items"][0]["ai_call_log_file_count"], 1)
        self.assertNotIn("ai_call_log_file_ids", diagnostics["items"][0])

    def test_failed_batch_summary_marks_blocker_and_shortens_error(self):
        diagnostics = build_translation_batch_diagnostics(
            {
                "generation": 0,
                "items": [
                    {
                        "batch_id": "batch_failed",
                        "root_batch_id": "batch_failed",
                        "status": "failed",
                        "page_start": 21,
                        "page_end": 32,
                        "item_count": 20,
                        "char_count": 30000,
                        "attempt_count": 2,
                        "max_attempts": 2,
                        "retryable": False,
                        "provider_call_budget": 12,
                        "error_code": "translation_provider_invalid_json",
                        "error_message": "x" * 400,
                    }
                ],
            }
        )
        result = self._result_with_diagnostics(diagnostics)

        summary = summarize_report_translation_batch_diagnostics([result])

        self.assertEqual(diagnostics["summary"]["failed"], 1)
        self.assertLessEqual(len(diagnostics["items"][0]["error_message"]), 240)
        self.assertIn("translation_batches_failed", summary["blockers"])

    def test_report_renders_batch_summary_and_keeps_file_ids_out(self):
        diagnostics = build_translation_batch_diagnostics(
            {
                "generation": 2,
                "items": [
                    {
                        "batch_id": "batch_ok",
                        "root_batch_id": "batch_ok",
                        "status": "succeeded",
                        "page_start": 1,
                        "page_end": 8,
                        "item_count": 10,
                        "char_count": 12000,
                        "attempt_count": 1,
                        "max_attempts": 2,
                        "finish_reason": "stop",
                        "provider_call_budget": 12,
                        "deterministic_batch_count": 1,
                        "result_file_id": "file_result",
                        "ai_call_log_file_ids": ["file_ai_sensitive"],
                    }
                ],
            }
        )
        result = self._result_with_diagnostics(diagnostics)
        result.docx_openable = True
        result.qa_available = True
        result.ai_call_count = 1
        result.term_hit_rate = 1.0

        report = build_report(
            P1RegressionConfig(debug_full_text=False),
            {"samples": [{"id": "sample"}], "target_sample_count": 1},
            Path("/tmp/p1-run"),
            [result],
            [],
            None,
        )
        markdown = format_markdown_report(report)

        self.assertTrue(report["summary"]["automated_chain_met_target"])
        self.assertEqual(report["summary"]["translation_batch_diagnostics"]["available"], 1)
        self.assertIn("translation_batches", markdown)
        self.assertIn("batch_ok", markdown)
        self.assertIn("ai_logs=`1`", markdown)
        self.assertNotIn("file_ai_sensitive", markdown)
        self.assertNotIn("file_ai_sensitive", str(report))

    def test_unavailable_diagnostics_becomes_report_blocker(self):
        result = P1SampleResult(
            sample_id="sample-1",
            filename="sample.pdf",
            title="Sample",
            tags=["en"],
            status="succeeded",
            source_status="available",
        )
        result.job_id = "docjob_missing_batches"

        record_translation_batch_diagnostics_unavailable(result, RuntimeError("endpoint down"))
        summary = summarize_report_translation_batch_diagnostics([result])

        self.assertFalse(result.translation_batch_diagnostics_available)
        self.assertIn("RuntimeError", result.translation_batch_diagnostics_error or "")
        self.assertIn("translation_batch_diagnostics_unavailable", result.translation_batch_warnings)
        self.assertIn("translation_batch_diagnostics_unavailable", summary["blockers"])

    def _result_with_diagnostics(self, diagnostics: dict) -> P1SampleResult:
        result = P1SampleResult(
            sample_id="sample-1",
            filename="sample.pdf",
            title="Sample",
            tags=["en", "datasheet"],
            status="succeeded",
            source_status="available",
        )
        result.job_id = "docjob_sample"
        result.result_file_id = "file_docx"
        result.translation_batch_diagnostics_available = True
        result.translation_batch_generation = diagnostics["generation"]
        result.translation_batch_summary = diagnostics["summary"]
        result.translation_batches = diagnostics["items"]
        result.translation_batch_warnings = diagnostics["warnings"]
        return result
