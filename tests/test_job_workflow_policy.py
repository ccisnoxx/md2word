from __future__ import annotations

# tests/test_job_workflow_policy.py: 保留正式资源快照共用模型的状态与兼容字段合同测试。

from unittest import TestCase

from app.domains.jobs.models import (
    JobRecord,
    SourcePdfJobContext,
    build_source_pdf_context_patch,
    sync_source_pdf_compatibility_fields,
)


class JobWorkflowPolicyTests(TestCase):
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
