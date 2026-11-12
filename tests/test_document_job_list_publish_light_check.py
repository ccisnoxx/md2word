"""列表仅判断发布状态，详情、发布前检查及提交仍认证真实证据。"""

import hashlib
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from app.domains.document_jobs.publication import observed_publication_source
from app.domains.document_jobs.publication_evidence import prepare_publication_evidence
from tests.document_job_list_query_v2_publication_fixtures import V2PublicationFixture
from tests import test_fastapi_jobs_backend as support
from tests import test_document_job_list_query_v2_service as service_fixtures
from tests.document_job_use_case_support import patch_use_case_clock, patch_publication_evidence


class DocumentJobListPublishLightCheckTests(V2PublicationFixture, TestCase):
    def test_publication_replay_preserves_one_protected_final_file(self):
        for kind in ("file", "sqlite"):
            with self.subTest(kind=kind), self.publication_runtime(kind=kind) as (
                runtime, job, _, _, client, headers, _,
            ):
                repository = runtime.document_job_repository
                files = runtime.document_file_repository
                file = files.get_document_file(job.result_file_id)
                original = runtime.file_upload_service.read_file_content(file)
                checksum = "sha256:" + hashlib.sha256(original).hexdigest()
                admin_headers = support.build_auth_header(client, "admin", "admin-pass")
                base_url = f"/api/v1/document-jobs/{job.id}"
                payload = {
                    "request_id": str(uuid4()),
                    "note": "首次批准交付",
                    "expected_source": observed_publication_source(job, file).model_dump(mode="json"),
                }
                draft_delete = client.post(f"{base_url}/delete-preview", headers=admin_headers)
                self.assertEqual(draft_delete.status_code, 200, draft_delete.text)
                created = client.post(f"{base_url}/publish", headers=admin_headers, json=payload)
                self.assertEqual(created.status_code, 201, created.text)
                publication = created.json()["publication"]
                publication_id = publication["publication_id"]
                self.assertEqual((publication["result_file_id"], publication["result_sha256"]), (file.id, checksum))

                replay = client.post(f"{base_url}/publish", headers=admin_headers, json=payload)
                self.assertEqual(replay.status_code, 200, replay.text)
                self.assertEqual(replay.json()["publication"], publication)
                for changed, reason in (
                    ({"note": "更改同一请求的交付备注"}, "publication_request_conflict"),
                    ({"request_id": str(uuid4())}, "publication_already_exists"),
                ):
                    rejected = client.post(f"{base_url}/publish", headers=admin_headers, json={**payload, **changed})
                    self.assertEqual(rejected.status_code, 409, rejected.text)
                    self.assertEqual(rejected.json()["error"]["reason_code"], reason)

                record, = repository.list_document_job_publications(job.id)
                self.assertEqual((record.id, record.result_sha256), (publication_id, checksum))
                current = repository.get_document_job(job.id)
                self.assertEqual((current.current_publication_id, current.delivery_status), (record.id, "published"))
                rejected_delete = client.post(f"{base_url}/delete", headers=admin_headers,
                    json={"preview_hash": draft_delete.json()["preview_hash"]})
                self.assertEqual(rejected_delete.status_code, 409, rejected_delete.text)
                self.assertTrue(files.is_document_file_protected(file.id))
                with self.assertRaisesRegex(ValueError, "不可变发布记录"):
                    files.update_document_file(file.id, checksum_sha256="sha256:" + "0" * 64)
                self.assertEqual(files.get_document_file(file.id), file)

                archive = client.delete(base_url, headers=admin_headers)
                self.assertEqual(archive.status_code, 200, archive.text)
                self.assertEqual(archive.json()["job"]["delivery_status"], "published")
                issued = client.get(f"{base_url}/publications/{publication_id}/download-url", headers=headers)
                self.assertEqual(issued.status_code, 200, issued.text)
                delivery = issued.json()
                self.assertEqual(
                    (delivery["publication_id"], delivery["result_file_id"], delivery["result_sha256"],
                     delivery["classification"]),
                    (publication_id, file.id, checksum, "final_delivery"),
                )
                download = client.get(delivery["download_url"])
                self.assertEqual(download.status_code, 200, download.text[:300] if download.is_error else "")
                self.assertEqual(download.content, original)

    def test_admin_list_skips_evidence_but_default_read_views_verify(self):
        for kind in ("file", "sqlite"):
            with self.subTest(kind=kind), self.publication_runtime(kind=kind) as (
                runtime, job, admin, user, client, headers, provider,
            ):
                service = runtime.document_job_use_cases
                admin_headers = support.build_auth_header(client, "admin", "admin-pass")
                observations = []
                observe = service.read_model.build_job_read_observation

                def capture_observation(*args, **kwargs):
                    observation = observe(*args, **kwargs)
                    observations.append(observation)
                    return observation

                with patch_publication_evidence(wraps=prepare_publication_evidence) as prepare, patch.object(
                    runtime.file_upload_service, "read_file_content",
                    wraps=runtime.file_upload_service.read_file_content) as read, patch.object(service.read_model, "build_job_read_observation", side_effect=capture_observation):
                    response = client.get("/api/v1/document-jobs", headers=admin_headers)
                self.assertEqual(response.status_code, 200, response.text)
                item = response.json()["items"][0]
                self.assertTrue(item["available_actions"]["publish"]["enabled"])
                self.assertEqual(item["delivery_status"], "ready_to_publish")
                prepare.assert_not_called()
                read.assert_not_called()
                self.assertEqual(len(observations), 1)
                evidence = next(check for check in observations[0][2] if check["code"] == "publication_evidence")
                self.assertEqual(evidence, {
                    "code": "publication_evidence", "status": "not_checked", "reason_code": None,
                    "message": "尚未核验预览、实物完整性、执行快照及保留能力；提交时由后端完整核验。",
                })

                # observed_result 只固定主件观察，不能隐式关闭默认深度核验。
                file = runtime.document_file_repository.get_document_file(job.result_file_id)
                with patch_publication_evidence(wraps=prepare_publication_evidence) as prepare:
                    _, actions = service.read_model.build_job_read_view(job, user=admin, observed_result=file)
                    self.assertTrue(actions["publish"].enabled)
                    self.assertTrue(service.read_model.build_available_actions(job, user=admin)["publish"].enabled)
                    preflight = client.get(f"/api/v1/document-jobs/{job.id}/publications", headers=admin_headers)
                self.assertEqual(prepare.call_count, 3)
                self.assertEqual(preflight.status_code, 200, preflight.text)
                evidence = next(check for check in preflight.json()["preflight_checks"]
                    if check["code"] == "publication_evidence")
                self.assertEqual(evidence["status"], "passed")
                self.assertEqual(len(provider.inputs), 1)
                self.publish(runtime, job, admin)
                published_list = client.get("/api/v1/document-jobs", headers=admin_headers)
                self.assertEqual(published_list.status_code, 200, published_list.text)
                action = published_list.json()["items"][0]["available_actions"]["publish"]
                self.assertFalse(action["enabled"])
                self.assertEqual(action["disabled_reason_code"], "already_published")

    def test_list_can_enable_while_detail_preflight_and_post_reject_bad_evidence(self):
        with self.publication_runtime() as (runtime, job, admin, user, client, headers, provider):
            admin_headers = support.build_auth_header(client, "admin", "admin-pass")
            file = runtime.document_file_repository.get_document_file(job.result_file_id)
            source = observed_publication_source(job, file).model_dump(mode="json")
            for failure, reason, status_code in (
                (FileNotFoundError("测试对象缺失"), "publication_result_unavailable", 409),
                (OSError("测试存储不可用"), "publication_storage_unavailable", 503),
                (None, "publication_hash_mismatch", 409),
            ):
                with self.subTest(reason=reason), patch.object(
                    runtime.file_upload_service, "read_file_content", side_effect=failure,
                    return_value=b"invalid-publication-content",
                ) as read, patch_publication_evidence(wraps=prepare_publication_evidence) as prepare:
                    listed = client.get("/api/v1/document-jobs", headers=admin_headers)
                    self.assertEqual(listed.status_code, 200, listed.text)
                    list_actions = listed.json()["items"][0]["available_actions"]
                    self.assertTrue(list_actions["publish"]["enabled"])
                    self.assertEqual(listed.json()["items"][0]["delivery_status"], "ready_to_publish")
                    read.assert_not_called()
                    prepare.assert_not_called()
                    detail = client.get(f"/api/v1/document-jobs/{job.id}", headers=admin_headers)
                    preflight = client.get(f"/api/v1/document-jobs/{job.id}/publications", headers=admin_headers)
                    self.assertEqual(detail.json()["delivery_status"], job.delivery_status)
                    for response in (detail, preflight):
                        self.assertEqual(response.status_code, 200, response.text)
                        actions = response.json()["available_actions"]
                        self.assertFalse(actions["publish"]["enabled"])
                        self.assertEqual(actions["publish"]["disabled_reason_code"], reason)
                        self.assertEqual({key: value for key, value in actions.items() if key != "publish"},
                            {key: value for key, value in list_actions.items() if key != "publish"})
                    evidence = next(check for check in preflight.json()["preflight_checks"]
                        if check["code"] == "publication_evidence")
                    self.assertEqual((evidence["status"], evidence["reason_code"]), ("blocked", reason))
                    published = client.post(f"/api/v1/document-jobs/{job.id}/publish", headers=admin_headers,
                        json={"request_id": str(uuid4()), "note": "验证证据拒绝", "expected_source": source})
                    self.assertEqual(published.status_code, status_code, published.text)
                    self.assertEqual(published.json()["error_code"], "conflict" if status_code == 409 else "service_unavailable")
                    self.assertEqual(published.json()["error"]["reason_code"], reason)
                    self.assertEqual(prepare.call_count, 3)
                    self.assertEqual(read.call_count, 3)
                self.assertEqual(runtime.document_job_repository.get_document_job(job.id), job)
                self.assertEqual(runtime.document_job_repository.list_document_job_publications(job.id), [])

            with patch_publication_evidence() as prepare, patch.object(
                runtime.file_upload_service, "read_file_content", side_effect=AssertionError("非管理员不得读取正文"),
            ) as read:
                listed = client.get("/api/v1/document-jobs", headers=headers)
                detail = client.get(f"/api/v1/document-jobs/{job.id}", headers=headers)
            self.assertEqual(listed.status_code, 200, listed.text)
            self.assertEqual(detail.status_code, 200, detail.text)
            actions = listed.json()["items"][0]["available_actions"]
            self.assertEqual(actions, detail.json()["available_actions"])
            self.assertEqual(actions["publish"]["disabled_reason_code"], "admin_required")
            prepare.assert_not_called()
            read.assert_not_called()


