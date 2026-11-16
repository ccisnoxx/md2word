"""线上数值列取证的原包边界、未决与单文档时限回归。"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from time import monotonic
from unittest import TestCase, mock

from app.domains.document_jobs.mineru_execution import MinerUExecution, _matches_mineru_result_identity
from app.domains.document_jobs.models import DocumentJobCallbackMessage, DocumentJobRecord
from app.domains.document_jobs.render_placeholders import RenderPlaceholderSource
from app.domains.document_jobs.table_value_column_sources import read_table_value_mineru_result, table_value_page_lineage
from app.domains.files.models import DocumentFileRecord
from app.domains.resources.models import utc_now
from app.services.document_ir.integrity import DocumentIntegrityError
from app.services.document_ir.mineru_converter import MinerUToDocumentIRService
from app.services.document_ir.models import DocumentIR
from app.services.document_ir.page_degradation import drop_degraded_table_groups, replace_degraded_pages
from app.services.document_ir.pdf_value_column_observer import PdfObservationUnavailable, _read_poppler
from app.services.document_ir.pdf_value_column_review_flow import verify_table_value_package_origin
from app.services.document_ir.table_placeholder import PdfCropSource, TablePlaceholderError, checksum
from app.services.tables.models import VALUE_COLUMN_SPAN_AMBIGUOUS
from app.services.tables.quality import BINDING_VALIDATOR_VERSION
from app.services.tables.validator import validate_document_tables
from tests.test_table_value_pdf_binding_poppler import _ruled_table_package


class OnlineMinerURawSourceTests(TestCase):
    def setUp(self) -> None:
        self.job = DocumentJobRecord(
            id="job", tenant_id="tenant", company_id="company", created_by="owner", source_file_id="pdf",
            template_version_id="template", status="running", stage="ir_converting", retry_count=2,
            mineru_raw_result_file_id="archive", mineru_batch_id="batch", mineru_data_id="data",
        )
        self.content = "原始归档字节".encode("utf-8")
        self.raw = DocumentFileRecord(
            id="archive", tenant_id=self.job.tenant_id, company_id=self.job.company_id, job_id=self.job.id,
            storage_provider="local_file", bucket="local", object_key="mineru.zip", original_filename="mineru.zip",
            file_type="mineru_raw_result", mime_type="application/zip", status="uploaded",
            size_bytes=len(self.content), checksum_sha256=checksum(self.content),
            expires_at=utc_now() + timedelta(days=1),
            metadata={"source_file_id": "pdf", "mineru_batch_id": "batch", "mineru_data_id": "data", "retry_count": 0},
        )
        self.jobs = mock.Mock()
        self.jobs.get_document_job.return_value = self.job
        self.files = mock.Mock()
        self.files.get_document_file.return_value = self.raw
        self.files.is_document_file_protected.return_value = False
        self.file_service = mock.Mock()
        self.file_service.read_file_content.return_value = self.content

    def read(self, *, raw=None, job=None):
        return read_table_value_mineru_result(
            job or self.job, raw or self.raw, job_repository=self.jobs,
            file_repository=self.files, file_service=self.file_service,
        )

    def test_current_pointer_can_reuse_an_older_parse_attempt(self):
        self.assertEqual(self.read(), (self.content, True))
        history = self.raw.model_copy(update={"metadata": {"source_file_id": "pdf"}})
        self.files.get_document_file.return_value = history
        self.assertEqual(self.read(raw=history), (self.content, False))

        unpinned = self.job.model_copy(update={"mineru_raw_result_file_id": None})
        self.jobs.get_document_job.return_value = unpinned
        self.files.get_document_file.return_value = self.raw
        self.assertEqual(self.read(job=unpinned), (self.content, False))

    def test_raw_identity_and_actual_bytes_fail_closed(self):
        for raw in (
            self.raw.model_copy(update={"job_id": "other-job"}),
            self.raw.model_copy(update={"deletion_claim": "scheduled"}),
            self.raw.model_copy(update={"expires_at": utc_now() - timedelta(seconds=1)}),
            self.raw.model_copy(update={"metadata": {**self.raw.metadata, "mineru_batch_id": "other-batch"}}),
            self.raw.model_copy(update={"metadata": {**self.raw.metadata, "retry_count": 3}}),
        ):
            with self.subTest(file_update=raw):
                self.files.get_document_file.return_value = raw
                with self.assertRaisesRegex(DocumentIntegrityError, "mineru_raw_result_binding_mismatch"):
                    self.read(raw=raw)

        self.files.get_document_file.return_value = self.raw
        self.file_service.read_file_content.return_value = b"x" * len(self.content)
        with self.assertRaisesRegex(DocumentIntegrityError, "mineru_raw_result_content_mismatch"):
            self.read()

    def test_raw_read_checks_current_job_again_after_io(self):
        self.jobs.get_document_job.side_effect = [
            self.job, self.job.model_copy(update={"retry_count": 3}),
        ]
        with self.assertRaisesRegex(DocumentIntegrityError, "mineru_raw_result_binding_mismatch"):
            self.read()
        self.file_service.read_file_content.assert_called_once()

    def test_page_comparison_requires_current_parse_or_frozen_replay_lineage(self):
        source_job = self.job.model_copy(update={"retry_count": 0})
        self.assertIsNone(table_value_page_lineage(source_job, self.raw))
        verified = self.raw.model_copy(update={
            "metadata": {**self.raw.metadata, "mineru_result_identity_verified": True,
                         "mineru_uploaded_source_sha256": checksum(b"source PDF")},
        })
        lineage = table_value_page_lineage(source_job, verified)
        self.assertIsNotNone(lineage)
        self.assertEqual(lineage.parse_generation, source_job.retry_count)
        self.assertIsNone(table_value_page_lineage(self.job, verified))
        self.assertEqual(table_value_page_lineage(self.job, verified, frozen=lineage), lineage)
        for field, replacement in (
            ("mineru_data_id", "other-data"),
            ("mineru_uploaded_source_sha256", checksum(b"another PDF")),
        ):
            with self.subTest(field=field):
                other = verified.model_copy(update={"metadata": {**verified.metadata, field: replacement}})
                self.assertIsNone(table_value_page_lineage(self.job, other, frozen=lineage))

    def test_provider_must_echo_the_batch_and_one_completed_matching_result(self):
        url = "https://mineru.net/result.zip"
        completed = {"data_id": "data", "state": "done", "full_zip_url": url}
        proof_inputs = {"batch_id": "batch", "data_id": "data", "full_zip_url": url}
        self.assertTrue(_matches_mineru_result_identity(
            {"batch_id": "batch", "extract_result": [completed]}, **proof_inputs,
        ))
        for payload in (
            {"extract_result": [completed]},
            {"batch_id": "old-batch", "extract_result": [completed]},
            {"batch_id": "batch", "extract_result": [completed, completed]},
            {"batch_id": "batch", "extract_result": [{**completed, "data_id": None}]},
            {"batch_id": "batch", "extract_result": [{**completed, "state": "running"}]},
            {"batch_id": "batch", "extract_result": [{**completed, "full_zip_url": "https://mineru.net/other.zip"}]},
        ):
            with self.subTest(payload=payload):
                self.assertFalse(_matches_mineru_result_identity(payload, **proof_inputs))

    def test_conflicting_callback_keeps_the_active_batch_and_data_for_polling(self):
        job = self.job.model_copy(update={"stage": "parsing", "mineru_raw_result_file_id": None})
        self.jobs.get_document_job.return_value = job
        messages = mock.Mock()
        client = mock.Mock()
        execution = MinerUExecution(
            settings=mock.Mock(stage_message_lease_seconds=60),
            job_repository=self.jobs, file_repository=self.files, file_service=self.file_service,
            lifecycle=mock.Mock(), callback_message_store=messages, mineru_config_resolver=mock.Mock(),
            mineru_client_factory=client,
        )
        expected = {"batch_id": job.mineru_batch_id, "data_id": job.mineru_data_id}
        for field in ("batch_id", "data_id"):
            with self.subTest(field=field):
                message = DocumentJobCallbackMessage(
                    id="message", job_id=job.id, job_retry_count=job.retry_count, dedupe_key="delivery",
                    payload={**expected, field: "old", "state": "done", "full_zip_url": "https://mineru.net/old.zip"},
                )
                messages.list_replayable_callback_messages.return_value = [message]
                messages.mark_callback_message_running.return_value = message.model_copy(update={"status": "running"})
                self.assertEqual(execution.process_replayable_callback_messages(job, trace_id=None), job)
                self.assertEqual(messages.mark_callback_message_ignored.call_args.kwargs["error_code"],
                                 "mineru_callback_identity_mismatch")
        self.jobs.update_document_job_if_current.assert_not_called()
        client.assert_not_called()


class OnlineTableValueObservationTests(TestCase):
    def setUp(self) -> None:
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.package, pdf = _ruled_table_package(Path(directory.name))
        source = pdf.read_bytes()
        self.source = PdfCropSource("pdf", checksum(source), source)
        self.service = MinerUToDocumentIRService()

    def convert(self, loader, **options) -> DocumentIR:
        return self.service.convert_zip(
            self.package, job_id="job", source_file_id="pdf", document_language="en",
            placeholder_source_loader=loader, auto_table_value_columns=True, **options,
        ).document

    def assert_pending(self, document, reason):
        findings = {
            finding.finding_id for report in validate_document_tables(document, validator_version=BINDING_VALIDATOR_VERSION).reports
            for finding in report.findings if finding.flag.code == VALUE_COLUMN_SPAN_AMBIGUOUS
        }
        issues = document.metadata.pdf_value_column_unresolved
        self.assertEqual(len(findings), 3)
        self.assertEqual({issue.finding_id for issue in issues}, findings)
        self.assertEqual({issue.reason for issue in issues}, {reason})

    def test_optional_pdf_absence_preserves_findings_and_integrity_failure_propagates(self):
        unavailable = mock.Mock(side_effect=TablePlaceholderError("table_placeholder_source_unavailable"))
        self.assert_pending(self.convert(unavailable), "pdf_source_unavailable")
        unavailable.assert_called_once()

        corrupt = mock.Mock(side_effect=TablePlaceholderError("table_placeholder_integrity_failed"))
        with self.assertRaisesRegex(TablePlaceholderError, "table_placeholder_integrity_failed"):
            self.convert(corrupt)

    def test_source_loader_distinguishes_wrong_pdf_owner_from_unavailable_origin(self):
        job = DocumentJobRecord(
            id="job", tenant_id="tenant", company_id="company", created_by="owner", source_file_id="pdf",
            template_version_id="template", status="running", stage="ir_converting",
        )
        source_file = DocumentFileRecord(
            id="pdf", tenant_id=job.tenant_id, company_id=job.company_id, job_id=job.id,
            storage_provider="local_file", bucket="local", object_key="source.pdf", original_filename="source.pdf",
            file_type="source_pdf", mime_type="application/pdf", status="uploaded",
            size_bytes=len(self.source.content), checksum_sha256=self.source.checksum_sha256,
            expires_at=utc_now() + timedelta(days=1),
        )
        files = mock.Mock()
        file_service = mock.Mock()
        placeholders = RenderPlaceholderSource(job_repository=mock.Mock(), file_repository=files, file_service=file_service)

        def load_verified_source():
            return placeholders.load_source(job, strict_identity=True)

        for invalid in (source_file.model_copy(update={"job_id": "other-job"}),
                        source_file.model_copy(update={"tenant_id": "other-tenant"})):
            files.get_document_file.return_value = invalid
            with self.assertRaisesRegex(TablePlaceholderError, "table_placeholder_integrity_failed"):
                self.convert(load_verified_source)
        for unavailable in (None, source_file.model_copy(update={"expires_at": utc_now() - timedelta(seconds=1)})):
            files.get_document_file.return_value = unavailable
            self.assert_pending(self.convert(load_verified_source), "pdf_source_unavailable")

        files.get_document_file.return_value = source_file.model_copy(update={"job_id": "other-job"})
        with self.assertRaisesRegex(TablePlaceholderError, "table_placeholder_source_unavailable"):
            placeholders.load_source(job)
        file_service.read_file_content.assert_not_called()

    def test_unproven_raw_and_exhausted_budget_skip_optional_pdf_read(self):
        loader = mock.Mock()
        self.assert_pending(self.convert(loader, value_column_source_pair_eligible=False), "source_pair_unverified")
        self.assert_pending(self.convert(
            loader, value_column_observation_deadline=monotonic() - 1,
        ), "pdf_observation_budget_exhausted")
        loader.assert_not_called()

    def test_poppler_subprocess_stops_on_document_deadline(self):
        with self.assertRaisesRegex(PdfObservationUnavailable, "^pdf_observation_budget_exhausted$"):
            _read_poppler(
                [sys.executable, "-c", "import time; time.sleep(5); print('late')"],
                deadline=monotonic() + 0.1,
            )

    def test_degraded_table_removes_only_final_ir_references(self):
        document = self.convert(mock.Mock(), value_column_source_pair_eligible=False)
        candidate = document.model_copy(deep=True)
        removed, _ = replace_degraded_pages(
            candidate, {0: b"page-raster"}, {0: {"reason_codes": ["render_failed"]}},
            source_pdf_sha256=self.source.checksum_sha256, dpi=144, trigger="render",
        )
        drop_degraded_table_groups(candidate, removed)
        self.assert_pending(document, "source_pair_unverified")
        self.assertEqual(candidate.metadata.pdf_value_column_unresolved, ())
        self.assertEqual(candidate.metadata.degraded_pages[0]["reason_codes"], ["render_failed"])
        DocumentIR.model_validate_json(candidate.model_dump_json())

    def test_replay_preflight_selects_the_same_v2_and_checks_origin(self):
        content = self.package.read_bytes()
        result = self.service.convert_zip(self.package, job_id="job", source_file_id="pdf", document_language="en")
        self.assertEqual(
            verify_table_value_package_origin(content, self.source),
            result.document.metadata.mineru_validation.content_list_sha256,
        )
        different_pdf = self.source.content + b"\n"
        other = PdfCropSource(self.source.file_id, checksum(different_pdf), different_pdf)
        self.assertIsNone(verify_table_value_package_origin(content, other))
