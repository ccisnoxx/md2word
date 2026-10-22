"""验证真实任务服务的下载分类、发布核心资格与已有 metadata 拒绝。"""

import tempfile
from datetime import timedelta
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from app.core.errors import ApiError
from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.files.models import DocumentFileRecord
from app.domains.resources.models import utc_now
from app.services.auth.models import AuthenticatedUser
from tests import test_fastapi_jobs_backend as fixtures


class DocumentJobDownloadAvailabilityTests(TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.runtime = fixtures.build_test_runtime(Path(self.directory.name))
        self.service = self.runtime.document_job_service
        self.operator = AuthenticatedUser(
            id="owner", username="operator", role="operator", tenant_id="tenant", company_id="company",
        )
        self.admin = self.operator.model_copy(update={"id": "admin", "role": "admin"})
        self.sequence = 0

    def _result(self, *, file_patch=None, **job_patch):
        self.sequence += 1
        job_id = f"availability_{self.sequence}"
        file = DocumentFileRecord(
            id=f"result_{self.sequence}", tenant_id="tenant", company_id="company", job_id=job_id,
            file_type="generated_word", storage_provider="s3", bucket="private-bucket",
            object_key=f"private/{job_id}/main.docx", original_filename="main.docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            size_bytes=10, status="uploaded", expires_at=utc_now() + timedelta(hours=1),
        )
        if file_patch:
            file = DocumentFileRecord.model_validate({**file.model_dump(mode="python"), **file_patch})
        self.runtime.document_file_repository.create_document_file(file)
        job = DocumentJobRecord(
            **{
                "id": job_id, "tenant_id": "tenant", "company_id": "company", "created_by": "owner",
                "source_file_id": f"source_{self.sequence}", "template_version_id": "template",
                "status": "succeeded", "stage": "completed", "result_file_id": file.id, **job_patch,
            }
        )
        self.runtime.document_job_repository.create_document_job(job)
        return job, file

    def test_warning_priority_and_internal_download_do_not_promote_delivery(self):
        cases = (
            ("blocked", "blocked", "quality_blocked_not_deliverable"),
            ("blocked", "needs_fix", "quality_blocked_not_deliverable"),
            ("blocked", "unreviewed", "quality_blocked_not_deliverable"),
            ("pending", "blocked", "review_blocked_not_deliverable"),
            ("pending", "needs_fix", "review_needs_fix_not_deliverable"),
            ("pending", "unreviewed", "document_unreviewed_not_deliverable"),
            ("pending", "approved", "quality_pending_not_deliverable"),
            ("warning", "approved", None),
            ("passed", "approved", None),
        )
        for quality, review, warning_code in cases:
            with self.subTest(quality=quality, review=review):
                job, file = self._result(quality_status=quality, review_status=review)
                action = self.service.build_available_actions(job, user=self.admin)["download"]
                self.assertTrue(action.enabled)
                self.assertEqual(action.classification, "internal_only")
                self.assertEqual(action.warning_code, warning_code)
                self.assertEqual(action.warning_message is not None, warning_code is not None)
                self.assertIsNone(action.disabled_reason_code)
                self.assertFalse(action.retryable)
                default_job, default_file = self.service.get_file_for_download(job.id, user=self.operator, file_id=None)
                explicit_job, explicit_file = self.service.get_file_for_download(job.id, user=self.operator, file_id=file.id)
                default = self.service.build_download_policy(default_job, default_file)
                self.assertEqual(default, self.service.build_download_policy(explicit_job, explicit_file))
                self.assertEqual(default.warning_code, action.warning_code)
                self.assertEqual(self.runtime.document_job_repository.get_document_job(job.id), job)

    def test_publish_eligibility_requires_canonical_quality_review_and_current_admin(self):
        for quality, review, role, eligible, codes in (
            ("passed", "approved", "admin", True, []),
            ("warning", "approved", "admin", True, []),
            ("passed", "approved", "operator", False, ["admin_required"]),
            ("pending", "approved", "admin", False, ["quality_status_pending"]),
            ("blocked", "unreviewed", "admin", False, ["quality_status_blocked", "review_status_unreviewed"]),
            ("passed", "needs_fix", "admin", False, ["review_status_needs_fix"]),
            ("passed", "blocked", "admin", False, ["review_status_blocked"]),
            ("passed", "unreviewed", "admin", False, ["review_status_unreviewed"]),
        ):
            with self.subTest(quality=quality, review=review, role=role):
                job, _ = self._result(quality_status=quality, review_status=review, translation_qa_status="approved")
                user = self.admin if role == "admin" else self.operator
                action = self.service.build_available_actions(job, user=user)["publish"]
                self.assertEqual(action.eligible, eligible)
                self.assertFalse(action.enabled)
                self.assertFalse(action.retryable)
                self.assertEqual([reason.code for reason in action.disabled_reasons],
                                 [*codes, "preview_unavailable", "publication_unavailable"])
                self.assertEqual(action.disabled_reason_code, action.disabled_reasons[0].code)
                self.assertEqual(action.disabled_reason, action.disabled_reasons[0].message)

    def test_published_is_not_republished_or_classified_as_final(self):
        job, _ = self._result(quality_status="passed", review_status="approved", delivery_status="published")
        actions = self.service.build_available_actions(job, user=self.admin)
        self.assertFalse(actions["publish"].eligible)
        self.assertEqual(actions["publish"].disabled_reason_code, "already_published")
        self.assertEqual(actions["download"].classification, "internal_only")
        self.assertFalse(actions["delete"].enabled)

    def test_default_download_actions_share_existing_issuance_rejections(self):
        cases = (
            ({"deleted_at": utc_now()}, {}, "job_deleted", 409),
            ({"status": "running", "stage": "uploading"}, {}, "job_not_completed", 409),
            ({"result_file_id": None}, {}, "result_file_missing", 409),
            ({"result_file_id": "missing_metadata"}, {}, "result_file_missing", 404),
            ({}, {"tenant_id": "other"}, "result_file_mismatch", 409),
            ({}, {"company_id": "other"}, "result_file_mismatch", 409),
            ({}, {"job_id": "other"}, "result_file_mismatch", 409),
            ({}, {"file_type": "document_ir"}, "result_file_mismatch", 409),
            ({}, {"status": "pending_upload"}, "result_file_not_uploaded", 409),
            ({}, {"status": "deleted"}, "result_file_not_uploaded", 409),
            ({}, {"expires_at": utc_now() - timedelta(minutes=1)}, "file_expired", 409),
        )
        for job_patch, file_patch, code, http_status in cases:
            with self.subTest(job_patch=job_patch, file_patch=file_patch):
                job, _ = self._result(file_patch=file_patch, **job_patch)
                actions = self.service.build_available_actions(job, user=self.admin)
                download = actions["download"]
                self.assertFalse(download.enabled)
                self.assertEqual(download.disabled_reason_code, code)
                self.assertIsNone(download.classification)
                self.assertIsNone(download.warning_code)
                self.assertFalse(actions["publish"].eligible)
                self.assertEqual(actions["publish"].disabled_reason_code, code)
                with self.assertRaises(ApiError) as caught:
                    self.service.get_file_for_download(job.id, user=self.operator, file_id=None)
                self.assertEqual((caught.exception.status_code, caught.exception.reason_code), (http_status, code))

    def test_ordinary_artifacts_remain_downloadable_without_main_document_classification(self):
        job, file = self._result(status="running", stage="uploading")
        source = file.model_copy(update={"id": job.source_file_id, "file_type": "source_pdf"})
        self.runtime.document_file_repository.create_document_file(source)
        _, downloaded = self.service.get_file_for_download(job.id, user=self.operator, file_id=source.id)
        policy = self.service.build_download_policy(job, downloaded)
        self.assertIsNone(policy.classification)
        self.assertIsNone(policy.warning_code)
        self.assertIsNone(policy.warning_message)
        # 历史普通附件按原有同代规则保留，不因 generated_word 类型伪装成权威主件。
        legacy = file.model_copy(update={"id": "legacy_word"})
        self.runtime.document_file_repository.create_document_file(legacy)
        _, downloaded = self.service.get_file_for_download(job.id, user=self.operator, file_id=legacy.id)
        self.assertIsNone(self.service.build_download_policy(job, downloaded).classification)

    def test_availability_reads_only_metadata_without_object_io(self):
        job, _ = self._result(quality_status="passed", review_status="approved")
        before = self.runtime.document_job_repository.get_document_job(job.id)
        with patch.object(self.runtime.file_upload_service, "read_file_content", side_effect=AssertionError("不得读取正文")), \
                patch.object(self.runtime.file_upload_service, "_s3_client", side_effect=AssertionError("不得探测 S3 对象")):
            actions = self.service.build_available_actions(job, user=self.admin)
        self.assertTrue(actions["download"].enabled)
        self.assertTrue(actions["publish"].eligible)
        self.assertEqual(self.runtime.document_job_repository.get_document_job(job.id), before)
