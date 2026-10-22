"""通过真实 TestClient 验证下载与任务投影、错误兼容及安全审计合同。"""

import json
from datetime import datetime, timedelta
from unittest import TestCase
from unittest.mock import patch

from app.domains.document_jobs.router import _build_download_token
from app.domains.resources.models import utc_now
from tests import test_document_job_delivery_state_api as state_fixtures
from tests import test_fastapi_jobs_backend as fixtures


class DocumentJobDownloadAvailabilityApiTests(TestCase):
    _application = state_fixtures.DocumentJobDeliveryStateApiTests._application
    _create = state_fixtures.DocumentJobDeliveryStateApiTests._create
    _qa = state_fixtures.DocumentJobDeliveryStateApiTests._qa

    def _detail(self, client, headers, job_id):
        response = client.get(f"/api/v1/document-jobs/{job_id}", headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _signed(self, client, headers, job_id, *, file_id=None):
        response = client.get(
            f"/api/v1/document-jobs/{job_id}/download-url", headers=headers,
            params={} if file_id is None else {"file_id": file_id},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _assert_download_policy(self, payload, warning_code):
        self.assertEqual(payload["classification"], "internal_only")
        self.assertEqual(payload["warning_code"], warning_code)
        self.assertEqual(payload["warning_message"] is not None, warning_code is not None)

    def test_core_scenarios_roles_and_latest_default_explicit_signing_policy(self):
        with self._application("file", eager=True) as (runtime, client, headers):
            created = self._create(client, headers)
            job_id = created["job_id"]
            admin = fixtures.build_auth_header(client, username="admin", password="admin-pass")
            self.assertEqual(created["job"]["available_actions"], self._detail(client, headers, job_id)["available_actions"])
            for quality, review, warning_code in (
                ("blocked", "unreviewed", "quality_blocked_not_deliverable"),
                ("passed", "unreviewed", "document_unreviewed_not_deliverable"),
                ("warning", "needs_fix", "review_needs_fix_not_deliverable"),
            ):
                with self.subTest(quality=quality, review=review):
                    job = runtime.document_job_repository.update_document_job(
                        job_id, quality_status=quality, review_status=review,
                    )
                    actions = self._detail(client, headers, job_id)["available_actions"]
                    self.assertTrue(actions["download"]["enabled"])
                    self._assert_download_policy(actions["download"], warning_code)
                    self.assertFalse(actions["publish"]["eligible"])
                    self.assertFalse(actions["publish"]["enabled"])
                    default = self._signed(client, headers, job_id)
                    explicit = self._signed(client, headers, job_id, file_id=job.result_file_id)
                    for field in ("classification", "warning_code", "warning_message"):
                        self.assertEqual(default[field], explicit[field])
                        self.assertEqual(default[field], actions["download"][field])
                    self._assert_download_policy(default, warning_code)
                    self.assertEqual(client.get(default["download_url"]).status_code, 200)

            runtime.document_job_repository.update_document_job(job_id, quality_status="passed")
            approved = self._qa(client, headers, job_id)
            self.assertEqual(approved.status_code, 200, approved.text)
            for quality in ("passed", "warning", "pending"):
                with self.subTest(approved_quality=quality):
                    runtime.document_job_repository.update_document_job(job_id, quality_status=quality)
                    for actor, eligible in ((admin, quality != "pending"), (headers, False)):
                        publish = self._detail(client, actor, job_id)["available_actions"]["publish"]
                        self.assertEqual(publish["eligible"], eligible)
                        self.assertFalse(publish["enabled"])
                        self.assertEqual([reason["code"] for reason in publish["disabled_reasons"]][-2:],
                                         ["preview_unavailable", "publication_unavailable"])
                        self.assertTrue(publish["disabled_reason"])
                    operator = self._detail(client, headers, job_id)["available_actions"]["publish"]
                    self.assertEqual(operator["disabled_reason_code"], "admin_required")
                    warning = "quality_pending_not_deliverable" if quality == "pending" else None
                    self._assert_download_policy(self._signed(client, admin, job_id), warning)

    def test_list_detail_and_incidents_use_the_same_metadata_only_owner(self):
        with self._application("file", eager=True) as (runtime, client, headers):
            job_id = self._create(client, headers)["job_id"]
            job = runtime.document_job_repository.update_document_job(
                job_id, quality_status="blocked", review_status="blocked",
            )
            before = runtime.document_job_repository.get_document_job(job_id)
            events = runtime.document_job_event_repository.list_document_job_events(job_id)
            audit = runtime.audit_event_repository.list_audit_events()
            with patch.object(runtime.file_upload_service, "read_file_content", side_effect=AssertionError("GET 不读取正文")), \
                    patch.object(runtime.file_upload_service, "_s3_client", side_effect=AssertionError("GET 不探测 S3")):
                detail = self._detail(client, headers, job_id)
                queue = client.get("/api/v1/document-jobs", headers=headers).json()["items"][0]
                diagnostic_response = client.get(f"/api/v1/document-job-incidents/{job_id}/diagnostics", headers=headers)
                self.assertEqual(diagnostic_response.status_code, 200, diagnostic_response.text)
                diagnostic = diagnostic_response.json()["item"]["job"]
                incident = client.get("/api/v1/document-job-incidents", headers=headers).json()["items"][0]["job"]
            for projected in (queue, diagnostic, incident):
                self.assertEqual(projected["available_actions"], detail["available_actions"])
            self.assertEqual(runtime.document_job_repository.get_document_job(job.id), before)
            self.assertEqual(runtime.document_job_event_repository.list_document_job_events(job_id), events)
            self.assertEqual(runtime.audit_event_repository.list_audit_events(), audit)

    def test_reason_code_is_additive_and_unrelated_api_errors_keep_the_exact_legacy_shape(self):
        with self._application("file") as (runtime, client, headers):
            job_id = self._create(client, headers)["job_id"]
            response = client.get(f"/api/v1/document-jobs/{job_id}/download-url", headers=headers)
            self.assertEqual(response.status_code, 409)
            payload = response.json()
            self.assertEqual(payload["error_code"], "conflict")
            self.assertEqual(payload["error"]["code"], "conflict")
            self.assertEqual(payload["detail"], "文档任务尚未成功完成，生成 Word 不可下载。")
            self.assertEqual(payload["error"]["reason_code"], "job_not_completed")
            self.assertNotIn("reason_code", payload)
            actions = self._detail(client, headers, job_id)["available_actions"]
            self.assertEqual(actions["download"]["disabled_reason_code"], payload["error"]["reason_code"])

            missing = client.get("/api/v1/document-jobs/unknown", headers={**headers, "X-Trace-Id": "legacy-error"})
            self.assertEqual(missing.status_code, 404)
            message = "文档任务不存在: unknown"
            self.assertEqual(missing.json(), {
                "detail": message, "error_code": "not_found", "request_id": "legacy-error", "trace_id": "legacy-error",
                "error": {"code": "not_found", "message": message, "status_code": 404,
                          "request_id": "legacy-error", "trace_id": "legacy-error"},
            })
            runtime.document_job_repository.update_document_job(
                job_id, status="succeeded", stage="completed", result_file_id="missing-result",
            )
            missing_file = client.get(f"/api/v1/document-jobs/{job_id}/download-url", headers=headers)
            self.assertEqual(missing_file.status_code, 404)
            self.assertEqual(missing_file.json()["error_code"], "not_found")
            self.assertEqual(missing_file.json()["error"]["reason_code"], "result_file_missing")

    def test_signed_policy_event_and_audit_have_only_safe_summaries(self):
        with self._application("file", eager=True) as (runtime, client, headers):
            job_id = self._create(client, headers)["job_id"]
            job = runtime.document_job_repository.update_document_job(job_id, quality_status="blocked")
            file = runtime.document_file_repository.get_document_file(job.result_file_id)
            content = runtime.file_upload_service.read_file_content(file)
            signed = self._signed(client, {**headers, "X-Trace-Id": "availability-audit"}, job_id)
            event = [item for item in runtime.document_job_event_repository.list_document_job_events(job_id)
                     if item.event_type == "download_authorized"][-1]
            audit = [item for item in runtime.audit_event_repository.list_audit_events()
                     if item.action == "document_job.download_authorize"][-1]
            expected = {"generation": job.retry_count, "file_id": file.id, "classification": "internal_only",
                        "warning_code": "quality_blocked_not_deliverable"}
            self.assertEqual(audit.details, expected)
            self.assertEqual(event.payload, {
                **expected, "file_type": "generated_word",
                "expires_at": datetime.fromisoformat(signed["expires_at"]).isoformat(),
            })
            self.assertEqual(event.trace_id, "availability-audit")
            self.assertEqual(audit.trace_id, "availability-audit")
            serialized = json.dumps({"event": event.model_dump(mode="json"), "audit": audit.model_dump(mode="json")})
            for sensitive in (signed["download_url"], signed["download_url"].split("token=")[1],
                              file.object_key, file.bucket, content.hex(), "warning_message", "object_key", "token"):
                self.assertNotIn(sensitive, serialized)

    def test_artifacts_candidates_and_scope_keep_their_existing_security_boundaries(self):
        with self._application("file", eager=True) as (runtime, client, headers):
            created = self._create(client, headers)
            job_id = created["job_id"]
            job = runtime.document_job_repository.get_document_job(job_id)
            file = runtime.document_file_repository.get_document_file(job.result_file_id)
            for file_id in (job.source_file_id, job.document_ir_file_id):
                artifact = self._signed(client, headers, job_id, file_id=file_id)
                for field in ("classification", "warning_code", "warning_message"):
                    self.assertIsNone(artifact[field])
            candidate = runtime.file_upload_service.register_result_candidate(
                tenant_id=job.tenant_id, company_id=job.company_id, job_id=job.id, created_by=job.created_by,
                filename="candidate.docx", content=runtime.file_upload_service.read_file_content(file), metadata=file.metadata,
            )
            rejected = client.get(f"/api/v1/document-jobs/{job_id}/download-url", headers=headers, params={"file_id": candidate.id})
            self.assertEqual(rejected.status_code, 409)
            self.assertEqual(rejected.json()["error"]["reason_code"], "file_not_current")
            token = _build_download_token(runtime, job_id=job.id, file_id=candidate.id, expires_at=utc_now() + timedelta(minutes=1))
            self.assertEqual(client.get(f"/api/v1/document-jobs/{job_id}/download", params={"token": token}).status_code, 409)
            for username, password in (("operator2", "operator2-pass"), ("other_tenant", "operator-pass"),
                                       ("other_company", "operator-pass")):
                other = fixtures.build_auth_header(client, username=username, password=password)
                denied = client.get(f"/api/v1/document-jobs/{job_id}/download-url", headers=other)
                self.assertEqual(denied.status_code, 403)
                self.assertNotIn("reason_code", denied.json()["error"])
            admin = fixtures.build_auth_header(client, username="admin", password="admin-pass")
            self._signed(client, admin, job_id)
            runtime.document_file_repository.update_document_file(file.id, expires_at=utc_now() - timedelta(seconds=1))
            expired = client.get(f"/api/v1/document-jobs/{job_id}/download-url", headers=headers)
            self.assertEqual(expired.status_code, 409)
            self.assertEqual(expired.json()["error"]["reason_code"], "file_expired")
            download = self._detail(client, headers, job_id)["available_actions"]["download"]
            self.assertFalse(download["enabled"])
            self.assertEqual(download["disabled_reason_code"], "file_expired")

    def test_download_signing_keeps_event_and_audit_failures_explicit(self):
        with self._application("file", eager=True) as (runtime, client, headers):
            job_id = self._create(client, headers)["job_id"]
            for owner, method in ((runtime.document_job_service, "record_download_authorized"), (runtime.audit_service, "record")):
                with self.subTest(method=method), patch.object(owner, method, side_effect=OSError("模拟审计存储失败")):
                    with self.assertRaisesRegex(OSError, "模拟审计存储失败"):
                        client.get(f"/api/v1/document-jobs/{job_id}/download-url", headers=headers)

    def test_source_pdf_during_execution_keeps_ordinary_download_contract(self):
        with self._application("file") as (_runtime, client, headers):
            created = self._create(client, headers, translation=False)
            self.assertFalse(created["job"]["available_actions"]["download"]["enabled"])
            source = self._signed(client, headers, created["job_id"], file_id=created["job"]["source_file_id"])
            self.assertIsNone(source["classification"])
            self.assertIsNone(source["warning_code"])
            downloaded = client.get(source["download_url"])
            self.assertEqual(downloaded.status_code, 200)
            self.assertTrue(downloaded.content.startswith(b"%PDF"))
