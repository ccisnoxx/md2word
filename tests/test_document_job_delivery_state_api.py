"""验证真实服务、API 与 file/SQLite 的复核投影及并发边界。"""

import io
import json
import sqlite3
import tempfile
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from docx import Document
from fastapi.testclient import TestClient

from app.domains.document_jobs.router import _build_download_token
from app.domains.resources.models import utc_now
from app.main import create_app
from app.services.auth.models import AuthenticatedUser
from app.domains.translation.document_ir_translator import DocumentIRTranslationService
from tests import test_fastapi_jobs_backend as fixtures


STATE_DEFAULTS = {
    "quality_status": "pending",
    "review_status": "unreviewed",
    "delivery_status": "internal_draft",
    "quality_summary": {},
}


class DocumentJobDeliveryStateApiTests(TestCase):
    @contextmanager
    def _application(self, backend, *, eager=False, raise_server_exceptions=True):
        with tempfile.TemporaryDirectory() as directory:
            users = json.loads(fixtures.build_multi_operator_auth_users_json())
            for username, scope in (("other_tenant", {"tenant_id": "tenant_other"}),
                                    ("other_company", {"company_id": "company_other"})):
                users.append({**users[1], **scope, "id": username, "username": username})
            runtime = fixtures.build_test_runtime(
                Path(directory), jobs_repository_backend=backend,
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret", auth_internal_users_json=json.dumps(users),
                document_jobs_worker_backend="eager" if eager else "disabled",
            )
            translator = DocumentIRTranslationService(fixtures.FakeDocumentJobTranslationProvider())
            runtime.document_job_execution_service.document_ir_translation_service = translator
            runtime.document_job_execution_service.fake_mineru_client.result_zip_bytes = fixtures.make_english_mineru_zip_bytes()
            with TestClient(create_app(runtime), raise_server_exceptions=raise_server_exceptions) as client:
                yield runtime, client, fixtures.build_auth_header(client)

    def _create(self, client, headers, *, translation=True, extra=None):
        source = fixtures.FastAPIJobsBackendTests._upload_source_pdf(self, client, headers)
        response = client.post(
            "/api/v1/document-jobs", headers=headers,
            json={"source_file_id": source["id"],
                  "translation_mode": "en2zh" if translation else "direct", **(extra or {})},
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def _qa(self, client, headers, job_id, qa_status="approved", *, note="内部复核备注"):
        return client.patch(
            f"/api/v1/document-jobs/{job_id}/translation-qa", headers={**headers, "X-Trace-Id": "trace-review"},
            json={"status": qa_status, "issue_type": "terminology", "note": note},
        )

    def _assert_defaults(self, response):
        self.assertEqual({field: response[field] for field in STATE_DEFAULTS}, STATE_DEFAULTS)
        self.assertEqual(response["translation_qa_status"], "unreviewed")
        for field in ("issue_type", "note", "reviewed_by", "reviewed_at"):
            self.assertIsNone(response[f"translation_qa_{field}"])

    def _raw_payload(self, runtime, job_id, *, replace=None):
        if runtime.settings.jobs_repository_backend == "file":
            path = runtime.document_job_repository.backend.document_jobs_dir / job_id / "job.json"
            if replace is not None:
                path.write_text(json.dumps(replace, ensure_ascii=False), encoding="utf-8")
            return path.read_text(encoding="utf-8")
        with sqlite3.connect(runtime.settings.jobs_metadata_database_file) as connection:
            if replace is not None:
                connection.execute("UPDATE document_jobs SET payload = ? WHERE job_id = ?",
                                   (json.dumps(replace, ensure_ascii=False), job_id))
            return connection.execute("SELECT payload FROM document_jobs WHERE job_id = ?", (job_id,)).fetchone()[0]

    def test_legacy_raw_qa_is_canonical_in_detail_qa_queue_and_incidents_without_writes(self):
        for backend in ("file", "database"):
            with self.subTest(backend=backend), self._application(backend) as (runtime, client, headers):
                created = self._create(client, headers, extra={
                    "quality_status": "passed", "review_status": "approved", "delivery_status": "published",
                    "quality_summary": {"ignored": True},
                })
                self._assert_defaults(created["job"])
                job_id = created["job_id"]
                runtime.document_job_repository.update_document_job(
                    job_id, status="failed", stage="failed", failed_stage="rendering", error_code="render_failed",
                    translation_qa_status="approved", translation_qa_note="object missing 历史备注",
                    translation_qa_issue_type="artifact_missing", translation_qa_reviewed_by="legacy-reviewer",
                    translation_qa_reviewed_at=utc_now(),
                )
                payload = json.loads(self._raw_payload(runtime, job_id))
                for field in STATE_DEFAULTS:
                    payload.pop(field)
                before = self._raw_payload(runtime, job_id, replace=payload)
                detail = client.get(f"/api/v1/document-jobs/{job_id}", headers=headers).json()
                self._assert_defaults(detail)
                qa = client.get(f"/api/v1/document-jobs/{job_id}/translation-qa", headers=headers).json()["qa"]
                self.assertEqual(qa, {"status": "unreviewed", "issue_type": None, "note": None,
                                      "reviewed_by": None, "reviewed_at": None})
                queue = client.get("/api/v1/document-jobs", headers=headers,
                                   params={"translation_qa_status": "unreviewed"}).json()
                self.assertEqual([item["id"] for item in queue["items"]], [job_id])
                self._assert_defaults(queue["items"][0])
                self.assertEqual(queue["translation_qa_summary"],
                                 {"unreviewed": 1, "approved": 0, "needs_fix": 0, "blocked": 0})
                self.assertEqual(client.get("/api/v1/document-jobs", headers=headers,
                                            params={"translation_qa_status": "approved"}).json()["items"], [])
                diagnostic = client.get(f"/api/v1/document-job-incidents/{job_id}/diagnostics", headers=headers)
                self.assertEqual(diagnostic.status_code, 200, diagnostic.text)
                self._assert_defaults(diagnostic.json()["item"]["job"])
                self.assertFalse(diagnostic.json()["item"]["blocked"])
                self.assertEqual(diagnostic.json()["item"]["failure_type"], "conversion_failed")
                incident = client.get("/api/v1/document-job-incidents", headers=headers).json()["items"][0]
                self._assert_defaults(incident["job"])
                self.assertEqual(self._raw_payload(runtime, job_id), before)

    def test_legacy_blocked_metadata_does_not_create_current_incidents(self):
        for backend in ("file", "database"):
            with self.subTest(backend=backend), self._application(backend) as (runtime, client, headers):
                job_id = self._create(client, headers)["job_id"]
                runtime.document_job_repository.update_document_job(
                    job_id, translation_qa_status="blocked", translation_qa_issue_type="artifact_missing",
                    translation_qa_note="missing object 历史 QA 不能制造当前异常",
                )
                response = client.get("/api/v1/document-job-incidents", headers=headers)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["items"], [])
                detail = client.get(f"/api/v1/document-jobs/{job_id}", headers=headers).json()
                self._assert_defaults(detail)

    def test_operator_approval_updates_owner_and_safe_audit_while_remaining_draft(self):
        for backend in ("file", "database"):
            with self.subTest(backend=backend), self._application(backend, eager=True) as (runtime, client, headers):
                created = self._create(client, headers)
                self.assertEqual(created["job"]["status"], "succeeded", created)
                job_id = created["job_id"]
                original = runtime.document_job_repository.get_document_job(job_id)
                file = runtime.document_file_repository.get_document_file(original.result_file_id)
                Document(io.BytesIO(runtime.file_upload_service.read_file_content(file)))
                response = self._qa(client, headers, job_id)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["qa"]["status"], "approved")
                self.assertEqual(response.json()["job"]["review_status"], "approved")
                self.assertEqual(response.json()["job"]["delivery_status"], "internal_draft")
                self.assertEqual(response.json()["job"]["quality_status"], "pending")
                self.assertEqual(response.json()["job"]["translation_qa_reviewed_by"], "user_operator")
                queue = client.get("/api/v1/document-jobs", headers=headers,
                                   params={"translation_qa_status": "approved"}).json()
                self.assertEqual([item["id"] for item in queue["items"]], [job_id])
                self.assertEqual(queue["translation_qa_summary"]["approved"], 1)
                events = runtime.document_job_event_repository.list_document_job_events(job_id)
                event = [event for event in events if event.event_type == "translation_qa_updated"][-1]
                self.assertEqual(event.trace_id, "trace-review")
                self.assertEqual(event.payload["observed_review_status"], "unreviewed")
                self.assertNotIn("previous_review_status", event.payload)
                self.assertEqual(event.payload["review_status"], "approved")
                self.assertEqual(event.payload["generation"], original.retry_count)
                self.assertEqual(event.payload["result_file_id"], file.id)
                self.assertEqual(event.payload["checksum_sha256"], file.checksum_sha256)
                self.assertEqual(event.payload["note_length"], len("内部复核备注"))
                serialized = json.dumps(event.model_dump(mode="json"), ensure_ascii=False)
                for secret in ("内部复核备注", file.object_key, "prompt"):
                    self.assertNotIn(secret, serialized)
                reset = self._qa(client, headers, job_id, "unreviewed")
                self.assertEqual(reset.status_code, 200, reset.text)
                self._assert_defaults(reset.json()["job"])

    def test_qa_keeps_owner_tenant_company_admin_and_direct_boundaries(self):
        with self._application("file", eager=True) as (runtime, client, headers):
            job_id = self._create(client, headers)["job_id"]
            for username, password in (("operator2", "operator2-pass"),
                                       ("other_tenant", "operator-pass"), ("other_company", "operator-pass")):
                other = fixtures.build_auth_header(client, username=username, password=password)
                self.assertEqual(self._qa(client, other, job_id, "needs_fix").status_code, 403)
                self.assertEqual(client.get(f"/api/v1/document-jobs/{job_id}/translation-qa", headers=other).status_code, 403)
            admin = fixtures.build_auth_header(client, username="admin", password="admin-pass")
            self.assertEqual(self._qa(client, admin, job_id).status_code, 200)
            direct_id = self._create(client, headers, translation=False)["job_id"]
            runtime.document_job_repository.update_document_job(direct_id, translation_qa_status="approved")
            direct = client.get(f"/api/v1/document-jobs/{direct_id}/translation-qa", headers=headers).json()
            self.assertFalse(direct["available"])
            self.assertEqual(direct["qa"]["status"], "unreviewed")
            self.assertEqual(self._qa(client, headers, direct_id).status_code, 409)
            detail = client.get(f"/api/v1/document-jobs/{direct_id}", headers=headers).json()
            self._assert_defaults(detail)

    def test_approval_rejects_blocked_incomplete_expired_missing_and_invalid_current_files(self):
        for backend in ("file", "database"):
            with self.subTest(backend=backend), self._application(backend, eager=True) as (runtime, client, headers):
                job_id = self._create(client, headers)["job_id"]
                repository = runtime.document_job_repository
                job = repository.get_document_job(job_id)
                file = runtime.document_file_repository.get_document_file(job.result_file_id)
                path = runtime.file_upload_service.resolve_local_object_path(file.object_key)
                content = path.read_bytes()
                repository.update_document_job(job_id, quality_status="blocked")
                self.assertEqual(self._qa(client, headers, job_id).status_code, 409)
                repository.update_document_job(job_id, quality_status="pending", status="running", stage="uploading")
                self.assertEqual(self._qa(client, headers, job_id).status_code, 409)
                repository.update_document_job(job_id, status="succeeded", stage="completed")
                for file_patch in ({"expires_at": utc_now() - timedelta(seconds=1)},
                                   {"status": "pending_upload"}, {"tenant_id": "tenant_other"},
                                   {"job_id": "another-job"}, {"file_type": "document_ir"}):
                    with self.subTest(file_patch=file_patch):
                        runtime.document_file_repository.update_document_file(file.id, **file_patch)
                        self.assertEqual(self._qa(client, headers, job_id).status_code, 409)
                        runtime.document_file_repository.update_document_file(file.id, **file.model_dump(mode="python"))
                path.unlink()
                self.assertEqual(self._qa(client, headers, job_id).status_code, 409)
                path.write_bytes(content[:-1] + bytes([content[-1] ^ 1]))
                self.assertEqual(self._qa(client, headers, job_id).status_code, 409)
                path.write_bytes(content)
                runtime.document_file_repository.update_document_file(file.id, status="deleted")
                self.assertEqual(self._qa(client, headers, job_id).status_code, 409)
                repository.update_document_job(job_id, result_file_id="file_metadata_missing", prepared_result=None)
                missing = self._qa(client, headers, job_id)
                self.assertEqual(missing.status_code, 409, missing.text)
                self.assertEqual(client.get(f"/api/v1/document-jobs/{job_id}/download-url", headers=headers).status_code, 404)
                repository.update_document_job(job_id, result_file_id=None, prepared_result=None)
                self.assertEqual(self._qa(client, headers, job_id).status_code, 409)
                self.assertEqual(repository.get_document_job(job_id).review_status, "unreviewed")
                self.assertFalse(any(event.event_type == "translation_qa_updated"
                                     for event in runtime.document_job_event_repository.list_document_job_events(job_id)))

    def test_review_cas_rejects_retry_replacement_blocker_and_none_result_races(self):
        for backend in ("file", "database"):
            for race in ("retry", "replacement", "blocked", "none_result"):
                with self.subTest(backend=backend, race=race), self._application(backend, eager=True) as (runtime, client, headers):
                    job_id = self._create(client, headers)["job_id"]
                    repository = runtime.document_job_repository
                    job = repository.get_document_job(job_id)
                    file = runtime.document_file_repository.get_document_file(job.result_file_id)
                    runtime.document_job_service.task_queue = None
                    if race == "none_result":
                        repository.update_document_job(job_id, status="pending", stage="uploaded",
                                                       result_file_id=None, prepared_result=None)
                    original = repository.update_document_job_review_if_current

                    def compete(current_id, **kwargs):
                        # 在服务读完、仓储取得短锁前插入真实提交，验证锁内条件而非 mock 返回值。
                        if race == "retry":
                            repository.update_document_job(current_id, status="failed", stage="failed", failed_stage="uploading")
                            next_job = repository.retry_document_job(
                                current_id, expected_retry_count=job.retry_count, max_retries=2,
                                retry_count=job.retry_count + 1, status="running", stage="uploading",
                            )
                            self.assertEqual(next_job.result_file_id, file.id)
                        elif race == "replacement":
                            replacement = runtime.file_upload_service.register_generated_content(
                                tenant_id=job.tenant_id, company_id=job.company_id, job_id=job.id,
                                created_by=job.created_by, file_type="generated_word", filename="replacement.docx",
                                mime_type=file.mime_type, content=runtime.file_upload_service.read_file_content(file),
                                metadata=file.metadata,
                            )
                            repository.update_document_job(current_id, prepared_result=None, result_file_id=replacement.id)
                        elif race == "blocked":
                            repository.update_document_job(current_id, quality_status="blocked")
                        else:
                            self.assertIsNone(kwargs["expected_result_file_id"])
                            repository.update_document_job(current_id, result_file_id=file.id)
                        return original(current_id, **kwargs)

                    with patch.object(repository, "update_document_job_review_if_current", side_effect=compete):
                        response = self._qa(client, headers, job_id, "needs_fix" if race == "none_result" else "approved")
                    self.assertEqual(response.status_code, 409, response.text)
                    current = repository.get_document_job(job_id)
                    self.assertEqual(current.review_status, "unreviewed")
                    self.assertEqual(current.delivery_status, "internal_draft")
                    self.assertEqual(current.retry_count, job.retry_count + (race == "retry"))
                    if race == "blocked":
                        self.assertEqual(current.quality_status, "blocked")
                    self.assertFalse(any(event.event_type == "translation_qa_updated"
                                         for event in runtime.document_job_event_repository.list_document_job_events(job_id)))

    def test_clone_and_retry_return_defaults_even_with_reused_result_and_old_metadata(self):
        for backend in ("file", "database"):
            with self.subTest(backend=backend), self._application(backend, eager=True) as (runtime, client, headers):
                job_id = self._create(client, headers)["job_id"]
                runtime.document_job_repository.update_document_job(job_id, quality_status="warning", quality_summary={"count": 1})
                self.assertEqual(self._qa(client, headers, job_id).status_code, 200)
                source = runtime.document_job_repository.get_document_job(job_id)
                runtime.document_job_service.task_queue = None
                clone = client.post(f"/api/v1/document-jobs/{job_id}/clone", headers=headers,
                                    json={"config_strategy": "keep_source_snapshot", "review_status": "approved",
                                          "delivery_status": "published"})
                self.assertEqual(clone.status_code, 201, clone.text)
                self._assert_defaults(clone.json()["job"])
                self.assertEqual(runtime.document_job_repository.get_document_job(job_id), source)
                self.assertEqual(self._qa(client, headers, job_id, "needs_fix").status_code, 200)
                runtime.document_job_repository.update_document_job(
                    job_id, status="failed", stage="failed", failed_stage="uploading", error_code="oss_failed",
                )
                retried = client.post(f"/api/v1/document-jobs/{job_id}/retry", headers=headers,
                                      json={"quality_status": "passed", "review_status": "approved"})
                self.assertEqual(retried.status_code, 200, retried.text)
                self._assert_defaults(retried.json()["job"])
                self.assertEqual(retried.json()["job"]["result_file_id"], source.result_file_id)
                self.assertEqual(retried.json()["job"]["retry_count"], source.retry_count + 1)
                self.assertIsNone(runtime.document_job_repository.get_document_job(job_id).prepared_result)

    def test_internal_download_keeps_blocked_unreviewed_results_and_token_candidate_guards(self):
        for backend in ("file", "database"):
            with self.subTest(backend=backend), self._application(backend, eager=True) as (runtime, client, headers):
                job_id = self._create(client, headers)["job_id"]
                repository = runtime.document_job_repository
                job = repository.update_document_job(job_id, quality_status="blocked")
                file = runtime.document_file_repository.get_document_file(job.result_file_id)
                content = runtime.file_upload_service.read_file_content(file)
                self.assertEqual(job.review_status, "unreviewed")
                detail = client.get(f"/api/v1/document-jobs/{job_id}", headers=headers).json()
                self.assertTrue(detail["available_actions"]["download"]["enabled"])
                signed = client.get(f"/api/v1/document-jobs/{job_id}/download-url", headers=headers)
                self.assertEqual(signed.status_code, 200, signed.text)
                downloaded = client.get(signed.json()["download_url"])
                self.assertEqual(downloaded.status_code, 200)
                self.assertEqual(downloaded.content, content)
                Document(io.BytesIO(downloaded.content))
                candidate = runtime.file_upload_service.register_result_candidate(
                    tenant_id=job.tenant_id, company_id=job.company_id, job_id=job.id, created_by=job.created_by,
                    filename="candidate.docx", content=content, metadata=file.metadata,
                )
                files = client.get(f"/api/v1/document-jobs/{job_id}/files", headers=headers).json()["files"]
                self.assertNotIn(candidate.id, [item["id"] for item in files])
                self.assertEqual(client.get(f"/api/v1/document-jobs/{job_id}/download-url", headers=headers,
                                            params={"file_id": candidate.id}).status_code, 409)
                candidate_token = _build_download_token(runtime, job_id=job_id, file_id=candidate.id,
                                                        expires_at=utc_now() + timedelta(minutes=1))
                self.assertEqual(client.get(f"/api/v1/document-jobs/{job_id}/download",
                                            params={"token": candidate_token}).status_code, 409)
                expired = _build_download_token(runtime, job_id=job_id, file_id=file.id,
                                                expires_at=utc_now() - timedelta(seconds=5))
                self.assertEqual(client.get(f"/api/v1/document-jobs/{job_id}/download",
                                            params={"token": expired}).status_code, 403)
                self.assertEqual(client.get(signed.json()["download_url"] + "tampered").status_code, 403)
                other = fixtures.build_auth_header(client, username="other_tenant", password="operator-pass")
                self.assertEqual(client.get(f"/api/v1/document-jobs/{job_id}/download-url", headers=other).status_code, 403)
                repository.update_document_job(job_id, status="running", stage="uploading")
                self.assertEqual(client.get(signed.json()["download_url"]).status_code, 409)

    def test_published_delete_rejects_stale_preview_without_side_effects_and_keeps_archive(self):
        for backend in ("file", "database"):
            with self.subTest(backend=backend), self._application(
                backend, eager=True, raise_server_exceptions=False,
            ) as (runtime, client, headers):
                job_id = self._create(client, headers)["job_id"]
                admin = fixtures.build_auth_header(client, username="admin", password="admin-pass")
                self.assertEqual(self._qa(client, headers, job_id).status_code, 200)
                preview = client.post(f"/api/v1/document-jobs/{job_id}/delete-preview", headers=admin)
                self.assertEqual(preview.status_code, 200, preview.text)
                self.assertGreater(preview.json()["totals"]["delete"], 0)
                # 仅构造合法的未来已发布记录，不引入发布 API；删除请求继续持有旧草稿 hash。
                published = runtime.document_job_repository.update_document_job(
                    job_id, quality_status="passed", delivery_status="published",
                )
                files = runtime.document_file_repository.list_document_files()
                contents = {file.id: runtime.file_upload_service.read_file_content(file) for file in files}
                events = runtime.document_job_event_repository.list_document_job_events(job_id)
                audits = runtime.audit_event_repository.list_audit_events()

                with patch.object(
                    runtime.file_upload_service, "execute_document_job_physical_delete",
                    wraps=runtime.file_upload_service.execute_document_job_physical_delete,
                ) as physical_delete:
                    detail = client.get(f"/api/v1/document-jobs/{job_id}", headers=admin)
                    refused_preview = client.post(f"/api/v1/document-jobs/{job_id}/delete-preview", headers=admin)
                    refused_delete = client.post(
                        f"/api/v1/document-jobs/{job_id}/delete", headers=admin,
                        json={"preview_hash": preview.json()["preview_hash"]},
                    )

                self.assertEqual(refused_delete.status_code, 409, refused_delete.text)
                self.assertEqual(refused_preview.status_code, 409, refused_preview.text)
                self.assertEqual(detail.status_code, 200, detail.text)
                delete_action = detail.json()["available_actions"]["delete"]
                self.assertFalse(delete_action["enabled"])
                self.assertIn("已发布", delete_action["disabled_reason"])
                self.assertEqual(refused_preview.json()["detail"], delete_action["disabled_reason"])
                self.assertEqual(refused_delete.json()["detail"], delete_action["disabled_reason"])
                physical_delete.assert_not_called()
                self.assertEqual(runtime.document_job_repository.get_document_job(job_id), published)
                self.assertEqual(runtime.document_file_repository.list_document_files(), files)
                self.assertEqual(
                    {file.id: runtime.file_upload_service.read_file_content(file) for file in files}, contents,
                )
                self.assertEqual(runtime.document_job_event_repository.list_document_job_events(job_id), events)
                self.assertEqual(runtime.audit_event_repository.list_audit_events(), audits)
                self.assertTrue(detail.json()["available_actions"]["archive"]["enabled"])
                archived = client.delete(f"/api/v1/document-jobs/{job_id}", headers=admin)
                self.assertEqual(archived.status_code, 200, archived.text)
                self.assertEqual(archived.json()["job"]["delivery_status"], "published")
                self.assertIsNotNone(archived.json()["job"]["archived_at"])
                self.assertEqual(runtime.document_file_repository.list_document_files(), files)

    def test_qa_event_labels_lock_free_observation_when_another_review_commits_first(self):
        for backend in ("file", "database"):
            with self.subTest(backend=backend), self._application(backend, eager=True) as (runtime, client, headers):
                job_id = self._create(client, headers)["job_id"]
                repository = runtime.document_job_repository
                observed = repository.get_document_job(job_id)
                user = AuthenticatedUser(id="user_operator", username="operator", role="operator",
                                         tenant_id="tenant_default", company_id="company_default")
                write_review = repository.update_document_job_review_if_current
                interleaved = False

                def commit_after_other_review(current_id, **kwargs):
                    nonlocal interleaved
                    if not interleaved:
                        interleaved = True
                        # A 已读未复核；B 先经真实 service/CAS 提交，随后 A 才进入自己的 CAS。
                        runtime.document_job_service.update_translation_qa(
                            current_id, user=user, qa_status="needs_fix", issue_type="terminology",
                            note="B 的复核备注", trace_id="trace-review-b",
                        )
                        before_a = repository.get_document_job(current_id)
                        self.assertEqual(before_a.review_status, "needs_fix")
                        self.assertEqual((before_a.retry_count, before_a.result_file_id),
                                         (observed.retry_count, observed.result_file_id))
                    return write_review(current_id, **kwargs)

                with patch.object(repository, "update_document_job_review_if_current", side_effect=commit_after_other_review):
                    response = self._qa(client, headers, job_id, "blocked")
                self.assertEqual(response.status_code, 200, response.text)
                current = repository.get_document_job(job_id)
                self.assertEqual(current.review_status, "blocked")
                self.assertEqual((current.retry_count, current.result_file_id),
                                 (observed.retry_count, observed.result_file_id))
                events = [event for event in runtime.document_job_event_repository.list_document_job_events(job_id)
                          if event.event_type == "translation_qa_updated"]
                self.assertEqual([event.payload["review_status"] for event in events], ["needs_fix", "blocked"])
                event_a = events[-1]
                self.assertEqual(event_a.trace_id, "trace-review")
                self.assertEqual(event_a.payload.get("observed_review_status"), "unreviewed")
                self.assertNotIn("previous_review_status", event_a.payload)

    def test_qa_event_failure_propagates_after_review_write(self):
        with self._application("file", eager=True) as (runtime, client, headers):
            job_id = self._create(client, headers)["job_id"]
            user = AuthenticatedUser(id="user_operator", username="operator", role="operator",
                                     tenant_id="tenant_default", company_id="company_default")
            with patch.object(runtime.document_job_event_repository, "append_document_job_event",
                              side_effect=RuntimeError("事件存储不可用")):
                with self.assertRaisesRegex(RuntimeError, "事件存储不可用"):
                    runtime.document_job_service.update_translation_qa(
                        job_id, user=user, qa_status="approved", issue_type=None, note=None, trace_id="trace-event-failure",
                    )
            self.assertEqual(runtime.document_job_repository.get_document_job(job_id).review_status, "approved")

    def test_state_schema_is_read_only_additive_and_json_object(self):
        with self._application("file") as (_runtime, client, _headers):
            schemas = client.get("/openapi.json").json()["components"]["schemas"]
            properties = schemas["DocumentJobResponse"]["properties"]
            for field in STATE_DEFAULTS:
                self.assertTrue(properties[field]["readOnly"])
            self.assertEqual(properties["quality_summary"]["type"], "object")
            for request in ("DocumentJobCreateRequest", "DocumentJobRetryRequest", "DocumentJobCloneRequest"):
                self.assertTrue(set(STATE_DEFAULTS).isdisjoint(schemas[request]["properties"]))
