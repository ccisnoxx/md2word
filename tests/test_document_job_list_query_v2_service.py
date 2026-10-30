"""v2 的真实服务、API、文件观察与表格窄重核合同。"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_runtime, require_current_user
from app.api.errors import register_api_error_handlers
from app.core.config import Settings
from app.core.errors import ApiError
from app.domains.document_jobs.list_query import DocumentJobListProjectionUnavailable
from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.document_jobs.review import ReviewBinding, ReviewSubmission, receipt_identity
from app.domains.document_jobs.router import router
from app.domains.document_jobs.service import DocumentJobService
from app.domains.document_jobs.table_evidence import _ensure_current_snapshot, table_evidence_snapshot_values
from app.domains.files.models import DocumentFileRecord
from app.domains.files.result_registration import review_source_descriptor
from app.infrastructure.persistence.file.backend import FilePersistenceBackend
from app.infrastructure.persistence.file.document_jobs import FileDocumentJobRepository
from app.infrastructure.persistence.file.files import FileDocumentFileRepository
from app.infrastructure.persistence.sqlite.backend import SqlitePersistenceBackend
from app.infrastructure.persistence.sqlite.document_jobs import SqliteDocumentJobRepository
from app.infrastructure.persistence.sqlite.files import SqliteDocumentFileRepository
from app.services.auth.models import AuthenticatedUser
from app.services.tables.evidence import TableEvidenceError

NOW = datetime(2026, 10, 30, 12, tzinfo=timezone.utc)
USER = AuthenticatedUser(id="owner", username="operator", role="operator", tenant_id="T", company_id="C")
ADMIN = USER.model_copy(update={"role": "admin"})
CHECKSUM = "sha256:" + "1" * 64


def make_job(job_id="job", **values):
    return DocumentJobRecord(id=job_id, tenant_id="T", company_id="C", created_by="owner",
        source_file_id="source", template_version_id="template@1", created_at=NOW, updated_at=NOW,
        **values)


def make_file(job_id="job", file_id="result", **values):
    return DocumentFileRecord(id=file_id, tenant_id="T", company_id="C", job_id=job_id,
        file_type="generated_word", storage_provider="local_file", bucket="local",
        object_key=f"document-jobs/T/{job_id}/generated_word/{file_id}/result.docx",
        original_filename="result.docx", mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes=10, checksum_sha256=CHECKSUM, status="uploaded", expires_at=NOW + timedelta(days=3),
        created_by="owner", created_at=NOW, updated_at=NOW, **values)


class DocumentJobListV2ServiceTests(TestCase):
    @contextmanager
    def environment(self, backend):
        with TemporaryDirectory() as directory:
            if backend == "file":
                store = FilePersistenceBackend(Path(directory))
                jobs, files = FileDocumentJobRepository(store), FileDocumentFileRepository(store)
            else:
                store = SqlitePersistenceBackend(Path(directory) / "metadata.sqlite")
                jobs, files = SqliteDocumentJobRepository(store), SqliteDocumentFileRepository(store)
            service = DocumentJobService(Settings.model_construct(document_publication_enabled=False),
                jobs, SimpleNamespace(), files)
            yield jobs, files, service

    def listing(self, service, **values):
        with patch("app.domains.document_jobs.service.utc_now", return_value=NOW):
            return service.list_jobs(user=USER, page=1, page_size=20, status_filter=None, **values)

    def verified(self, jobs, files, *, job_id="job", review="approved", mode="en2zh_pdf_to_word", **values):
        file = files.create_document_file(make_file(job_id, job_id + "-result"))
        job = jobs.create_document_job(make_job(job_id, mode=mode, status="succeeded", stage="completed",
            result_file_id=file.id, quality_status="passed", **values))
        binding = ReviewBinding(generation=job.retry_count, result_file_id=file.id, binding_state="verified",
            result_sha256=file.checksum_sha256, file_review_source_revision=file.review_source_revision,
            descriptor=review_source_descriptor(file), receipt_sha256=receipt_identity(job))
        job = jobs.update_document_job_review_if_current(job.id, submission=ReviewSubmission(
            record_id=job_id + "-review", status=review, reviewed_by="owner", reviewer_role="operator",
            reviewed_at=NOW, binding=binding))
        self.assertIsNotNone(job)
        return job, file

    def test_legacy_approved_is_filtered_by_effective_read_view(self):
        for backend in ("file", "sqlite"):
            with self.subTest(backend=backend), self.environment(backend) as (jobs, files, service):
                files.create_document_file(make_file())
                raw = jobs.create_document_job(make_job(mode="en2zh_pdf_to_word", status="succeeded", stage="completed",
                    result_file_id="result", quality_status="passed", review_status="approved"))
                baseline, _ = service.build_job_read_view(raw, user=USER, as_of=NOW)
                self.assertEqual(baseline.review_status, "unreviewed")
                result = self.listing(service, translation_qa_status="approved")
                self.assertEqual((result.total, result.items), (0, []))
                self.assertEqual(result.summary, {"succeeded": 1})
                self.assertEqual(result.filtered_summary, {})
                self.assertEqual(result.translation_qa_summary, {"unreviewed": 1, "approved": 0, "needs_fix": 0, "blocked": 0})
                self.assertEqual(jobs.get_document_job("job"), raw)

    def test_all_qa_filters_and_page_actions_use_effective_status(self):
        for backend in ("file", "sqlite"):
            with self.subTest(backend=backend), self.environment(backend) as (jobs, files, service):
                for review in ("approved", "needs_fix", "blocked"):
                    self.verified(jobs, files, job_id=review, review=review)
                jobs.create_document_job(make_job("unreviewed", mode="en2zh_pdf_to_word"))
                jobs.create_document_job(make_job("direct"))
                expected = {"unreviewed": 1, "approved": 1, "needs_fix": 1, "blocked": 1}
                for qa in (None, "all", *expected):
                    result = self.listing(service, translation_qa_status=qa)
                    self.assertEqual(result.translation_qa_summary, expected)
                    self.assertEqual(result.total, 5 if qa is None else 4 if qa == "all" else 1)
                    for view, actions in result.items:
                        self.assertEqual(len((view, actions)), 2)
                        self.assertIn("publish", actions)
                        self.assertIn("new_generation", actions)
                        if qa in expected:
                            self.assertEqual(view.review_status, qa)
                        if view.id in {"needs_fix", "blocked"}:
                            self.assertEqual(actions["download"].warning_code,
                                "review_" + view.review_status + "_not_deliverable")

    def test_file_change_invalidates_review_without_job_write(self):
        for backend in ("file", "sqlite"):
            with self.subTest(backend=backend), self.environment(backend) as (jobs, files, service):
                raw, file = self.verified(jobs, files)
                self.assertEqual(self.listing(service, translation_qa_status="approved").total, 1)
                reserved = files.reserve_document_file_deletion(file.id, claim_id="delete", now=NOW)
                self.assertEqual(reserved.review_source_revision, file.review_source_revision)
                result = self.listing(service, translation_qa_status="unreviewed")
                self.assertEqual(result.total, 1)
                self.assertEqual(result.items[0][1]["download"].disabled_reason_code, "file_deletion_reserved")
                self.assertEqual(jobs.get_document_job(raw.id), raw)

    def test_clock_is_captured_once_and_observed_file_is_reused(self):
        for backend in ("file", "sqlite"):
            with self.subTest(backend=backend), self.environment(backend) as (jobs, files, service):
                _, file = self.verified(jobs, files)
                files.update_document_file(file.id, expires_at=NOW + timedelta(seconds=1))
                # 用新的真实来源重新绑定，之后只推进列表时钟。
                source = files.get_document_file(file.id)
                binding = ReviewBinding(generation=0, result_file_id=file.id, binding_state="verified",
                    result_sha256=source.checksum_sha256, file_review_source_revision=source.review_source_revision,
                    descriptor=review_source_descriptor(source), receipt_sha256=None)
                jobs.update_document_job_review_if_current("job", submission=ReviewSubmission(record_id="second-review",
                    status="approved", reviewed_by="owner", reviewer_role="operator", reviewed_at=NOW, binding=binding))
                query = jobs.query_document_jobs
                def after_observation(value):
                    result = query(value)
                    files.reserve_document_file_deletion(file.id, claim_id="later", now=NOW)
                    return result
                with patch.object(jobs, "query_document_jobs", side_effect=after_observation), patch(
                    "app.domains.document_jobs.service.utc_now", side_effect=[NOW, NOW + timedelta(seconds=2)]) as clock:
                    result = service.list_jobs(user=USER, page=1, page_size=20, status_filter=None,
                        translation_qa_status="approved")
                self.assertEqual(clock.call_count, 1)
                self.assertEqual(result.total, 1)
                self.assertEqual(result.items[0][0].review_status, "approved")
                self.assertTrue(result.items[0][1]["download"].enabled)
                self.assertEqual(self.listing(service, translation_qa_status="approved").total, 0)

    def test_explicit_missing_observation_does_not_read_later_file(self):
        for backend in ("file", "sqlite"):
            with self.subTest(backend=backend), self.environment(backend) as (jobs, files, service):
                jobs.create_document_job(make_job(status="succeeded", stage="completed", result_file_id="result"))
                query = jobs.query_document_jobs
                def materialize_after_query(value):
                    result = query(value)
                    self.assertIsNone(result.observed_results["job"])
                    files.create_document_file(make_file())
                    return result
                with patch.object(jobs, "query_document_jobs", side_effect=materialize_after_query):
                    result = self.listing(service)
                self.assertEqual(result.items[0][1]["download"].disabled_reason_code, "result_file_missing")
                self.assertTrue(self.listing(service).items[0][1]["download"].enabled)

    def test_natural_expiry_changes_next_request_without_metadata_write(self):
        for backend in ("file", "sqlite"):
            with self.subTest(backend=backend), self.environment(backend) as (jobs, files, service):
                raw, file = self.verified(jobs, files)
                self.assertEqual(self.listing(service, translation_qa_status="approved").total, 1)
                with patch("app.domains.document_jobs.service.utc_now", return_value=file.expires_at):
                    result = service.list_jobs(user=USER, page=1, page_size=20, status_filter=None)
                self.assertEqual(result.translation_qa_summary,
                    {"unreviewed": 1, "approved": 0, "needs_fix": 0, "blocked": 0})
                self.assertEqual(result.items[0][0].review_status, "unreviewed")
                self.assertEqual(result.items[0][1]["download"].disabled_reason_code, "file_expired")
                self.assertEqual(jobs.get_document_job(raw.id), raw)
                self.assertEqual(files.get_document_file(file.id), file)

    def test_page_keeps_original_result_mismatch_and_upload_reasons(self):
        for backend in ("file", "sqlite"):
            for changes, reason in (({"tenant_id": "other"}, "result_file_mismatch"),
                    ({"status": "pending_upload"}, "result_file_not_uploaded"),
                    ({"file_type": "document_ir", "object_key": "document-jobs/T/job/document_ir/result/result.json"},
                        "result_file_mismatch")):
                with self.subTest(backend=backend, changes=changes), self.environment(backend) as (jobs, files, service):
                    file = make_file().model_copy(update=changes)
                    files.create_document_file(file)
                    raw = jobs.create_document_job(make_job(status="succeeded", stage="completed", result_file_id="result"))
                    original = service.build_job_read_view(raw, user=USER, as_of=NOW)
                    result = self.listing(service)
                    self.assertEqual(original[1]["download"].disabled_reason_code, reason)
                    self.assertEqual(result.items[0], original)

    def test_projection_unavailable_and_request_validation_keep_error_contract(self):
        with self.environment("file") as (jobs, files, service):
            with patch.object(jobs, "query_document_jobs", side_effect=DocumentJobListProjectionUnavailable()):
                with self.assertRaises(ApiError) as error:
                    self.listing(service)
                self.assertEqual((error.exception.status_code, error.exception.code), (503, "service_unavailable"))
                for parameters in ({"sort": "bad"}, {"translation_qa_status": "bad"}, {"status_group": "bad"}):
                    with self.assertRaises(ApiError) as error:
                        self.listing(service, **parameters)
                    self.assertEqual(error.exception.status_code, 400)

    def test_unknown_modern_base_is_pending_in_filter_page_and_actions(self):
        for backend in ("file", "sqlite"):
            with self.subTest(backend=backend), self.environment(backend) as (jobs, files, service):
                files.create_document_file(make_file())
                jobs.create_document_job(make_job(status="succeeded", stage="completed", result_file_id="result",
                    quality_status="passed", quality_summary={"checks_v1": {"document_base": {"quality_status": "passed"}}}))
                view, actions = self.listing(service).items[0]
                self.assertEqual(view.quality_status, "pending")
                self.assertFalse(actions["publish"].enabled)
                self.assertIn("quality_status_pending", {reason.code for reason in actions["publish"].disabled_reasons})

    def test_file_guard_uses_original_fields_and_rechecks_every_point(self):
        with self.environment("file") as (jobs, files, service):
            job = jobs.create_document_job(make_job())
            expected_values = table_evidence_snapshot_values(job)
            self.assertEqual(len(expected_values), 10)
            self.assertTrue(jobs.is_document_job_table_evidence_snapshot_current(job))
            jobs.update_document_job(job.id, progress=10)
            self.assertTrue(jobs.is_document_job_table_evidence_snapshot_current(job))
            with patch.object(jobs, "is_document_job_table_evidence_snapshot_current",
                side_effect=[True, False]) as narrow:
                _ensure_current_snapshot(job, [], file_repository=files, job_repository=jobs)
                with self.assertRaises(TableEvidenceError):
                    _ensure_current_snapshot(job, [], file_repository=files, job_repository=jobs)
            self.assertEqual(narrow.call_count, 2)
            jobs.update_document_job(job.id, archived_at=NOW)
            self.assertFalse(jobs.is_document_job_table_evidence_snapshot_current(job))

    def test_real_sqlite_api_is_page_bounded_and_keeps_actions(self):
        with self.environment("sqlite") as (jobs, files, service):
            self.verified(jobs, files)
            for index in range(6):
                jobs.create_document_job(make_job(f"pending-{index}"))
            app = FastAPI()
            app.include_router(router, prefix="/api/v1")
            register_api_error_handlers(app)
            app.dependency_overrides[get_runtime] = lambda: SimpleNamespace(document_job_service=service)
            app.dependency_overrides[require_current_user] = lambda: USER
            with TestClient(app) as client, patch.object(jobs, "list_document_jobs", side_effect=AssertionError("不得全量读取")), patch.object(
                DocumentJobRecord, "model_validate_json", wraps=DocumentJobRecord.model_validate_json) as decode, patch(
                "app.domains.document_jobs.service.utc_now", return_value=NOW):
                response = client.get("/api/v1/document-jobs", params={"translation_qa_status": "approved", "page_size": 1})
                self.assertEqual(response.status_code, 200, response.text)
                payload = response.json()
                self.assertEqual(payload["total"], 1)
                self.assertEqual(payload["items"][0]["review_status"], "approved")
                self.assertIn("publish", payload["items"][0]["available_actions"])
                self.assertEqual(decode.call_count, len(payload["items"]))
                decode.reset_mock()
                response = client.get("/api/v1/document-jobs", params={"translation_qa_status": "approved", "page": 99, "page_size": 1})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["items"], [])
                self.assertEqual(response.json()["total"], 1)
                self.assertEqual(decode.call_count, 0)


from tests.document_job_list_query_v2_publication_fixtures import V2PublicationFixture


class DocumentJobListV2PublicationTests(V2PublicationFixture, TestCase):
    def test_legacy_real_table_report_publication_action_is_page_bounded(self):
        """历史兼容任务的实际表格、预览与发布检查完整保留，证明窄读覆盖全部重核点。"""
        for kind in ("file", "sqlite"):
            with self.subTest(kind=kind), self.publication_runtime(kind=kind) as (
                    runtime, job, admin, user, client, headers, provider):
                from tests import test_fastapi_jobs_backend as support
                repository = runtime.document_job_repository
                result = runtime.document_file_repository.get_document_file(job.result_file_id)
                self.assertGreater(result.metadata["table_evidence_summary"]["table_count"], 0)
                admin_headers = support.build_auth_header(client, "admin", "admin-pass")
                with patch.object(repository, "is_document_job_table_evidence_snapshot_current",
                    wraps=repository.is_document_job_table_evidence_snapshot_current) as guard:
                    if kind == "sqlite":
                        with patch.object(repository, "list_document_jobs", side_effect=AssertionError("不得全量读取任务")), patch.object(
                            DocumentJobRecord, "model_validate_json", wraps=DocumentJobRecord.model_validate_json) as decode_json, patch.object(
                            DocumentJobRecord, "model_validate", wraps=DocumentJobRecord.model_validate) as decode:
                            response = client.get("/api/v1/document-jobs", headers=admin_headers, params={"page_size": 1})
                        self.assertEqual(decode_json.call_count + decode.call_count, 1)
                    else:
                        response = client.get("/api/v1/document-jobs", headers=admin_headers, params={"page_size": 1})
                self.assertEqual(response.status_code, 200, response.text)
                payload = response.json()
                self.assertEqual(payload["total"], 1)
                self.assertEqual(payload["items"][0]["delivery_status"], "ready_to_publish")
                self.assertTrue(payload["items"][0]["available_actions"]["publish"]["enabled"], payload)
                self.assertGreaterEqual(guard.call_count, 8)
                self.assertEqual(len(provider.inputs), 1)

    def test_modern_table_layout_risk_remains_pending_and_cannot_publish(self):
        with self.runtime(quality="passed", pages=True) as (runtime, execution, provider, job, user, client, headers):
            job = self.install_publication_resources(runtime, execution, job)
            job = execution.execute_job(job.id)
            self.assertEqual(job.status, "succeeded", job.error_message)
            self.assertEqual(job.quality_status, "pending")
            self.assertEqual(job.quality_summary["checks_v1"]["document_base"]["reason_code"], "base_risk_unclassified")
            self.assertGreater(job.quality_summary["table_evidence"]["table_count"], 0)
            runtime.settings.document_publication_enabled = True
            _, actions = runtime.document_job_service.build_job_read_view(job,
                user=user.model_copy(update={"role": "admin"}))
            self.assertFalse(actions["publish"].enabled)
            self.assertIn("quality_status_pending", {reason.code for reason in actions["publish"].disabled_reasons})