class DocumentJobListPublishStateTests(TestCase):
    environment = service_fixtures.DocumentJobListV2ServiceTests.environment
    verified = service_fixtures.DocumentJobListV2ServiceTests.verified

    def test_existing_state_reasons_and_order_are_preserved(self):
        cases = (
            ({}, "approved", "admin", True, None),
            ({"quality_status": "warning"}, "approved", "admin", True, None),
            ({}, "approved", "operator", True, "admin_required"),
            ({"quality_status": "pending"}, "approved", "admin", True, "quality_status_pending"),
            ({"quality_status": "blocked"}, "approved", "admin", True, "quality_status_blocked"),
            ({}, "unreviewed", "admin", True, "review_status_unreviewed"),
            ({}, "needs_fix", "admin", True, "review_status_needs_fix"),
            ({}, "blocked", "admin", True, "review_status_blocked"),
            ({}, "approved", "admin", False, "publication_disabled"),
            ({"archived_at": service_fixtures.NOW}, "approved", "admin", True, "publication_state_conflict"),
            ({"result_file_id": None}, "approved", "admin", True, "result_file_missing"),
            ({"status": "running", "stage": "uploading"}, "unreviewed", "admin", True, "job_not_completed"),
        )
        for changes, review, role, enabled, reason in cases:
            with self.subTest(changes=changes, review=review, role=role, enabled=enabled), self.environment("sqlite") as (
                jobs, files, service,
            ):
                job, file = self.verified(jobs, files, review=review)
                if changes:
                    job = jobs.update_document_job(job.id, **changes)
                service.read_model.settings.document_publication_enabled = enabled
                user = service_fixtures.ADMIN if role == "admin" else service_fixtures.USER
                with patch_use_case_clock(return_value=service_fixtures.NOW), patch_publication_evidence(side_effect=AssertionError("列表不得核验发布证据"),
                ) as prepare:
                    listed = service.queries.list_jobs(user=user, page=1, page_size=20, status_filter=None,
                        include_archived=True)
                    view, actions = listed.items[0]
                    action = actions["publish"]
                    self.assertEqual(action.enabled, reason is None)
                    self.assertEqual(action.disabled_reason_code, reason)
                    if reason is not None:
                        baseline, expected = service.read_model.build_job_read_view(job, user=user)
                        self.assertEqual(actions, expected)
                        self.assertEqual(view, baseline)
                        self.assertEqual(action.disabled_reason, action.disabled_reasons[0].message)
                prepare.assert_not_called()
