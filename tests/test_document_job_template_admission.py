"""验证模板目录变化后，新任务准入与旧任务执行的边界。"""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

import yaml

from app.domains.jobs.resource_snapshots import JobResourceSnapshotError
from app.domains.resources.integrity import content_sha256, resource_payload_sha256
from app.domains.resources.models import ResourceVersionStatus
from app.domains.templates.models import TemplateCatalogItem
from tests import test_fastapi_jobs_backend as fixtures
from tests.document_job_use_case_support import replace_dependency
from tests.test_template_package_contract import bundled_template_paths


class DocumentJobTemplateAdmissionTests(TestCase):
    _upload_source_pdf = fixtures.FastAPIJobsBackendTests._upload_source_pdf

    def test_legacy_without_yaml_rejects_new_job_and_clones_but_can_retry_and_download(self):
        with TemporaryDirectory() as temp_dir:
            runtime = fixtures.build_mysql_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=fixtures.build_auth_users_json(),
                document_jobs_worker_backend="eager",
                jobs_artifact_storage_backend="local_object",
            )
            execution = runtime.document_job_execution_service
            execution.fake_mineru_client.result_zip_bytes = fixtures.make_english_mineru_zip_bytes()
            versions = runtime.resource_version_service
            docx, _ = bundled_template_paths()
            fixtures.publish_template_resource_version(
                runtime, version="3", content=docx.read_bytes(), make_default=False,
            )
            with fixtures.TestClient(fixtures.create_app(runtime)) as client:
                admin = fixtures.build_auth_header(client, username="admin", password="admin-pass")
                source = self._upload_source_pdf(client, admin)
                create_url = "/api/v1/document-jobs"
                with patch.object(execution.rendering.word_renderer, "render_to_result", side_effect=RuntimeError()):
                    response = client.post(create_url, headers=admin, json={
                        "source_file_id": source["id"], "template_version_id": "default@3",
                    })
                self.assertEqual(response.status_code, 201, response.json())
                job_id = response.json()["job_id"]
                job = runtime.document_job_repository.get_document_job(job_id)
                # 构造旧服务曾经接受的合法无 YAML 绑定。
                record = versions.repository.get_resource_version("template", "default", "3")
                payload = {**record.payload, "layout_config_path": None, "layout_config_sha256": None}
                versions.repository.save_resource_version(record.model_copy(update={
                    "payload": payload, "snapshot_hash": resource_payload_sha256(payload),
                }))
                binding = versions.resolve_version("template", "default", "3").model_dump(mode="json")
                job.request_snapshot["resources"]["template"] = binding
                runtime.document_job_repository.update_document_job(job_id, request_snapshot=job.request_snapshot)
                versions.set_default("template", "default", "3")

                new_source = self._upload_source_pdf(client, admin)
                clone_url = f"{create_url}/{job_id}/clone"
                original_events = runtime.document_job_event_repository.list_document_job_events(job_id)
                for url, body in (
                    (create_url, {"source_file_id": new_source["id"]}),
                    (create_url, {"source_file_id": new_source["id"], "template_version_id": "default@3"}),
                    (clone_url, {}),
                    (clone_url, {"config_strategy": "use_current_defaults"}),
                    (clone_url, {"config_strategy": "select_published_versions", "template_version_id": "default@3"}),
                ):
                    with self.subTest(url=url, body=body):
                        result = client.post(url, headers=admin, json=body)
                        self.assertEqual(result.status_code, 400, result.json())
                        self.assertEqual(result.json()["error"]["reason_code"], "legacy_internal_only")
                self.assertEqual([job.id for job in runtime.document_job_repository.list_document_jobs()], [job_id])
                self.assertEqual(runtime.document_job_event_repository.list_document_job_events(job_id), original_events)
                self.assertIsNone(runtime.document_file_repository.get_document_file(new_source["id"]).job_id)

                retry = client.post(
                    f"{create_url}/{job_id}/retry", headers=admin, json={"use_latest_term_assets": True},
                )
                self.assertEqual(retry.status_code, 200, retry.json())
                finished = runtime.document_job_repository.get_document_job(job_id)
                self.assertEqual(finished.status, "succeeded", finished.error_message)
                self.assertEqual(finished.request_snapshot["resources"]["template"], binding)
                download = client.get(f"{create_url}/{job_id}/download-url", headers=admin)
                self.assertEqual(download.status_code, 200, download.json())
                self.assertEqual(download.json()["classification"], "internal_only")
                docx_download = client.get(download.json()["download_url"])
                self.assertEqual(docx_download.status_code, 200)
                self.assertTrue(docx_download.content.startswith(b"PK"))

    def test_registered_default_never_falls_back_to_unbound_snapshot(self):
        with TemporaryDirectory() as temp_dir:
            runtime = fixtures.build_mysql_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=fixtures.build_auth_users_json(),
            )
            with fixtures.TestClient(fixtures.create_app(runtime)) as client:
                admin = fixtures.build_auth_header(client, username="admin", password="admin-pass")
                source = self._upload_source_pdf(client, admin)
                queue = replace_dependency(runtime.document_job_use_cases, "task_queue", Mock())
                service = runtime.job_resource_snapshot_service
                with patch.object(service, "build_snapshot", side_effect=JobResourceSnapshotError(
                    "模板资源快照服务不可用。", category="service_unavailable", code="resource_snapshot_unavailable",
                )):
                    response = client.post("/api/v1/document-jobs", headers=admin, json={"source_file_id": source["id"]})
                self.assertEqual(response.status_code, 503, response.json())
                self.assertEqual(response.json()["error_code"], "resource_snapshot_unavailable")
                self.assertEqual(runtime.document_job_repository.list_document_jobs(), [])
                queue.enqueue.assert_not_called()

    def test_new_file_backend_job_pins_yaml_bytes_through_rendering(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docx, bundled_yaml = bundled_template_paths()
            layout = root / "layout.yaml"
            original_yaml = bundled_yaml.read_bytes()
            layout.write_bytes(original_yaml)
            manifest = root / "templates.yaml"
            manifest.write_text(yaml.safe_dump({"templates": [{
                "id": "default",
                "name": "模板",
                "template_path": str(docx),
                "layout_config_path": str(layout),
                "is_default_seed": True,
            }]}), encoding="utf-8")
            runtime = fixtures.build_test_runtime(
                root,
                templates_manifest_path=str(manifest),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=fixtures.build_auth_users_json(),
                document_jobs_worker_backend="eager",
                jobs_artifact_storage_backend="local_object",
            )
            execution = runtime.document_job_execution_service
            execution.fake_mineru_client.result_zip_bytes = fixtures.make_english_mineru_zip_bytes()
            renderer = execution.rendering.word_renderer
            render = renderer.render_to_result

            def change_yaml_before_render(*args, **kwargs):
                layout.write_bytes(original_yaml + b"\n# changed after admission\n")
                return render(*args, **kwargs)

            with fixtures.TestClient(fixtures.create_app(runtime)) as client:
                admin = fixtures.build_auth_header(client, username="admin", password="admin-pass")
                source = self._upload_source_pdf(client, admin)
                with patch.object(renderer, "render_to_result", side_effect=change_yaml_before_render):
                    result = client.post("/api/v1/document-jobs", headers=admin, json={"source_file_id": source["id"]})
                self.assertEqual(result.status_code, 201, result.json())
                job = runtime.document_job_repository.get_document_job(result.json()["job_id"])
                self.assertIsNone(job.request_snapshot["resources"])
                self.assertEqual(job.request_snapshot["template_layout_config_sha256"], content_sha256(original_yaml))
                self.assertEqual(job.status, "failed")
                self.assertIsNone(job.result_file_id)

                layout.write_bytes(original_yaml)
                retry = client.post(f"/api/v1/document-jobs/{job.id}/retry", headers=admin, json={})
                self.assertEqual(retry.status_code, 200, retry.json())
                recovered = runtime.document_job_repository.get_document_job(job.id)
                self.assertEqual(recovered.status, "succeeded", recovered.error_message)
                self.assertEqual(recovered.request_snapshot["template_layout_config_sha256"], content_sha256(original_yaml))

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
