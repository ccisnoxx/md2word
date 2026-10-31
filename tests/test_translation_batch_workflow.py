"""翻译批次代次 reducer 的纯合同测试。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from app.domains.document_jobs.models import DocumentJobTranslationBatchRecord
from app.domains.document_jobs.workflow import (
    TranslationRootPlan,
    reduce_translation_generation,
    validate_translation_batch_tree,
)


class TranslationBatchWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = TranslationRootPlan(
            batch_id="root-01",
            job_id="job-01",
            generation=0,
            job_retry_count=0,
            source_document_ir_file_id="source-ir-01",
            language_pair="en2zh",
            item_ids=("item-01", "item-02"),
            item_count=2,
            char_count=20,
            page_start=1,
            page_end=1,
            term_version_id="term-01",
            term_snapshot_hash="hash-01",
            deterministic_batch_count=1,
            provider_call_budget=4,
            max_attempts=2,
        )

    def batch(self, **changes: object) -> DocumentJobTranslationBatchRecord:
        values: dict[str, object] = {
            "id": "root-01",
            "job_id": "job-01",
            "job_retry_count": 0,
            "generation": 0,
            "root_batch_id": "root-01",
            "parent_batch_id": None,
            "status": "pending",
            "page_start": 1,
            "page_end": 1,
            "item_ids": ["item-01", "item-02"],
            "item_count": 2,
            "char_count": 20,
            "split_level": 0,
            "attempt_count": 0,
            "max_attempts": 2,
            "deterministic_batch_count": 1,
            "provider_call_budget": 4,
            "source_document_ir_file_id": "source-ir-01",
            "language_pair": "en2zh",
            "term_version_id": "term-01",
            "term_snapshot_hash": "hash-01",
        }
        values.update(changes)
        return DocumentJobTranslationBatchRecord.model_validate(values)

    def reduce(
        self,
        batches: list[DocumentJobTranslationBatchRecord],
        *,
        job_status: str = "running",
        job_stage: str = "translating",
        budget: int | None = None,
        expected_plans: list[TranslationRootPlan] | None = None,
    ):
        return reduce_translation_generation(
            job_id="job-01",
            job_status=job_status,
            job_stage=job_stage,
            generation=0,
            expected_plans=expected_plans or [self.plan],
            batches=batches,
            provider_call_budget=budget,
        )

    def test_pending_and_zero_unit_have_explicit_outcomes(self) -> None:
        self.assertEqual(self.reduce([self.batch()]).outcome, "not_started")
        empty = reduce_translation_generation(
            job_id="job-01",
            job_status="running",
            job_stage="translating",
            generation=0,
            expected_plans=[],
            batches=[],
        )
        self.assertEqual(empty.outcome, "completed")
        self.assertEqual(empty.leaf_count, 0)

    def test_terminal_job_status_precedes_empty_or_historical_batch_tree(self) -> None:
        failed = self.reduce([], job_status="failed")
        self.assertEqual(failed.outcome, "failed")
        self.assertEqual(failed.reason_code, "translation_failed")

        failed_with_active_history = self.reduce(
            [
                self.batch(status="running", attempt_count=1, lease_owner="worker-01"),
            ],
            job_status="failed",
        )
        self.assertEqual(failed_with_active_history.outcome, "failed")
        self.assertEqual(failed_with_active_history.active_leaf_count, 0)
        self.assertEqual(failed_with_active_history.retryable_failed_leaf_count, 0)
        self.assertEqual(
            failed_with_active_history.rows[0].failure_disposition,
            "stopped",
        )

        succeeded = self.reduce(
            [self.batch(id="orphan", root_batch_id="unknown", item_ids=["other"], item_count=1)],
            job_status="succeeded",
        )
        self.assertEqual(succeeded.outcome, "completed")
        self.assertIsNone(succeeded.tree.reason_code)


    def test_completed_and_validating_outcomes_keep_leaf_counts(self) -> None:
        succeeded = self.batch(status="succeeded", attempt_count=1, result_file_id="result-01")
        completed = self.reduce([succeeded])
        self.assertEqual(completed.outcome, "completed")
        self.assertEqual((completed.leaf_count, completed.succeeded_leaf_count), (1, 1))

        validating = self.reduce([succeeded], job_stage="translation_validating")
        self.assertEqual(validating.outcome, "validating")

        canceled = self.reduce([succeeded], job_status="canceled")
        self.assertEqual(canceled.outcome, "canceled")

    def test_terminal_failure_wins_over_active_sibling_and_marks_stopped(self) -> None:
        failed = self.batch(
            status="failed",
            attempt_count=2,
            retryable=False,
            error_code="provider_invalid_json",
        )
        sibling = self.batch(
            id="root-02",
            root_batch_id="root-02",
            item_ids=["item-03"],
            item_count=1,
            char_count=4,
            page_start=2,
            page_end=2,
            deterministic_batch_count=2,
            status="running",
            attempt_count=1,
            lease_owner="worker-01",
            lease_expires_at=datetime.now(timezone.utc) + timedelta(minutes=1),
        )
        sibling_plan = TranslationRootPlan(
            batch_id="root-02",
            job_id="job-01",
            generation=0,
            job_retry_count=0,
            source_document_ir_file_id="source-ir-01",
            language_pair="en2zh",
            item_ids=("item-03",),
            item_count=1,
            char_count=4,
            page_start=2,
            page_end=2,
            term_version_id="term-01",
            term_snapshot_hash="hash-01",
            deterministic_batch_count=2,
            provider_call_budget=4,
            max_attempts=2,
        )
        result = reduce_translation_generation(
            job_id="job-01",
            job_status="running",
            job_stage="translating",
            generation=0,
            expected_plans=[self.plan, sibling_plan],
            batches=[failed, sibling],
            provider_call_budget=4,
        )
        self.assertEqual(result.outcome, "failed")
        self.assertEqual(result.failure_batch_id, "root-01")
        self.assertEqual(result.reason_code, "attempts_exhausted")
        self.assertEqual(
            {row.batch_id: row.failure_disposition for row in result.rows},
            {"root-01": "terminal", "root-02": "stopped"},
        )

    def test_terminal_failure_stops_retryable_failed_sibling_and_counts_match_rows(self) -> None:
        terminal = self.batch(
            status="failed",
            attempt_count=2,
            retryable=False,
            error_code="provider_invalid_json",
        )
        retryable = self.batch(
            id="root-02",
            root_batch_id="root-02",
            item_ids=["item-03"],
            item_count=1,
            char_count=4,
            page_start=2,
            page_end=2,
            deterministic_batch_count=2,
            status="failed",
            attempt_count=1,
            retryable=True,
            error_code="translation_failed",
        )
        plan = TranslationRootPlan(
            batch_id="root-02",
            job_id="job-01",
            generation=0,
            job_retry_count=0,
            source_document_ir_file_id="source-ir-01",
            language_pair="en2zh",
            item_ids=("item-03",),
            item_count=1,
            char_count=4,
            page_start=2,
            page_end=2,
            term_version_id="term-01",
            term_snapshot_hash="hash-01",
            deterministic_batch_count=2,
            provider_call_budget=4,
            max_attempts=2,
        )
        result = self.reduce([terminal, retryable], expected_plans=[self.plan, plan])
        self.assertEqual(result.outcome, "failed")
        self.assertEqual(result.terminal_failed_leaf_count, 1)
        self.assertEqual(result.retryable_failed_leaf_count, 0)
        self.assertEqual(
            {row.batch_id: row.failure_disposition for row in result.rows},
            {"root-01": "terminal", "root-02": "stopped"},
        )

    def test_retrying_and_budget_exhaustion_are_distinct(self) -> None:
        retrying = self.batch(
            status="failed",
            attempt_count=1,
            retryable=True,
            error_code="translation_failed",
        )
        result = self.reduce([retrying], budget=4)
        self.assertEqual(result.outcome, "retrying")
        self.assertEqual(result.retryable_failed_leaf_count, 1)
        self.assertEqual(result.rows[0].failure_disposition, "retrying")

        exhausted = self.batch(
            status="failed",
            attempt_count=1,
            retryable=True,
            error_code="translation_failed",
        )
        result = self.reduce([exhausted], budget=1)
        self.assertEqual(result.outcome, "failed")
        self.assertEqual(result.reason_code, "call_budget_exhausted")
        self.assertEqual(result.terminal_failed_leaf_count, 1)
        self.assertEqual(result.retryable_failed_leaf_count, 0)

    def test_running_lease_that_owns_final_budget_is_not_failed(self) -> None:
        running = self.batch(
            status="running",
            attempt_count=1,
            lease_owner="worker-01",
            lease_expires_at=datetime.now(timezone.utc) + timedelta(minutes=1),
        )
        result = self.reduce([running], budget=1)
        self.assertEqual(result.outcome, "running")
        self.assertEqual(result.active_leaf_count, 1)

    def test_running_second_attempt_is_reported_as_retrying(self) -> None:
        running = self.batch(
            status="running",
            attempt_count=2,
            lease_owner="worker-02",
            lease_expires_at=datetime.now(timezone.utc) + timedelta(minutes=1),
        )
        result = self.reduce([running])
        self.assertEqual(result.outcome, "retrying")
        self.assertEqual(result.rows[0].failure_disposition, "retrying")

    def test_split_requires_two_deterministic_children_and_exact_partition(self) -> None:
        parent = self.batch(status="split", attempt_count=1)
        first = self.batch(
            id="root-01_s1_01",
            parent_batch_id="root-01",
            status="succeeded",
            split_level=1,
            item_ids=["item-01"],
            item_count=1,
            char_count=10,
            result_file_id="result-01",
        )
        second = self.batch(
            id="root-01_s1_02",
            parent_batch_id="root-01",
            status="succeeded",
            split_level=1,
            item_ids=["item-02"],
            item_count=1,
            char_count=10,
            result_file_id="result-02",
        )
        self.assertTrue(
            validate_translation_batch_tree(
                job_id="job-01",
                generation=0,
                expected_plans=[self.plan],
                batches=[parent, first, second],
            ).valid
        )
        summary = self.reduce([parent, first, second])
        self.assertEqual(summary.outcome, "completed")
        self.assertEqual(summary.leaf_count, 2)
        self.assertEqual(summary.succeeded_leaf_count, 2)
        self.assertEqual(
            {row.batch_id: row.failure_disposition for row in summary.rows},
            {"root-01": "superseded", "root-01_s1_01": "none", "root-01_s1_02": "none"},
        )

        invalid = self.reduce([parent, first])
        self.assertEqual(invalid.outcome, "failed")
        self.assertEqual(invalid.reason_code, "translation_batch_tree_invalid")

    def test_canceled_leaf_is_state_invalid_and_old_generation_is_tree_invalid(self) -> None:
        canceled = self.batch(status="canceled")
        result = self.reduce([canceled])
        self.assertEqual(result.outcome, "failed")
        self.assertEqual(result.reason_code, "translation_batch_state_invalid")

        old_generation = self.batch(generation=1, job_retry_count=1)
        result = self.reduce([old_generation])
        self.assertEqual(result.outcome, "failed")
        self.assertEqual(result.reason_code, "translation_batch_tree_invalid")

    def test_expired_lease_retries_when_resources_remain_and_fails_when_exhausted(self) -> None:
        expired = self.batch(
            status="running",
            attempt_count=1,
            lease_owner="worker-01",
            lease_expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            # claim 会将旧 failed 的 retryable 清零；lease 恢复不能依赖该标志。
            retryable=False,
        )
        result = self.reduce([expired], budget=4)
        self.assertEqual(result.outcome, "retrying")

        exhausted = self.batch(
            status="running",
            attempt_count=2,
            lease_owner="worker-01",
            lease_expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            retryable=False,
        )
        result = self.reduce([exhausted], budget=4)
        self.assertEqual(result.outcome, "failed")
        self.assertEqual(result.reason_code, "attempts_exhausted")
        self.assertEqual(result.terminal_failed_leaf_count, 1)
        self.assertEqual(result.rows[0].failure_disposition, "terminal")

        budget_exhausted = self.batch(
            status="running",
            attempt_count=1,
            lease_owner="worker-01",
            lease_expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            retryable=False,
        )
        result = self.reduce([budget_exhausted], budget=1)
        self.assertEqual(result.outcome, "failed")
        self.assertEqual(result.reason_code, "call_budget_exhausted")


if __name__ == "__main__":
    unittest.main()
