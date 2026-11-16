"""验证同包核定沿现有新代事务接受、重放和续跑。"""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
import json
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from app.domains.document_jobs.new_generation import (
    NewGenerationConflict, NewGenerationSubmission, TableValueColumnReplay,
    new_generation_request_sha256,
)
from app.domains.document_jobs.review import digest, observed_review_source
from app.domains.document_jobs.table_evidence import verify_report
from app.domains.resources.models import utc_now
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend, MysqlPersistenceConfig
from app.infrastructure.persistence.mysql.document_jobs import MysqlDocumentJobRepository
from app.services.document_ir.table_value_column_review import TableValueColumnCorrection, TableValueColumnReview
from app.services.tables.models import VALUE_COLUMN_SPAN_AMBIGUOUS
from tests.document_job_list_query_v2_publication_fixtures import V2PublicationFixture
from tests.test_document_job_list_query_v2_writers import FakeMysqlConnection
from tests.test_table_value_column_span import _GS008_ROWS
from tests.test_table_value_column_span_delivery import _gs008_package


class OnlineTableValueGenerationStoreTests(V2PublicationFixture, TestCase):
    @contextmanager
    def _verified_submission(self, kind):
        with (
            patch.dict("os.environ", {
                "DOCUMENT_TABLE_VALUE_PDF_BINDING_ENABLED": "true",
                "DOCUMENT_TABLE_VALUE_PDF_BINDING_COMPANY_ALLOWLIST": '[["tenant_default","company_default"]]',
            }),
            self.runtime(kind=kind, source_package=_gs008_package(_GS008_ROWS)) as (
                runtime, execution, _, job, _, _, _,
            ),
        ):
            current = execution.execute_job(job.id)
            self.assertEqual((current.status, current.quality_status), ("succeeded", "blocked"), current.error_message)
            jobs = runtime.document_job_repository
            files = runtime.document_file_repository
            result = files.get_document_file(current.result_file_id)
            source = files.get_document_file(current.source_file_id)
            raw = files.get_document_file(current.mineru_raw_result_file_id)
            verified = verify_report(current, result, file_repository=files, job_repository=jobs,
                                     file_service=runtime.file_upload_service)
            original, = (table.validation for table in verified.envelope.report.tables)
            fragment, = original.fragments
            finding = next(item for item in original.findings if item.flag.code == VALUE_COLUMN_SPAN_AMBIGUOUS)
            cell = next(item for item in original.cells if item.id == finding.evidence.cell_id)
            correction = TableValueColumnCorrection(
                source_row_index=cell.source_row_index, source_cell_index=cell.source_cell_index,
                content_sha256=cell.content_sha256, original_column_range=(cell.column, cell.column + cell.colspan),
                target_column=5, target_header="TYP",
            )
            review = TableValueColumnReview(
                schema_version="table-value-column-review/v1",
                source_pdf_sha256=source.checksum_sha256.removeprefix("sha256:"),
                content_list_sha256=original.source_content_sha256,
                json_pointer=fragment.json_pointer, page_index=fragment.page_index,
                raw_html_sha256=fragment.raw_html_sha256, normalizer_version=original.normalizer_version,
                corrections=(correction,),
            )
            intent = TableValueColumnReplay(source_file_id=source.id, source_file_sha256=source.checksum_sha256,
                raw_file_id=raw.id, raw_sha256=raw.checksum_sha256, reviews=(review,))
            submission = NewGenerationSubmission(request_id=str(uuid4()), actor_id="user_admin",
                note="复核原 PDF 的列位置", expected_source=observed_review_source(current, result),
                expected_request_snapshot_sha256=digest(current.request_snapshot), source_file=source,
                trace_id="generation-transaction", audit_id=f"audit_{uuid4().hex}", table_value_column_replay=intent,
                table_value_column_request_sha256=digest([review.model_dump(mode="json")]),
                table_value_column_files=(*verified.files, raw))
            yield jobs, files, current, submission

    def test_same_uuid_and_failed_retry_keep_private_same_package_intent(self):
        for kind in ("file", "sqlite"):
            with self.subTest(kind=kind), self._verified_submission(kind) as (jobs, files, current, submission):
                receipt, accepted, replayed = jobs.accept_document_job_new_generation(
                    current.id, submission=submission, max_retries=3)
                self.assertFalse(replayed)
                self.assertEqual((accepted.status, accepted.stage, accepted.retry_count), ("running", "parsed", 1))
                self.assertEqual(accepted.mineru_raw_result_file_id, current.mineru_raw_result_file_id)
                self.assertEqual((accepted.mineru_batch_id, accepted.mineru_data_id),
                                 (current.mineru_batch_id, current.mineru_data_id))
                self.assertIsNone(accepted.document_ir_file_id)
                self.assertIsNone(accepted.result_file_id)
                self.assertIsNone(accepted.prepared_result)
                self.assertNotIn("table_value_column_replay", accepted.model_dump())
                self.assertEqual(accepted.request_snapshot, current.request_snapshot)
                self.assertEqual(jobs.get_document_job_table_value_column_replay(current.id, 1),
                                 submission.table_value_column_replay)
                same, _, replayed = jobs.accept_document_job_new_generation(
                    current.id, submission=submission, max_retries=3)
                self.assertTrue(replayed)
                self.assertEqual(same, receipt)
                with self.assertRaises(NewGenerationConflict) as reused:
                    jobs.accept_document_job_new_generation(current.id, submission=submission.model_copy(update={
                        "table_value_column_request_sha256": digest("另一批原格核定"),
                    }), max_retries=3)
                self.assertEqual(reused.exception.reason_code, "new_generation_request_conflict")
                jobs.update_document_job(current.id, status="failed", stage="failed", failed_stage="ir_converting")
                retried = jobs.retry_document_job(current.id, expected_retry_count=1, max_retries=3,
                    retry_count=2, status="running", stage="parsed",
                    request_snapshot={**accepted.request_snapshot, "template_version_id": "其他版本"})
                self.assertIsNone(retried)
                self.assertEqual(jobs.get_document_job(current.id).retry_count, 1)
                retried = jobs.retry_document_job(current.id, expected_retry_count=1, max_retries=3,
                    retry_count=2, status="running", stage="parsed")
                self.assertEqual(retried.retry_count, 2)
                self.assertEqual(jobs.get_document_job_table_value_column_replay(current.id, 2),
                                 submission.table_value_column_replay)
                with self.assertRaises(NewGenerationConflict):
                    jobs.get_document_job_table_value_column_replay(current.id, 1)
                for snapshot in submission.table_value_column_files:
                    self.assertEqual(files.get_document_file(snapshot.id), snapshot)

    def test_legacy_accepted_intent_keeps_its_original_storage_shape_and_detector(self):
        with self._verified_submission("file") as (jobs, _, current, submission):
            original = {**submission.table_value_column_replay.model_dump(mode="json"),
                        "schema_version": "table-value-column-replay/v1"}
            old_intent = TableValueColumnReplay.model_validate_json(
                json.dumps(original, ensure_ascii=False))
            submission = submission.model_copy(update={"table_value_column_replay": old_intent})
            receipt, accepted, _ = jobs.accept_document_job_new_generation(
                current.id, submission=submission, max_retries=3)
            reloaded = jobs.get_document_job_table_value_column_replay(current.id, accepted.retry_count)
            self.assertEqual(reloaded.model_dump(mode="json"), original)
            self.assertEqual(reloaded.value_column_replay_mode, "blocker")
            recorded, _ = jobs.get_document_job_generation_request(
                current.id, request_id=submission.request_id, actor_id=submission.actor_id)
            self.assertEqual(recorded, receipt)

    def test_dependency_reservation_or_expiry_rejects_batch_without_changing_current_generation(self):
        for kind in ("file", "sqlite"):
            with self.subTest(kind=kind), self._verified_submission(kind) as (jobs, files, current, submission):
                report = next(file for file in submission.table_value_column_files if file.file_type == "quality_report")
                files.update_document_file(report.id, expires_at=utc_now() - timedelta(seconds=1))
                with self.assertRaises(NewGenerationConflict) as expired:
                    jobs.accept_document_job_new_generation(current.id, submission=submission, max_retries=3)
                self.assertEqual(expired.exception.reason_code, "new_generation_source_changed")
                self.assertEqual(jobs.get_document_job(current.id), current)
                self.assertIsNone(jobs.get_document_job_generation_request(
                    current.id, request_id=submission.request_id, actor_id=submission.actor_id))
                self.assertIsNone(jobs.get_document_job_table_value_column_replay(current.id, 0))

    def test_concurrent_new_keys_share_the_current_generation_compare(self):
        for kind in ("file", "sqlite"):
            with self.subTest(kind=kind), self._verified_submission(kind) as (jobs, _, current, submission):
                alternate = submission.model_copy(update={"request_id": str(uuid4()), "audit_id": f"audit_{uuid4().hex}"})

                def accept(request):
                    try:
                        return jobs.accept_document_job_new_generation(current.id, submission=request, max_retries=3)[0]
                    except NewGenerationConflict:
                        return None

                with ThreadPoolExecutor(max_workers=2) as pool:
                    receipts = [receipt for receipt in pool.map(accept, (submission, alternate)) if receipt is not None]
                self.assertEqual(len(receipts), 1)
                self.assertEqual(jobs.get_document_job(current.id).retry_count, 1)

    def test_standard_new_generation_keeps_v1_fingerprint_and_starts_fresh_parse(self):
        with self._verified_submission("sqlite") as (jobs, _, current, revised):
            standard = NewGenerationSubmission(request_id=revised.request_id, actor_id=revised.actor_id,
                note=revised.note, expected_source=revised.expected_source,
                expected_request_snapshot_sha256=revised.expected_request_snapshot_sha256,
                source_file=revised.source_file, trace_id=revised.trace_id, audit_id=revised.audit_id)
            v1 = digest({"schema_version": "document-new-generation-request/v1", "job_id": current.id,
                "actor_id": standard.actor_id, "expected_source": standard.expected_source.model_dump(mode="json"),
                "note": standard.note})
            self.assertEqual(new_generation_request_sha256(job_id=current.id, actor_id=standard.actor_id,
                expected_source=standard.expected_source, note=standard.note), v1)
            receipt, updated, _ = jobs.accept_document_job_new_generation(
                current.id, submission=standard, max_retries=3)
            self.assertEqual(receipt.submission_sha256, v1)
            self.assertEqual((updated.status, updated.stage), ("pending", "uploaded"))
            self.assertIsNone(updated.mineru_raw_result_file_id)
            self.assertIsNone(jobs.get_document_job_table_value_column_replay(current.id, 1))

    def test_mysql_acceptance_locks_each_frozen_dependency_in_identity_order(self):
        """只验证 MySQL 适配器的 SQL 锁范围，真实事务竞争由 file 和 SQLite 用例覆盖。"""
        with self._verified_submission("file") as (_, _, current, submission):
            snapshots = {file.id: file.model_dump_json()
                         for file in (submission.source_file, *submission.table_value_column_files)}

            class Connection(FakeMysqlConnection):
                def fetchone(self):
                    statement, args = self.sql[-1]
                    if "FROM document_files" in statement:
                        return {"payload": snapshots[args[0]]}
                    return super().fetchone()

            connection = Connection(current.model_dump_json())
            backend = MysqlPersistenceBackend(MysqlPersistenceConfig(
                host="unused", port=3306, user="unused", password="", database="unused"),
                initialize=False, connect_factory=lambda: connection)
            jobs = MysqlDocumentJobRepository(backend)
            receipt, updated, _ = jobs.accept_document_job_new_generation(current.id, submission=submission, max_retries=3)
            locks = [(statement, args[0]) for statement, args in connection.sql if "FOR UPDATE" in statement]
            self.assertIn("FROM document_jobs", locks[0][0])
            self.assertEqual(locks[0][1], current.id)
            self.assertEqual([identity for _, identity in locks[1:]], sorted(snapshots))
            self.assertTrue(all("FROM document_files" in statement for statement, _ in locks[1:]))
            self.assertEqual((receipt.accepted_generation, updated.stage), (1, "parsed"))
            self.assertEqual((connection.commits, connection.rollbacks), (1, 0))
            self.assertEqual(sum("INSERT INTO audit_events" in statement for statement, _ in connection.sql), 1)
