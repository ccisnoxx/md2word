from __future__ import annotations

# tests/test_job_workflow_policy.py: 针对集中 job workflow 规则的最小单元测试。

from unittest import TestCase

from app.core.job_models import JobRecord, SourcePdfJobContext, build_source_pdf_context_patch, sync_source_pdf_compatibility_fields
from app.core.job_workflow import (
    JobWorkflowViolation,
    build_cancel_transition,
    build_cleanup_local_files_transition,
    build_conversion_completed_transition,
    build_conversion_failed_transition,
    build_conversion_started_transition,
    build_mineru_callback_transition,
    build_parsed_result_conversion_started_transition,
    build_mineru_submission_failed_transition,
    build_mineru_submission_started_transition,
    build_mineru_submission_succeeded_transition,
    build_retry_transition,
    build_stage_enqueue_transition,
)


class JobWorkflowPolicyTests(TestCase):
    def test_retry_pdf_transition_resets_mineru_context(self):
        job = JobRecord(
            id="job_pdf_failed",
            source_filename="source.pdf",
            status="failed",
            progress=100,
            source_kind="source_pdf",
            source_pdf_context=SourcePdfJobContext(
                batch_id="batch_1",
                data_id="data_1",
                callback_seed="seed_1",
                upstream_status="failed",
                result_zip_url="https://mineru.net/result.zip",
            ),
            error_code="mineru_failed",
            error_message="boom",
            result_ready=True,
        )

        transition = build_retry_transition(job)

        patch = transition.as_job_update_patch(job)
        self.assertEqual(transition.resolved_status(job), "uploaded")
        self.assertEqual(patch["lifecycle_status"], "uploaded")
        self.assertEqual(patch["execution_status"], "idle")
        self.assertIsNone(patch["mineru_batch_id"])
        self.assertIsNone(patch["mineru_data_id"])
        self.assertIsNone(patch["mineru_callback_seed"])
        self.assertIsNone(patch["mineru_status"])
        self.assertEqual(patch["mineru_result_zip_url"], "https://mineru.net/result.zip")
        self.assertEqual(patch["source_pdf_context"].result_zip_url, "https://mineru.net/result.zip")
        self.assertEqual(transition.event_intents[0].kind, "job_retry_requested")

    def test_cancel_transition_rejects_converting_job(self):
        job = JobRecord(
            id="job_converting",
            source_filename="input.zip",
            status="converting",
            progress=50,
        )

        with self.assertRaises(JobWorkflowViolation) as ctx:
            build_cancel_transition(job)

        self.assertIn("暂不支持中断式取消", str(ctx.exception))

    def test_cleanup_transition_requires_completed_job(self):
        job = JobRecord(
            id="job_queued",
            source_filename="input.zip",
            status="queued",
            progress=10,
        )

        with self.assertRaises(JobWorkflowViolation) as ctx:
            build_cleanup_local_files_transition(job)

        self.assertIn("cleanup-local-files", str(ctx.exception))

    def test_mineru_callback_done_transition_marks_job_parsed(self):
        job = JobRecord(
            id="job_pdf",
            source_filename="source.pdf",
            status="parsing",
            progress=25,
            source_kind="source_pdf",
            source_pdf_context=SourcePdfJobContext(
                batch_id="batch_1",
                data_id="job_pdf",
            ),
        )

        transition = build_mineru_callback_transition(
            job,
            callback_state="done",
            batch_id="batch_1",
            data_id="job_pdf",
            full_zip_url="https://mineru.net/result.zip",
        )

        patch = transition.as_job_update_patch(job)
        self.assertEqual(transition.resolved_status(job), "parsed")
        self.assertEqual(patch["lifecycle_status"], "parsed")
        self.assertEqual(patch["execution_status"], "idle")
        self.assertEqual(patch["progress"], 60)
        self.assertEqual(patch["mineru_result_zip_url"], "https://mineru.net/result.zip")
        self.assertEqual(transition.event_intents[0].kind, "mineru_callback_processed")

    def test_mineru_callback_transition_rejects_completed_job(self):
        job = JobRecord(
            id="job_completed",
            source_filename="done.zip",
            status="completed",
            progress=100,
            result_ready=True,
            source_kind="source_pdf",
            source_pdf_context=SourcePdfJobContext(
                batch_id="batch_1",
                data_id="job_completed",
            ),
        )

        with self.assertRaises(JobWorkflowViolation) as ctx:
            build_mineru_callback_transition(
                job,
                callback_state="done",
                batch_id="batch_1",
                data_id="job_completed",
                full_zip_url="https://mineru.net/result.zip",
            )

        self.assertIn("不允许处理 MinerU callback", str(ctx.exception))

    def test_stage_enqueue_transition_marks_job_queued(self):
        job = JobRecord(
            id="job_uploaded",
            source_filename="input.zip",
            status="uploaded",
            progress=0,
        )

        transition = build_stage_enqueue_transition(job, stage="convert_package")

        patch = transition.as_job_update_patch(job)
        self.assertEqual(transition.resolved_status(job), "queued")
        self.assertEqual(patch["lifecycle_status"], "uploaded")
        self.assertEqual(patch["execution_status"], "queued")
        self.assertEqual(patch["progress"], 10)
        self.assertEqual(transition.event_intents[0].kind, "stage_enqueued")

    def test_stage_enqueue_transition_rejects_wrong_stage_owner(self):
        zip_job = JobRecord(
            id="job_zip",
            source_filename="input.zip",
            status="uploaded",
            progress=0,
        )
        pdf_job_not_parsed = JobRecord(
            id="job_pdf_not_parsed",
            source_filename="source.pdf",
            status="queued",
            progress=10,
            source_kind="source_pdf",
            lifecycle_status="uploaded",
            execution_status="queued",
            source_pdf_context=SourcePdfJobContext(),
        )

        with self.assertRaises(JobWorkflowViolation):
            build_stage_enqueue_transition(zip_job, stage="submit_to_mineru")
        with self.assertRaises(JobWorkflowViolation):
            build_stage_enqueue_transition(pdf_job_not_parsed, stage="convert_parsed_result")

    def test_parsed_result_stage_requires_parsed_idle_pdf_job(self):
        parsed_job = JobRecord(
            id="job_parsed_ready",
            source_filename="source.pdf",
            status="parsed",
            progress=60,
            source_kind="source_pdf",
            lifecycle_status="parsed",
            execution_status="idle",
            source_pdf_context=SourcePdfJobContext(),
        )

        enqueue_transition = build_stage_enqueue_transition(parsed_job, stage="convert_parsed_result")
        started_transition = build_parsed_result_conversion_started_transition(parsed_job)

        self.assertEqual(enqueue_transition.resolved_status(parsed_job), "queued")
        self.assertEqual(enqueue_transition.as_job_update_patch(parsed_job)["progress"], 65)
        self.assertEqual(started_transition.resolved_status(parsed_job), "converting")
        self.assertEqual(started_transition.as_job_update_patch(parsed_job)["progress"], 80)
        self.assertEqual(started_transition.event_intents[0].kind, "parsed_result_conversion_started")

    def test_mineru_submit_transitions_update_pdf_job_context(self):
        job = JobRecord(
            id="job_pdf_submit",
            source_filename="source.pdf",
            status="queued",
            progress=10,
            source_kind="source_pdf",
        )

        started = build_mineru_submission_started_transition(job)
        succeeded = build_mineru_submission_succeeded_transition(
            job,
            batch_id="batch_1",
            data_id="job_pdf_submit",
            callback_seed="seed_1",
        )

        self.assertEqual(started.resolved_status(job), "submitting")
        self.assertEqual(succeeded.resolved_status(job), "parsing")
        started_patch = started.as_job_update_patch(job)
        succeeded_patch = succeeded.as_job_update_patch(job)
        self.assertEqual(started_patch["execution_status"], "submitting")
        self.assertEqual(succeeded_patch["execution_status"], "parsing")
        self.assertEqual(succeeded_patch["mineru_batch_id"], "batch_1")
        self.assertEqual(succeeded.event_intents[0].kind, "mineru_submit_succeeded")

    def test_mineru_submit_transitions_reject_non_pdf_jobs(self):
        job = JobRecord(
            id="job_zip_submit",
            source_filename="input.zip",
            status="queued",
            progress=10,
        )

        with self.assertRaises(JobWorkflowViolation):
            build_mineru_submission_started_transition(job)
        with self.assertRaises(JobWorkflowViolation):
            build_mineru_submission_failed_transition(job, error_message="mineru boom")
        with self.assertRaises(JobWorkflowViolation):
            build_mineru_submission_succeeded_transition(
                job,
                batch_id="batch_1",
                data_id="job_zip_submit",
                callback_seed=None,
            )

    def test_mineru_submit_failed_transition_marks_job_failed(self):
        job = JobRecord(
            id="job_pdf_submit_failed",
            source_filename="source.pdf",
            status="submitting",
            progress=15,
            source_kind="source_pdf",
        )

        transition = build_mineru_submission_failed_transition(job, error_message="mineru boom")

        patch = transition.as_job_update_patch(job)
        self.assertEqual(transition.resolved_status(job), "failed")
        self.assertEqual(patch["lifecycle_status"], "failed")
        self.assertEqual(patch["execution_status"], "idle")
        self.assertEqual(patch["error_code"], "mineru_submit_failed")
        self.assertEqual([item.kind for item in transition.event_intents], ["mineru_submit_failed", "job_failed"])

    def test_mineru_callback_failed_transition_marks_job_failed(self):
        job = JobRecord(
            id="job_pdf_callback_failed",
            source_filename="source.pdf",
            status="parsing",
            progress=25,
            source_kind="source_pdf",
            source_pdf_context=SourcePdfJobContext(
                batch_id="batch_1",
                data_id="job_pdf_callback_failed",
            ),
        )

        transition = build_mineru_callback_transition(
            job,
            callback_state="failed",
            batch_id="batch_1",
            data_id="job_pdf_callback_failed",
            full_zip_url=None,
        )

        patch = transition.as_job_update_patch(job)
        self.assertEqual(transition.resolved_status(job), "failed")
        self.assertEqual(patch["lifecycle_status"], "failed")
        self.assertEqual(patch["execution_status"], "idle")
        self.assertEqual(patch["progress"], 100)
        self.assertEqual(patch["error_code"], "mineru_failed")
        self.assertEqual(patch["mineru_status"], "failed")
        self.assertEqual(transition.event_intents[0].kind, "mineru_callback_failed")

    def test_conversion_started_transition_marks_converting_and_clears_error(self):
        job = JobRecord(
            id="job_convert_start",
            source_filename="input.zip",
            status="queued",
            progress=10,
            error_code="old_error",
            error_message="old message",
        )

        transition = build_conversion_started_transition(job)

        patch = transition.as_job_update_patch(job)
        self.assertEqual(transition.resolved_status(job), "converting")
        self.assertEqual(patch["execution_status"], "converting")
        self.assertEqual(patch["progress"], 50)
        self.assertIsNone(patch["error_code"])
        self.assertIsNone(patch["error_message"])
        self.assertEqual(transition.event_intents[0].kind, "conversion_started")

    def test_conversion_transitions_cover_failed_and_completed_paths(self):
        job = JobRecord(
            id="job_convert",
            source_filename="input.zip",
            status="queued",
            progress=10,
            translation_mode="en2zh",
        )

        failed = build_conversion_failed_transition(
            job,
            error_code="translation_timeout",
            error_message="timeout",
        )
        completed = build_conversion_completed_transition(job, document_language="zh")

        failed_patch = failed.as_job_update_patch(job)
        completed_patch = completed.as_job_update_patch(job)
        self.assertEqual(failed.resolved_status(job), "failed")
        self.assertEqual([item.kind for item in failed.event_intents], ["translation_failed", "job_failed"])
        self.assertEqual(failed_patch["execution_status"], "idle")
        self.assertEqual(completed.resolved_status(job), "completed")
        self.assertEqual(completed_patch["lifecycle_status"], "completed")
        self.assertTrue(completed_patch["result_ready"])

    def test_job_record_projects_legacy_status_to_dual_status(self):
        legacy_job = JobRecord(
            id="job_legacy_parsing",
            source_filename="source.pdf",
            status="parsing",
            progress=25,
            source_kind="source_pdf",
        )

        self.assertEqual(legacy_job.resolved_lifecycle_status(), "uploaded")
        self.assertEqual(legacy_job.resolved_execution_status(), "parsing")
        self.assertEqual(legacy_job.projected_status(), "parsing")

    def test_source_pdf_context_patch_keeps_nested_and_legacy_fields_aligned(self):
        job = JobRecord(
            id="job_pdf_context",
            source_filename="source.pdf",
            status="parsing",
            progress=25,
            source_kind="source_pdf",
            source_pdf_context=SourcePdfJobContext(),
        )

        patch = build_source_pdf_context_patch(
            job,
            batch_id="batch_1",
            data_id="data_1",
            callback_seed="seed_1",
            upstream_status="submitted",
            result_zip_url="https://mineru.net/result.zip",
        )

        self.assertEqual(patch["source_pdf_context"].batch_id, "batch_1")
        self.assertEqual(patch["source_pdf_context"].data_id, "data_1")
        self.assertEqual(patch["source_pdf_context"].callback_seed, "seed_1")
        self.assertEqual(patch["source_pdf_context"].upstream_status, "submitted")
        self.assertEqual(patch["source_pdf_context"].result_zip_url, "https://mineru.net/result.zip")
        self.assertEqual(patch["mineru_batch_id"], "batch_1")
        self.assertEqual(patch["mineru_data_id"], "data_1")
        self.assertEqual(patch["mineru_callback_seed"], "seed_1")
        self.assertEqual(patch["mineru_status"], "submitted")
        self.assertEqual(patch["mineru_result_zip_url"], "https://mineru.net/result.zip")

    def test_job_record_read_helpers_prefer_nested_source_pdf_context(self):
        job = JobRecord(
            id="job_pdf_prefer_nested",
            source_filename="source.pdf",
            status="parsing",
            progress=25,
            source_kind="source_pdf",
            source_pdf_context=SourcePdfJobContext(
                batch_id="nested_batch",
                data_id="nested_data",
                callback_seed="nested_seed",
                upstream_status="nested_status",
                result_zip_url="https://mineru.net/nested.zip",
            ),
            mineru_batch_id="flat_batch",
            mineru_data_id="flat_data",
            mineru_callback_seed="flat_seed",
            mineru_status="flat_status",
            mineru_result_zip_url="https://mineru.net/flat.zip",
        )

        self.assertEqual(job.read_mineru_batch_id(), "nested_batch")
        self.assertEqual(job.read_mineru_data_id(), "nested_data")
        self.assertEqual(job.read_mineru_callback_seed(), "nested_seed")
        self.assertEqual(job.read_mineru_status(), "nested_status")
        self.assertEqual(job.read_mineru_result_zip_url(), "https://mineru.net/nested.zip")

    def test_sync_source_pdf_compatibility_fields_projects_nested_context(self):
        job = JobRecord(
            id="job_pdf_projected",
            source_filename="source.pdf",
            status="parsing",
            progress=25,
            source_kind="source_pdf",
            source_pdf_context=SourcePdfJobContext(
                batch_id="nested_batch",
                data_id="nested_data",
                callback_seed="nested_seed",
                upstream_status="submitted",
                result_zip_url="https://mineru.net/nested.zip",
            ),
        )

        synced = sync_source_pdf_compatibility_fields(job)

        self.assertEqual(synced.mineru_batch_id, "nested_batch")
        self.assertEqual(synced.mineru_data_id, "nested_data")
        self.assertEqual(synced.mineru_callback_seed, "nested_seed")
        self.assertEqual(synced.mineru_status, "submitted")
        self.assertEqual(synced.mineru_result_zip_url, "https://mineru.net/nested.zip")
