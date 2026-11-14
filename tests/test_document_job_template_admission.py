"""验证模板目录变化后，新任务准入与旧任务执行的边界。"""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from app.domains.resources.integrity import resource_payload_sha256
from app.domains.resources.models import ResourceVersionStatus
from app.domains.templates.models import TemplateCatalogItem
from tests import test_fastapi_jobs_backend as fixtures
from tests.test_template_package_contract import bundled_template_paths


class DocumentJobTemplateAdmissionTests(TestCase):
    _upload_source_pdf = fixtures.FastAPIJobsBackendTests._upload_source_pdf

    def test_directory_rejects_new_jobs_and_clones_but_existing_job_can_retry_and_render(self):
        for deleted in (False, True):
            with self.subTest(deleted=deleted), TemporaryDirectory() as temp_dir:
                runtime = fixtures.build_mysql_test_runtime(
                    Path(temp_dir),
                    auth_jwt_secret_key="test-jwt-secret",
                    auth_internal_users_json=fixtures.build_auth_users_json(),
                    document_jobs_worker_backend="eager",
                    jobs_artifact_storage_backend="local_object",
                )
                execution = runtime.document_job_execution_service
                execution.fake_mineru_client.result_zip_bytes = fixtures.make_english_mineru_zip_bytes()
                docx, _ = bundled_template_paths()
                fixtures.publish_template_resource_version(
                    runtime, template_id="custom", version="1", content=docx.read_bytes(), make_default=True,
                )
                template = TemplateCatalogItem(id="custom", name="自定义模板")
                with fixtures.TestClient(fixtures.create_app(runtime)) as client:
                    catalog = Mock()
                    templates = runtime.template_read_service
                    catalog.get_template.return_value = template
                    with patch.object(templates, "catalog_repository", catalog):
                        admin = fixtures.build_auth_header(client, username="admin", password="admin-pass")
                        source = self._upload_source_pdf(client, admin)
                        with patch.object(execution.rendering.word_renderer, "render_to_result", side_effect=RuntimeError()):
                            created = client.post(
                                "/api/v1/document-jobs", headers=admin,
                                json={"source_file_id": source["id"], "template_version_id": "custom@1"},
                            )
                        self.assertEqual(created.status_code, 201, created.json())
                        job_id = created.json()["job_id"]
                        original = runtime.document_job_repository.get_document_job(job_id)
                        binding = original.request_snapshot["resources"]["template"]
                        self.assertEqual(binding["resource_id"], "custom")
                        self.assertEqual(original.status, "failed")

                        catalog.get_template.return_value = template.model_copy(update={"enabled": False, "deleted": deleted})
                        new_source = self._upload_source_pdf(client, admin)
                        for selection in ("custom", "custom@1"):
                            rejected = client.post(
                                "/api/v1/document-jobs", headers=admin,
                                json={"source_file_id": new_source["id"], "template_version_id": selection},
                            )
                            self.assertEqual(rejected.status_code, 404, rejected.json())
                        rejected_clone = client.post(f"/api/v1/document-jobs/{job_id}/clone", headers=admin, json={})
                        self.assertEqual(rejected_clone.status_code, 404, rejected_clone.json())
                        self.assertEqual([job.id for job in runtime.document_job_repository.list_document_jobs()], [job_id])

                        catalog.get_template.reset_mock()
                        retry = client.post(
                            f"/api/v1/document-jobs/{job_id}/retry", headers=admin, json={"use_latest_term_assets": True},
                        )
                        self.assertEqual(retry.status_code, 200, retry.json())
                        finished = runtime.document_job_repository.get_document_job(job_id)
                        self.assertEqual(finished.status, "succeeded", finished.error_message)
                        self.assertEqual(finished.request_snapshot["resources"]["template"], binding)
                        self.assertTrue(finished.result_file_id)
                        catalog.get_template.assert_not_called()

    def test_cloning_a_draft_checks_role_and_preserves_binding_after_publication(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = fixtures.build_mysql_test_runtime(
                root,
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=fixtures.build_auth_users_json(),
            )
            docx, _ = bundled_template_paths()
            upload = root / "draft.docx"
            upload.write_bytes(docx.read_bytes())
            draft = runtime.template_read_service.create_template_version(
                "default", source_path=upload, source_filename=upload.name,
            )
            repository = runtime.resource_version_service.repository
            with fixtures.TestClient(fixtures.create_app(runtime)) as client:
                admin = fixtures.build_auth_header(client, username="admin", password="admin-pass")
                operator = fixtures.build_auth_header(client)
                source = self._upload_source_pdf(client, admin)
                created = client.post(
                    "/api/v1/document-jobs", headers=admin,
                    json={"source_file_id": source["id"], "template_version_id": draft.template_version_id},
                )
                self.assertEqual(created.status_code, 201, created.json())
                original = created.json()["job"]
                binding = original["request_snapshot"]["resources"]["template"]
                self.assertEqual(binding["status"], "draft")
                runtime.document_job_repository.update_document_job(original["id"], created_by="user_operator")
                clone_url = f"/api/v1/document-jobs/{original['id']}/clone"

                rejected = client.post(clone_url, headers=operator, json={})
                self.assertEqual(rejected.status_code, 400, rejected.json())
                self.assertIn("draft", rejected.json()["detail"])
                approved = client.post(clone_url, headers=admin, json={})
                self.assertEqual(approved.status_code, 201, approved.json())
                self.assertEqual(approved.json()["job"]["request_snapshot"]["resources"]["template"], binding)

                record = repository.get_resource_version("template", "default", str(draft.version))
                published_payload = {**record.payload, "verification_job_id": original["id"]}
                repository.save_resource_version(record.model_copy(update={
                    "status": ResourceVersionStatus.PUBLISHED,
                    "payload": published_payload,
                    "snapshot_hash": resource_payload_sha256(published_payload),
                }))
                cloned = client.post(clone_url, headers=operator, json={})
                self.assertEqual(cloned.status_code, 201, cloned.json())
                self.assertEqual(cloned.json()["job"]["request_snapshot"]["resources"]["template"], binding)

                repository.save_resource_version(record.model_copy(update={"status": ResourceVersionStatus.DISABLED}))
                rejected = client.post(clone_url, headers=operator, json={})
                self.assertEqual(rejected.status_code, 400, rejected.json())
