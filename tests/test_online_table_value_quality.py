"""已登记数值列实物证据在质量读取和批准时的定向合同。"""
from __future__ import annotations

from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch

from app.domains.document_jobs.use_cases import review_writer
from app.services.document_ir.models import DocumentIR
from app.services.document_ir.table_value_column_review import (
    PdfValueColumnUnresolved, TableValueColumnCorrection, TableValueColumnReview,
    attach_table_value_column_reviews,
)
from app.services.tables.validator import validate_document_tables
from tests.document_job_list_query_v2_publication_fixtures import V2PublicationFixture
from tests.test_table_value_column_span import _CODE, _GS008_ROWS
from tests.test_table_value_column_span_delivery import _gs008_package


class OnlineTableValueQualityTests(V2PublicationFixture, TestCase):
    def _install_review(self, runtime, execution, job, *, repair_count, bad_unresolved=False):
        """登记有确定核定的 IR，继续走正式 Word 写入、认证及报告登记。"""
        files = runtime.file_upload_service
        ir = execution.rendering.results.get_document_ir_file(job)
        document = DocumentIR.model_validate_json(files.read_file_content(ir))
        report, = validate_document_tables(document).reports
        fragment, = report.fragments
        findings = [item for item in report.findings if item.flag.code == _CODE]
        cells = {cell.id: cell for cell in report.cells}
        pdf = execution.rendering.placeholders.load_source(job)
        corrections = []
        for item, (column, header) in zip(findings[:repair_count], ((5, "TYP"), (6, "MAX"))):
            cell = cells[item.flag.cell_id]
            corrections.append(TableValueColumnCorrection(
                source_row_index=cell.source_row_index, source_cell_index=cell.source_cell_index,
                content_sha256=cell.content_sha256, original_column_range=(cell.column, cell.column + cell.colspan),
                target_column=column, target_header=header,
            ))
        review = TableValueColumnReview(
            schema_version="table-value-column-review/v1",
            source_pdf_sha256=pdf.checksum_sha256.removeprefix("sha256:"),
            content_list_sha256=report.source_content_sha256, json_pointer=fragment.json_pointer,
            page_index=fragment.page_index, raw_html_sha256=fragment.raw_html_sha256,
            normalizer_version=report.normalizer_version, corrections=tuple(corrections),
        )
        attach_table_value_column_reviews(document, (review,), report.source_content_sha256, lambda: pdf)
        document.metadata.pdf_value_column_unresolved = tuple(
            PdfValueColumnUnresolved(
                finding_id="table-finding:" + "0" * 64 if bad_unresolved else item.finding_id,
                fragment_id=item.evidence.fragment_id, source_row_index=item.evidence.source_row_index,
                source_cell_index=item.evidence.source_cell_index, reason="fixture_private_machine_value",
            )
            for item in findings[repair_count:]
        )
        version = files.register_generated_content(
            tenant_id=job.tenant_id, company_id=job.company_id, job_id=job.id, created_by=job.created_by,
            file_type="document_ir", filename="value-columns.document-ir.json", mime_type="application/json",
            content=document.model_dump_json().encode(), metadata=ir.metadata,
        )
        runtime.document_job_repository.update_document_job(job.id, document_ir_file_id=version.id)
        return findings

    def _approve(self, client, headers, job_id):
        url = f"/api/v1/document-jobs/{job_id}/review"
        view = client.get(url, headers=headers)
        self.assertEqual(view.status_code, 200, view.text)
        source = view.json()["source"]
        source.pop("ir_file_id")
        return client.patch(url, headers=headers, json={"status": "approved", "expected_source": source})

    def test_quality_projection_only_exposes_active_original_finding_and_safe_reason(self):
        with self.runtime(source_package=_gs008_package(_GS008_ROWS)) as (
            runtime, execution, _, job, _, client, headers,
        ):
            _, pending = self._install_review(runtime, execution, job, repair_count=1)
            result = execution.execute_job(job.id)
            self.assertEqual((result.status, result.quality_status), ("succeeded", "blocked"), result.error_message)
            response = client.get(f"/api/v1/document-jobs/{job.id}/quality/tables", headers=headers)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertNotIn("fixture_private_machine_value", response.text)
            body = response.json()
            self.assertEqual(body["source"]["generation"], result.retry_count)
            table, = body["items"]
            self.assertEqual(table["unresolved_value_columns"], [{
                "finding_id": pending.finding_id,
                "fragment_id": pending.evidence.fragment_id,
                "source_page_index": pending.evidence.page_index,
                "bbox": list(pending.evidence.bbox),
                "source_row_index": pending.evidence.source_row_index,
                "source_cell_index": pending.evidence.source_cell_index,
                "reason_code": "pdf_observation_unavailable",
            }])

    def test_unknown_unresolved_finding_cannot_become_a_selected_result(self):
        with self.runtime(source_package=_gs008_package(_GS008_ROWS)) as (
            runtime, execution, _, job, _, _, _,
        ):
            self._install_review(runtime, execution, job, repair_count=1, bad_unresolved=True)
            result = execution.execute_job(job.id)
            self.assertEqual(result.status, "failed")
            self.assertIsNone(result.result_file_id)

    def test_approval_rejects_missing_or_changed_report_then_accepts_restored_evidence(self):
        with self.runtime(source_package=_gs008_package(_GS008_ROWS)) as (
            runtime, execution, _, job, _, client, headers,
        ):
            self._install_review(runtime, execution, job, repair_count=2)
            result = execution.execute_job(job.id)
            self.assertEqual(result.status, "succeeded", result.error_message)
            record = runtime.document_file_repository.get_document_file(result.result_file_id)
            report_id = record.metadata["table_evidence_report"]["report_file_id"]
            response = client.get(f"/api/v1/document-jobs/{job.id}/quality/tables", headers=headers)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertNotIn("unresolved_value_columns", response.json()["items"][0])

            original_read = runtime.file_upload_service.read_file_content
            for missing, reason in (
                (True, "review_result_unavailable"), (False, "review_result_integrity_conflict"),
            ):
                def read_damaged(file):
                    if file.id == report_id:
                        if missing:
                            raise FileNotFoundError()
                        return original_read(file) + b" "
                    return original_read(file)

                with self.subTest(missing=missing), patch.object(
                    runtime.file_upload_service, "read_file_content", side_effect=read_damaged,
                ):
                    rejected = self._approve(client, headers, job.id)
                    self.assertEqual(rejected.status_code, 409, rejected.text)
                    self.assertEqual(rejected.json()["error"]["reason_code"], reason)
                    self.assertEqual(runtime.document_job_repository.get_document_job(job.id).review_status, "unreviewed")

            approved = self._approve(client, headers, job.id)
            self.assertEqual(approved.status_code, 200, approved.text)

    def test_approval_rechecks_report_descriptor_after_real_validation(self):
        with self.runtime(source_package=_gs008_package(_GS008_ROWS)) as (
            runtime, execution, _, job, _, client, headers,
        ):
            self._install_review(runtime, execution, job, repair_count=2)
            result = execution.execute_job(job.id)
            self.assertEqual(result.status, "succeeded", result.error_message)
            verify = review_writer.verify_report

            def verify_then_change_report(*args, **kwargs):
                evidence = verify(*args, **kwargs)
                report_id = evidence.summary["report_file_id"]
                file = runtime.document_file_repository.get_document_file(report_id)
                runtime.document_file_repository.update_document_file(
                    report_id, metadata={**file.metadata, "generation": evidence.job.retry_count + 1},
                )
                return evidence

            with patch.object(review_writer, "verify_report", side_effect=verify_then_change_report):
                rejected = self._approve(client, headers, job.id)
            self.assertEqual(rejected.status_code, 409, rejected.text)
            self.assertEqual(rejected.json()["error"]["reason_code"], "review_result_integrity_conflict")
            self.assertIsNone(runtime.document_job_repository.get_document_job(job.id).current_review_record_id)

    def test_removed_correction_marker_cannot_bypass_receipt_guard(self):
        with self.runtime(source_package=_gs008_package(_GS008_ROWS)) as (
            runtime, execution, _, job, _, client, headers,
        ):
            self._install_review(runtime, execution, job, repair_count=2)
            result = execution.execute_job(job.id)
            self.assertEqual(result.status, "succeeded", result.error_message)
            repository = runtime.document_file_repository
            record = repository.get_document_file(result.result_file_id)
            metadata = deepcopy(record.metadata)
            metadata.pop("table_evidence")
            metadata.pop("table_evidence_report")
            metadata.pop("table_rendering")
            repository.update_document_file(record.id, metadata=metadata)
            rejected = self._approve(client, headers, job.id)
            self.assertEqual(rejected.status_code, 409, rejected.text)
            self.assertEqual(rejected.json()["error"]["reason_code"], "review_result_integrity_conflict")
            self.assertIsNone(runtime.document_job_repository.get_document_job(job.id).current_review_record_id)
