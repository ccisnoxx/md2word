# tests/test_fastapi_jobs_backend.py: 覆盖 FastAPI jobs API、workflow 和 artifact 合同。

import io
import json
import hashlib
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest import TestCase

import yaml

VENDOR_DIR = Path(__file__).resolve().parents[1] / ".python_packages"
if VENDOR_DIR.exists():
    vendor_path = str(VENDOR_DIR)
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)

from fastapi.testclient import TestClient

from app.conversion.contracts import ArtifactDescriptor, ConversionFailure, ConversionResult
from app.core.config import Settings
from app.core.job_models import JobFile, JobRecord, JobStageMessage, SourcePdfJobContext, build_source_pdf_context_patch, utc_now
from app.core.job_paths import build_job_paths, ensure_job_dirs
from app.core.runtime import AppRuntime
from app.main import create_app
from app.repositories.file_job_repository import FileJobRepository
from app.repositories.file_term_rule_repository import FileTermRuleRepository
from app.services.health_service import HealthService
from app.services.jobs.artifacts import JobArtifactService
from app.services.jobs.command import JobCommandService
from app.services.jobs.dispatch import InProcessStageDispatcher
from app.services.jobs.lifecycle import JobLifecycleService
from app.services.jobs.query import JobQueryService
from app.services.jobs.stage import JobStageService
from app.services.term_rules.bootstrap import TermRuleBootstrapService
from app.services.term_rules.import_validation import TermRuleImportValidationService
from app.services.term_rules.service import TermRuleService
from app.services.term_rules.sync_files import TermRuleFileSyncService
from app.services.templates.read_service import TemplateReadService


class FakeMinerUClient:
    def __init__(self) -> None:
        self.calls = []
        self.raise_error = False
        self.download_calls = []
        self.raise_download_error = False

    def upload_files_batch(
        self,
        file_paths,
        *,
        task_uuids=None,
        enable_formula=True,
        enable_table=True,
        language="en",
        callback=None,
        seed=None,
    ):
        if self.raise_error:
            raise RuntimeError("mineru boom")
        self.calls.append(
            {
                "file_paths": [str(path) for path in file_paths],
                "task_uuids": task_uuids,
                "enable_formula": enable_formula,
                "enable_table": enable_table,
                "language": language,
                "callback": callback,
                "seed": seed,
            }
        )
        return "batch_test_001", ["https://example.com/upload"]

    def download_result_zip(self, result_url, output_path):
        if self.raise_download_error:
            raise RuntimeError("mineru download boom")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-parsed-result-zip")
        self.download_calls.append({"result_url": result_url, "output_path": str(output_path)})
        return output_path


class FakeConversionService:
    def __init__(self) -> None:
        self.requests = []
        self.raise_error = False

    def convert(self, request):
        if self.raise_error:
            raise ConversionFailure("conversion_failed", "boom")
        self.requests.append(request)
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        request.output_path.write_bytes(b"fake-docx")
        artifacts = [ArtifactDescriptor(file_type="result_docx", path=request.output_path)]
        if request.translation_request_output is not None:
            request.translation_request_output.parent.mkdir(parents=True, exist_ok=True)
            request.translation_request_output.write_text(
                json.dumps({"items": []}, ensure_ascii=False),
                encoding="utf-8",
            )
            artifacts.append(
                ArtifactDescriptor(
                    file_type="translation_request",
                    path=request.translation_request_output,
                )
            )
        return ConversionResult(
            source_path=request.package_path,
            output_docx_path=request.output_path,
            pages=2,
            document_language="zh",
            artifacts=artifacts,
        )


def build_test_runtime(
    data_dir: Path,
    *,
    openai_api_key: str = "",
    mineru_api_token: str = "",
    public_deployment_mode: str = "internal",
    mineru_callback_token: str = "",
    mineru_callback_url: str = "",
    mineru_uid: str = "",
    mineru_result_host_allowlist: str = "mineru.net,cdn-mineru.openxlab.org.cn",
    admin_token: str = "",
    templates_manifest_path: str | None = None,
    term_rules_seed_path: str | None = None,
) -> AppRuntime:
    settings = Settings(
        _env_file=None,
        data_dir=str(data_dir),
        app_name="md2word_file_test",
        openai_api_key=openai_api_key,
        openai_base_url="",
        openai_model="deepseek-v4-flash",
        mineru_api_token=mineru_api_token,
        public_deployment_mode=public_deployment_mode,
        mineru_callback_token=mineru_callback_token,
        mineru_callback_url=mineru_callback_url,
        mineru_uid=mineru_uid,
        mineru_result_host_allowlist=mineru_result_host_allowlist,
        admin_token=admin_token,
        **({"templates_manifest_path": templates_manifest_path} if templates_manifest_path else {}),
        **({"term_rules_seed_path": term_rules_seed_path} if term_rules_seed_path else {}),
    )
    repository = FileJobRepository(settings.data_path)
    health_service = HealthService(settings)
    template_read_service = TemplateReadService(settings)
    term_rule_repository = FileTermRuleRepository(settings.term_rules_store_file)
    term_rule_service = TermRuleService(
        term_rule_repository,
        settings.term_rules_runtime_yaml_file,
        settings.term_rules_seed_file,
    )
    term_rule_import_validation_service = TermRuleImportValidationService()
    term_rule_file_sync_service = TermRuleFileSyncService(
        term_rule_repository,
        settings.term_rules_runtime_yaml_file,
        settings.term_rules_seed_file,
        repository_backend="file",
    )
    TermRuleBootstrapService(
        term_rule_repository,
        settings.term_rules_runtime_yaml_file,
        settings.term_rules_seed_file,
        repository_backend="file",
    ).bootstrap()
    template_read_service.get_default_template_id()
    conversion_service = FakeConversionService()
    artifact_service = JobArtifactService()
    fake_mineru_client = FakeMinerUClient()
    stage_service = JobStageService(
        settings,
        repository,
        conversion_service,
        artifact_service,
        mineru_client_factory=lambda: fake_mineru_client,
        resolve_template_path=template_read_service.resolve_job_template_path,
        resolve_subscript_config_path=lambda: settings.subscript_config_path,
    )
    stage_service.fake_mineru_client = fake_mineru_client
    stage_dispatcher = InProcessStageDispatcher(stage_service)
    command_service = JobCommandService(settings, repository, stage_service, artifact_service)
    lifecycle_service = JobLifecycleService(
        repository=repository,
        stage_repository=repository,
        stage_service=stage_service,
        artifact_service=artifact_service,
    )
    query_service = JobQueryService(repository)
    return AppRuntime(
        settings=settings,
        repository=repository,
        health_service=health_service,
        template_read_service=template_read_service,
        term_rule_service=term_rule_service,
        term_rule_import_validation_service=term_rule_import_validation_service,
        term_rule_file_sync_service=term_rule_file_sync_service,
        artifact_service=artifact_service,
        command_service=command_service,
        lifecycle_service=lifecycle_service,
        query_service=query_service,
        stage_service=stage_service,
        stage_dispatcher=stage_dispatcher,
    )


def make_zip_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("content_list_v2.json", "[]")
    return buffer.getvalue()


def build_callback_payload(*, batch_id: str, data_id: str, state: str, full_zip_url: str | None = None, uid: str | None = None) -> tuple[dict, str]:
    data = {
        "batch_id": batch_id,
        "extract_result": [
            {
                "data_id": data_id,
                "state": state,
                **({"full_zip_url": full_zip_url} if full_zip_url else {}),
            }
        ],
    }
    content = json.dumps(data, ensure_ascii=False)
    payload = {"batch_id": batch_id, "content": content}
    if uid is not None:
        payload["uid"] = uid
    return payload, content


def write_templates_manifest(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"templates": entries}, allow_unicode=True, sort_keys=False), encoding="utf-8")


class FastAPIJobsBackendTests(TestCase):
    def test_health_ready_reports_runtime_dependencies(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(build_test_runtime(Path(temp_dir)))
            with TestClient(app) as client:
                response = client.get("/api/v1/health/ready")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["app_name"], "md2word_file_test")
        self.assertEqual(payload["dependency_checks"]["configured_repository_backend"], "file")
        self.assertEqual(payload["dependency_checks"]["effective_repository_backend"], "file")
        self.assertTrue(payload["dependency_checks"]["jobs_dir_exists"])
        self.assertTrue(payload["dependency_checks"]["stage_spool_dir_exists"])
        self.assertTrue(payload["dependency_checks"]["jobs_dir_writable"])
        self.assertEqual(payload["dependency_checks"]["stage_spool_pending_messages"], 0)
        self.assertEqual(payload["dependency_checks"]["default_translation_mode"], "direct")
        self.assertTrue(payload["dependency_checks"]["translation_client_configured"] is False)
        self.assertTrue(payload["dependency_checks"]["translation_prompt_exists"])
        self.assertFalse(payload["dependency_checks"]["mineru_api_token_configured"])

    def test_templates_read_api_returns_default_template_and_bound_configs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(build_test_runtime(Path(temp_dir)))
            with TestClient(app) as client:
                list_response = client.get("/api/v1/templates")
                self.assertEqual(list_response.status_code, 200)
                items = list_response.json()["items"]
                self.assertEqual(len(items), 1)
                self.assertEqual(items[0]["id"], "default")
                self.assertTrue(items[0]["is_default"])
                self.assertTrue(items[0]["template"]["exists"])
                self.assertTrue(items[0]["layout_config"]["exists"])
                self.assertTrue(items[0]["subscript_config"]["exists"])

                detail_response = client.get("/api/v1/templates/default")
                self.assertEqual(detail_response.status_code, 200)
                detail = detail_response.json()
                self.assertEqual(detail["id"], "default")
                self.assertEqual(detail["template"]["file_name"], "datasheet_template.docx")
                self.assertIsNotNone(detail["template"]["sha256"])
                self.assertEqual(detail["layout_config"]["file_name"], "datasheet_template.yaml")
                self.assertEqual(detail["subscript_config"]["file_name"], "runtime_subscripts_dictionary.yaml")

    def test_template_download_returns_docx(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(build_test_runtime(Path(temp_dir)))
            with TestClient(app) as client:
                response = client.get("/api/v1/templates/default/download")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            response.headers["content-type"],
        )
        self.assertGreater(len(response.content), 0)

    def test_templates_manifest_supports_multiple_visible_templates_and_admin_default_switch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            alt_template_path = temp_root / "alt_template.docx"
            alt_template_path.write_bytes(b"alt-docx")
            manifest_path = temp_root / "templates_manifest.yaml"
            repo_root = Path(__file__).resolve().parents[1]
            write_templates_manifest(
                manifest_path,
                [
                    {
                        "id": "default",
                        "name": "Default Template",
                        "description": "default",
                        "enabled": True,
                        "is_default_seed": True,
                        "template_path": str((repo_root / "template" / "datasheet_template.docx").resolve()),
                        "layout_config_path": str((repo_root / "template_configs" / "datasheet_template.yaml").resolve()),
                    },
                    {
                        "id": "alt",
                        "name": "Alt Template",
                        "description": "alt",
                        "enabled": True,
                        "is_default_seed": False,
                        "template_path": str(alt_template_path.resolve()),
                        "layout_config_path": str((repo_root / "template_configs" / "datasheet_template.yaml").resolve()),
                    },
                ],
            )

            runtime = build_test_runtime(
                temp_root,
                admin_token="secret-admin",
                templates_manifest_path=str(manifest_path),
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                list_response = client.get("/api/v1/templates")
                self.assertEqual(list_response.status_code, 200)
                items = list_response.json()["items"]
                self.assertEqual([item["id"] for item in items], ["default", "alt"])
                self.assertTrue(items[0]["is_default"])
                self.assertFalse(items[1]["is_default"])

                denied = client.patch("/api/v1/templates/alt/default")
                self.assertEqual(denied.status_code, 403)

                switch_response = client.patch(
                    "/api/v1/templates/alt/default",
                    headers={"X-Admin-Token": "secret-admin"},
                )
                self.assertEqual(switch_response.status_code, 200)
                self.assertEqual(switch_response.json()["id"], "alt")
                self.assertTrue(switch_response.json()["is_default"])

                refreshed = client.get("/api/v1/templates").json()["items"]
                self.assertFalse(refreshed[0]["is_default"])
                self.assertTrue(refreshed[1]["is_default"])

    def test_term_rule_categories_export_and_simulate_are_available(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(build_test_runtime(Path(temp_dir)))
            with TestClient(app) as client:
                categories_response = client.get("/api/v1/term-rule-categories")
                self.assertEqual(categories_response.status_code, 200)
                self.assertGreater(len(categories_response.json()["items"]), 0)

                export_response = client.get("/api/v1/term-rules/export")
                self.assertEqual(export_response.status_code, 200)
                self.assertIn("schema_version: 2", export_response.json()["yaml_text"])

                simulate_response = client.post(
                    "/api/v1/term-rules/simulate",
                    json={"text": "VIN VOUT"},
                )
                self.assertEqual(simulate_response.status_code, 200)
                self.assertIn("V<sub>IN</sub>", simulate_response.json()["html_preview"])

    def test_term_rule_import_and_sync_files_use_admin_boundary_and_replace_live_store(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), admin_token="secret-admin")
            app = create_app(runtime)
            payload = {
                "yaml_text": (
                    "schema_version: 2\n"
                    "categories:\n"
                    "  voltage_terms:\n"
                    "    name: 电压相关\n"
                    "    priority: 10\n"
                    "    enabled: true\n"
                    "    description: ''\n"
                    "rules:\n"
                    "  - source_term: VIN\n"
                    "    category: voltage_terms\n"
                    "    segments:\n"
                    "      - segment_text: V\n"
                    "        render_type: plain\n"
                    "      - segment_text: IN\n"
                    "        render_type: subscript\n"
                    "    apply_scope: both\n"
                    "    case_sensitive: true\n"
                    "    enabled: true\n"
                    "    priority: 10\n"
                    "    notes: ''\n"
                )
            }
            with TestClient(app) as client:
                validate_response = client.post("/api/v1/term-rules/import/validate", json=payload)
                self.assertEqual(validate_response.status_code, 200)
                self.assertTrue(validate_response.json()["valid"])

                denied_import = client.post("/api/v1/term-rules/import", json=payload)
                self.assertEqual(denied_import.status_code, 403)

                import_response = client.post(
                    "/api/v1/term-rules/import",
                    json=payload,
                    headers={"X-Admin-Token": "secret-admin"},
                )
                self.assertEqual(import_response.status_code, 200)
                self.assertEqual(import_response.json()["total"], 1)

                export_response = client.get("/api/v1/term-rules/export")
                self.assertIn("source_term: VIN", export_response.json()["yaml_text"])

                sync_response = client.post(
                    "/api/v1/term-rules/sync-files",
                    headers={"X-Admin-Token": "secret-admin"},
                )
                self.assertEqual(sync_response.status_code, 200)
                runtime_yaml_path = Path(sync_response.json()["runtime_yaml_path"])
                self.assertTrue(runtime_yaml_path.exists())
                self.assertIn("subscript_rules", runtime_yaml_path.read_text(encoding="utf-8"))

    def test_jobs_accept_visible_template_id_and_fallback_to_runtime_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            alt_template_path = temp_root / "alt_template.docx"
            alt_template_path.write_bytes(b"alt-docx")
            manifest_path = temp_root / "templates_manifest.yaml"
            repo_root = Path(__file__).resolve().parents[1]
            write_templates_manifest(
                manifest_path,
                [
                    {
                        "id": "default",
                        "name": "Default Template",
                        "description": "default",
                        "enabled": True,
                        "is_default_seed": True,
                        "template_path": str((repo_root / "template" / "datasheet_template.docx").resolve()),
                        "layout_config_path": str((repo_root / "template_configs" / "datasheet_template.yaml").resolve()),
                    },
                    {
                        "id": "alt",
                        "name": "Alt Template",
                        "description": "alt",
                        "enabled": True,
                        "is_default_seed": False,
                        "template_path": str(alt_template_path.resolve()),
                        "layout_config_path": str((repo_root / "template_configs" / "datasheet_template.yaml").resolve()),
                    },
                ],
            )

            runtime = build_test_runtime(
                temp_root,
                admin_token="secret-admin",
                templates_manifest_path=str(manifest_path),
            )
            runtime.template_read_service.set_default_template("alt")
            app = create_app(runtime)
            with TestClient(app) as client:
                explicit_response = client.post(
                    "/api/v1/jobs",
                    files={"package": ("mineru-output.zip", make_zip_bytes(), "application/zip")},
                    data={"translation_mode": "direct", "template_id": "alt"},
                )
                self.assertEqual(explicit_response.status_code, 201)
                explicit_job_id = explicit_response.json()["job_id"]
                explicit_detail = client.get(f"/api/v1/jobs/{explicit_job_id}").json()
                self.assertEqual(explicit_detail["template_id"], "alt")

                default_response = client.post(
                    "/api/v1/jobs",
                    files={"package": ("mineru-output.zip", make_zip_bytes(), "application/zip")},
                    data={"translation_mode": "direct"},
                )
                self.assertEqual(default_response.status_code, 201)
                default_job_id = default_response.json()["job_id"]
                default_detail = client.get(f"/api/v1/jobs/{default_job_id}").json()
                self.assertEqual(default_detail["template_id"], "alt")

            fake_service = runtime.stage_service.conversion_entrypoint
            self.assertEqual(len(fake_service.requests), 2)
            self.assertEqual(fake_service.requests[0].template_path, alt_template_path.resolve())
            self.assertEqual(fake_service.requests[1].template_path, alt_template_path.resolve())

    def test_upload_zip_runs_background_conversion_and_downloads_docx(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(build_test_runtime(Path(temp_dir)))
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs",
                    files={"package": ("mineru-output.zip", make_zip_bytes(), "application/zip")},
                    data={"translation_mode": "direct"},
                )
                self.assertEqual(create_response.status_code, 201)
                job_id = create_response.json()["job_id"]

                detail_response = client.get(f"/api/v1/jobs/{job_id}")
                self.assertEqual(detail_response.status_code, 200)
                detail_payload = detail_response.json()
                self.assertEqual(detail_payload["status"], "completed")
                self.assertTrue(detail_payload["result_ready"])
                self.assertEqual(detail_payload["files"][0]["file_type"], "source_package")
                self.assertEqual(detail_payload["files"][1]["file_type"], "result_docx")

                result_response = client.get(f"/api/v1/jobs/{job_id}/result")
                self.assertEqual(result_response.status_code, 200)
                self.assertIn(f"/api/v1/jobs/{job_id}/download/result", result_response.json()["download_url"])

                download_response = client.get(f"/api/v1/jobs/{job_id}/download/result")
                self.assertEqual(download_response.status_code, 200)
                self.assertEqual(download_response.content, b"fake-docx")

                events_response = client.get(f"/api/v1/jobs/{job_id}/events")
                self.assertEqual(events_response.status_code, 200)
                event_stages = [item["stage"] for item in events_response.json()["items"]]
                self.assertIn("job_created", event_stages)
                self.assertIn("job_completed", event_stages)

    def test_upload_zip_dispatches_stage_through_runtime_dispatcher(self):
        class RecordingDispatcher:
            def __init__(self) -> None:
                self.message_ids: list[str] = []
                self.replay_called = False

            def dispatch(self, message_id: str) -> None:
                self.message_ids.append(message_id)

            def replay_pending(self) -> None:
                self.replay_called = True

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir))
            dispatcher = RecordingDispatcher()
            runtime.stage_dispatcher = dispatcher
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs",
                    files={"package": ("mineru-output.zip", make_zip_bytes(), "application/zip")},
                    data={"translation_mode": "direct"},
                )
                self.assertEqual(create_response.status_code, 201)

            pending_messages = runtime.repository.list_pending_stage_messages()
            self.assertTrue(dispatcher.replay_called)
            self.assertEqual(dispatcher.message_ids, [pending_messages[0].id])
            self.assertEqual(pending_messages[0].stage, "convert_package")

    def test_upload_en2zh_preserves_conversion_request_options_and_translation_artifact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), openai_api_key="fake-key")
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs",
                    files={"package": ("mineru-output.zip", make_zip_bytes(), "application/zip")},
                    data={
                        "translation_mode": "en2zh",
                        "document_language": "auto",
                        "use_mineru_header_footer": "true",
                    },
                )
                self.assertEqual(create_response.status_code, 201)
                job_id = create_response.json()["job_id"]

                files_response = client.get(f"/api/v1/jobs/{job_id}/files")
                self.assertEqual(files_response.status_code, 200)
                file_types = [item["file_type"] for item in files_response.json()["files"]]
                self.assertEqual(file_types, ["source_package", "translation_request", "result_docx"])
                events_response = client.get(f"/api/v1/jobs/{job_id}/events")
                self.assertEqual(events_response.status_code, 200)
                event_stages = [item["stage"] for item in events_response.json()["items"]]
                self.assertIn("translation_started", event_stages)
                self.assertIn("translation_completed", event_stages)

            fake_service = runtime.stage_service.conversion_entrypoint
            self.assertEqual(len(fake_service.requests), 1)
            request = fake_service.requests[0]
            self.assertEqual(request.translation_mode, "en2zh")
            self.assertTrue(request.use_mineru_header_footer)
            self.assertIsNotNone(request.translation_request_output)
            self.assertEqual(request.translation_model, "deepseek-v4-flash")

    def test_upload_en2zh_rejects_when_translation_unavailable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(build_test_runtime(Path(temp_dir), openai_api_key=""))
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/jobs",
                    files={"package": ("mineru-output.zip", make_zip_bytes(), "application/zip")},
                    data={"translation_mode": "en2zh"},
                )

        self.assertEqual(response.status_code, 503)
        self.assertIn("OPENAI_API_KEY", response.json()["detail"])

    def test_upload_rejects_non_zip_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(build_test_runtime(Path(temp_dir)))
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/jobs",
                    files={"package": ("bad.txt", b"not-zip", "text/plain")},
                )

        self.assertEqual(response.status_code, 400)
        self.assertIn(".zip", response.json()["detail"])

    def test_upload_pdf_submits_to_mineru_and_enters_parsing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), mineru_api_token="token-123")
            app = create_app(runtime)
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("source.pdf", b"%PDF-1.4\nbody", "application/pdf")},
                    data={"translation_mode": "direct"},
                )
                self.assertEqual(response.status_code, 201)
                job_id = response.json()["job_id"]

                detail = client.get(f"/api/v1/jobs/{job_id}").json()
                self.assertEqual(detail["status"], "parsing")
                self.assertEqual(detail["source_kind"], "source_pdf")
                self.assertEqual(detail["mineru_batch_id"], "batch_test_001")
                self.assertEqual(detail["mineru_data_id"], job_id)
                self.assertEqual(detail["mineru_status"], "submitted")
                self.assertEqual(detail["mineru_result_zip_url"], None)
                persisted_job = runtime.repository.get_job(job_id)
                self.assertIsNotNone(persisted_job)
                self.assertIsNotNone(persisted_job.source_pdf_context)
                self.assertEqual(persisted_job.source_pdf_context.batch_id, "batch_test_001")
                self.assertEqual(persisted_job.source_pdf_context.data_id, job_id)
                self.assertEqual(persisted_job.source_pdf_context.upstream_status, "submitted")
                self.assertIsNone(persisted_job.source_pdf_context.result_zip_url)

                files = client.get(f"/api/v1/jobs/{job_id}/files").json()["files"]
                self.assertEqual(files[0]["file_type"], "source_pdf")

            fake_client = runtime.stage_service.fake_mineru_client
            self.assertEqual(len(fake_client.calls), 1)
            self.assertEqual(fake_client.calls[0]["task_uuids"], [job_id])

    def test_upload_pdf_rejects_when_mineru_token_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(build_test_runtime(Path(temp_dir), mineru_api_token=""))
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("source.pdf", b"%PDF-1.4\nbody", "application/pdf")},
                )

        self.assertEqual(response.status_code, 503)
        self.assertIn("MINERU_API_TOKEN", response.json()["detail"])

    def test_upload_pdf_rejects_invalid_pdf(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(build_test_runtime(Path(temp_dir), mineru_api_token="token-123"))
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("bad.pdf", b"not-pdf", "application/pdf")},
                )

        self.assertEqual(response.status_code, 400)
        self.assertIn("PDF", response.json()["detail"])

    def test_upload_pdf_marks_job_failed_when_mineru_submit_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), mineru_api_token="token-123")
            runtime.stage_service.fake_mineru_client.raise_error = True
            app = create_app(runtime)
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("source.pdf", b"%PDF-1.4\nbody", "application/pdf")},
                )
                self.assertEqual(response.status_code, 201)
                job_id = response.json()["job_id"]

                detail = client.get(f"/api/v1/jobs/{job_id}").json()
                self.assertEqual(detail["status"], "failed")
                self.assertEqual(detail["error_code"], "mineru_submit_failed")
                event_stages = [item["stage"] for item in detail["events"]]
                self.assertIn("mineru_submit_failed", event_stages)
                self.assertIn("job_failed", event_stages)

    def test_retry_requeues_failed_pdf_submit_to_mineru_stage(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), mineru_api_token="token-123")
            runtime.stage_service.fake_mineru_client.raise_error = True
            app = create_app(runtime)
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("source.pdf", b"%PDF-1.4\nbody", "application/pdf")},
                )
                self.assertEqual(response.status_code, 201)
                job_id = response.json()["job_id"]

                failed_detail = client.get(f"/api/v1/jobs/{job_id}").json()
                self.assertEqual(failed_detail["status"], "failed")

                runtime.stage_service.fake_mineru_client.raise_error = False
                retry_response = client.post(
                    f"/api/v1/jobs/{job_id}/retry",
                    data={"reason": "retry-pdf-submit"},
                )
                self.assertEqual(retry_response.status_code, 200)

                reparsed_detail = client.get(f"/api/v1/jobs/{job_id}").json()
                self.assertEqual(reparsed_detail["status"], "parsing")
                self.assertEqual(reparsed_detail["mineru_batch_id"], "batch_test_001")

    def test_callback_internal_mode_accepts_and_auto_completes_job(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), mineru_api_token="token-123")
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("source.pdf", b"%PDF-1.4\nbody", "application/pdf")},
                )
                job_id = create_response.json()["job_id"]
                detail = client.get(f"/api/v1/jobs/{job_id}").json()
                payload, _content = build_callback_payload(
                    batch_id=detail["mineru_batch_id"],
                    data_id=job_id,
                    state="done",
                    full_zip_url="https://mineru.net/result.zip",
                )
                callback_response = client.post("/api/v1/mineru-callbacks/result", json=payload)
                self.assertEqual(callback_response.status_code, 200)

                updated = client.get(f"/api/v1/jobs/{job_id}").json()
                self.assertEqual(updated["status"], "completed")
                self.assertEqual(updated["mineru_result_zip_url"], "https://mineru.net/result.zip")
                self.assertTrue(updated["result_ready"])
                persisted_job = runtime.repository.get_job(job_id)
                self.assertIsNotNone(persisted_job)
                self.assertIsNotNone(persisted_job.source_pdf_context)
                self.assertEqual(persisted_job.source_pdf_context.result_zip_url, "https://mineru.net/result.zip")
                files = runtime.repository.list_files(job_id)
                self.assertEqual([item.file_type for item in files], ["source_pdf", "parsed_result_package", "result_docx"])

    def test_callback_public_mode_requires_token(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                public_deployment_mode="single_tenant_public",
                mineru_callback_token="secret-token",
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                payload, _content = build_callback_payload(
                    batch_id="batch_x",
                    data_id="job_x",
                    state="done",
                    full_zip_url="https://mineru.net/result.zip",
                )
                response = client.post("/api/v1/mineru-callbacks/result", json=payload)

        self.assertEqual(response.status_code, 403)

    def test_callback_public_mode_accepts_query_token(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                mineru_api_token="token-123",
                public_deployment_mode="single_tenant_public",
                mineru_callback_token="secret-token",
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("source.pdf", b"%PDF-1.4\nbody", "application/pdf")},
                )
                job_id = create_response.json()["job_id"]
                detail = client.get(f"/api/v1/jobs/{job_id}").json()
                payload, _content = build_callback_payload(
                    batch_id=detail["mineru_batch_id"],
                    data_id=job_id,
                    state="done",
                    full_zip_url="https://mineru.net/result.zip",
                )
                response = client.post(
                    "/api/v1/mineru-callbacks/result?callback_token=secret-token",
                    json=payload,
                )
                self.assertEqual(response.status_code, 200)
                updated = client.get(f"/api/v1/jobs/{job_id}").json()
                self.assertEqual(updated["status"], "completed")

    def test_callback_public_mode_missing_token_config_returns_503(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                public_deployment_mode="single_tenant_public",
                mineru_callback_token="",
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                payload, _content = build_callback_payload(
                    batch_id="batch_x",
                    data_id="job_x",
                    state="done",
                    full_zip_url="https://mineru.net/result.zip",
                )
                response = client.post("/api/v1/mineru-callbacks/result", json=payload)

        self.assertEqual(response.status_code, 503)

    def test_callback_checksum_uses_seed_and_uid_fallback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                mineru_api_token="token-123",
                mineru_callback_url="https://example.com/api/v1/mineru-callbacks/result",
                mineru_uid="mineru-user-1",
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("source.pdf", b"%PDF-1.4\nbody", "application/pdf")},
                )
                job_id = create_response.json()["job_id"]
                detail = client.get(f"/api/v1/jobs/{job_id}").json()
                payload, content = build_callback_payload(
                    batch_id=detail["mineru_batch_id"],
                    data_id=job_id,
                    state="done",
                    full_zip_url="https://mineru.net/result.zip",
                )
                seed = detail["mineru_callback_seed"]
                checksum = hashlib.sha256(f"mineru-user-1{seed}{content}".encode("utf-8")).hexdigest()
                payload["checksum"] = checksum

                response = client.post("/api/v1/mineru-callbacks/result", json=payload)
                self.assertEqual(response.status_code, 200)
                updated = client.get(f"/api/v1/jobs/{job_id}").json()
                self.assertEqual(updated["status"], "completed")

    def test_callback_rejects_invalid_checksum_without_leaving_stage_message(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                mineru_api_token="token-123",
                mineru_callback_url="https://example.com/api/v1/mineru-callbacks/result",
                mineru_uid="mineru-user-1",
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("source.pdf", b"%PDF-1.4\nbody", "application/pdf")},
                )
                job_id = create_response.json()["job_id"]
                detail = client.get(f"/api/v1/jobs/{job_id}").json()
                payload, _content = build_callback_payload(
                    batch_id=detail["mineru_batch_id"],
                    data_id=job_id,
                    state="done",
                    full_zip_url="https://mineru.net/result.zip",
                )
                payload["checksum"] = "bad-checksum"

                response = client.post("/api/v1/mineru-callbacks/result", json=payload)
                updated = client.get(f"/api/v1/jobs/{job_id}").json()

        self.assertEqual(response.status_code, 403)
        self.assertEqual(updated["status"], "parsing")
        self.assertEqual(runtime.repository.list_pending_stage_messages(), [])

    def test_callback_rejects_untrusted_result_url(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), mineru_api_token="token-123")
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("source.pdf", b"%PDF-1.4\nbody", "application/pdf")},
                )
                job_id = create_response.json()["job_id"]
                detail = client.get(f"/api/v1/jobs/{job_id}").json()
                payload, _content = build_callback_payload(
                    batch_id=detail["mineru_batch_id"],
                    data_id=job_id,
                    state="done",
                    full_zip_url="http://evil.example/result.zip",
                )
                response = client.post("/api/v1/mineru-callbacks/result", json=payload)
                updated = client.get(f"/api/v1/jobs/{job_id}").json()

        self.assertEqual(response.status_code, 400)
        self.assertIn("https", response.json()["detail"])
        self.assertEqual(updated["status"], "parsing")
        self.assertIsNone(updated["mineru_result_zip_url"])
        self.assertEqual(runtime.repository.list_pending_stage_messages(), [])

    def test_callback_failed_state_marks_job_failed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), mineru_api_token="token-123")
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("source.pdf", b"%PDF-1.4\nbody", "application/pdf")},
                )
                job_id = create_response.json()["job_id"]
                detail = client.get(f"/api/v1/jobs/{job_id}").json()
                payload, _content = build_callback_payload(
                    batch_id=detail["mineru_batch_id"],
                    data_id=job_id,
                    state="failed",
                )
                response = client.post("/api/v1/mineru-callbacks/result", json=payload)
                self.assertEqual(response.status_code, 200)
                updated = client.get(f"/api/v1/jobs/{job_id}").json()
                self.assertEqual(updated["status"], "failed")
                self.assertEqual(updated["error_code"], "mineru_failed")

    def test_callback_matches_data_id_before_batch_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), mineru_api_token="token-123")
            app = create_app(runtime)
            with TestClient(app) as client:
                first_response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("first.pdf", b"%PDF-1.4\nbody", "application/pdf")},
                )
                second_response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("second.pdf", b"%PDF-1.4\nbody", "application/pdf")},
                )
                first_job_id = first_response.json()["job_id"]
                second_job_id = second_response.json()["job_id"]

                first_detail = client.get(f"/api/v1/jobs/{first_job_id}").json()
                second_detail = client.get(f"/api/v1/jobs/{second_job_id}").json()
                second_job = runtime.repository.get_job(second_job_id)
                self.assertIsNotNone(second_job)
                runtime.repository.update_job(
                    second_job_id,
                    **build_source_pdf_context_patch(second_job, batch_id=first_detail["mineru_batch_id"]),
                )

                payload, _content = build_callback_payload(
                    batch_id=first_detail["mineru_batch_id"],
                    data_id=second_detail["mineru_data_id"],
                    state="done",
                    full_zip_url="https://mineru.net/result.zip",
                )
                response = client.post("/api/v1/mineru-callbacks/result", json=payload)

                self.assertEqual(response.status_code, 200)
                first_updated = client.get(f"/api/v1/jobs/{first_job_id}").json()
                second_updated = client.get(f"/api/v1/jobs/{second_job_id}").json()
                self.assertEqual(first_updated["status"], "parsing")
                self.assertEqual(second_updated["status"], "completed")

    def test_callback_rejects_non_parsing_job_status(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir))
            app = create_app(runtime)
            job = JobRecord(
                id="job_completed_callback",
                source_filename="done.zip",
                status="completed",
                progress=100,
                result_ready=True,
                source_kind="source_pdf",
                source_pdf_context=SourcePdfJobContext(
                    batch_id="batch_completed",
                    data_id="job_completed_callback",
                ),
                completed_at=utc_now(),
            )
            runtime.repository.create_job(job)
            with TestClient(app) as client:
                payload, _content = build_callback_payload(
                    batch_id="batch_completed",
                    data_id="job_completed_callback",
                    state="done",
                    full_zip_url="https://mineru.net/result.zip",
                )
                response = client.post("/api/v1/mineru-callbacks/result", json=payload)

            self.assertEqual(response.status_code, 400)
            self.assertIn("不允许处理 MinerU callback", response.json()["detail"])
            self.assertEqual(runtime.repository.list_pending_stage_messages(), [])

    def test_find_job_for_callback_reads_nested_source_pdf_context(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir))
            job = JobRecord(
                id="job_nested_callback",
                source_filename="source.pdf",
                status="parsing",
                progress=25,
                source_kind="source_pdf",
                lifecycle_status="uploaded",
                execution_status="parsing",
                source_pdf_context=SourcePdfJobContext(
                    batch_id="batch_nested",
                    data_id="job_nested_callback",
                    callback_seed="seed_nested",
                    upstream_status="submitted",
                ),
            )
            runtime.repository.create_job(job)

            by_data_id = runtime.command_service.find_job_for_callback({"data_id": "job_nested_callback"})
            by_batch_id = runtime.command_service.find_job_for_callback({"batch_id": "batch_nested"})

            self.assertEqual(by_data_id.id, "job_nested_callback")
            self.assertEqual(by_batch_id.id, "job_nested_callback")

    def test_replay_pending_replays_pending_and_running_stage_messages_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir))
            job = JobRecord(
                id="job_replay",
                source_filename="source.pdf",
                status="queued",
                progress=10,
                source_kind="source_pdf",
                lifecycle_status="uploaded",
                execution_status="queued",
                source_pdf_context=SourcePdfJobContext(),
            )
            runtime.repository.create_job(job)
            pending = JobStageMessage(
                id="msg_pending",
                job_id=job.id,
                stage="submit_to_mineru",
                trace_id="trace_pending",
                status="pending",
            )
            running = JobStageMessage(
                id="msg_running",
                job_id=job.id,
                stage="process_callback",
                trace_id="trace_running",
                status="running",
            )
            failed = JobStageMessage(
                id="msg_failed",
                job_id=job.id,
                stage="convert_package",
                trace_id="trace_failed",
                status="failed",
            )
            runtime.repository.put_stage_message(pending)
            runtime.repository.put_stage_message(running)
            runtime.repository.put_stage_message(failed)

            dispatched: list[str] = []
            runtime.stage_service.dispatch_message = lambda message_id: dispatched.append(message_id)

            runtime.stage_service.replay_pending()

            self.assertEqual(dispatched, ["msg_pending", "msg_running"])

    def test_enqueue_parsed_result_conversion_downloads_zip_and_completes_docx(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir))
            job = JobRecord(
                id="job_parsed_conversion",
                source_filename="source.pdf",
                status="parsed",
                progress=60,
                source_kind="source_pdf",
                lifecycle_status="parsed",
                execution_status="idle",
                source_pdf_context=SourcePdfJobContext(
                    batch_id="batch_parsed",
                    data_id="job_parsed_conversion",
                    upstream_status="done",
                    result_zip_url="https://mineru.net/result.zip",
                ),
            )
            runtime.repository.create_job(job)

            message = runtime.stage_service.enqueue_parsed_result_conversion(job, trace_id="trace_parsed")
            queued_job = runtime.repository.get_job(job.id)
            self.assertIsNotNone(queued_job)
            self.assertEqual(queued_job.status, "queued")
            self.assertEqual(queued_job.progress, 65)
            self.assertEqual(message.stage, "convert_parsed_result")

            runtime.stage_service.dispatch_message(message.id)

            updated_job = runtime.repository.get_job(job.id)
            self.assertIsNotNone(updated_job)
            self.assertEqual(updated_job.status, "completed")
            self.assertEqual(updated_job.resolved_execution_status(), "idle")
            self.assertIsNone(runtime.repository.get_stage_message(message.id))
            files = runtime.repository.list_files(job.id)
            self.assertEqual([item.file_type for item in files], ["parsed_result_package", "result_docx"])
            job_paths = build_job_paths(runtime.settings.data_path, job.id)
            self.assertTrue(job_paths.parsed_result_package.exists())
            self.assertEqual(job_paths.parsed_result_package.read_bytes(), b"fake-parsed-result-zip")
            self.assertEqual(runtime.stage_service.fake_mineru_client.download_calls[0]["result_url"], "https://mineru.net/result.zip")
            fake_conversion = runtime.stage_service.conversion_entrypoint
            self.assertEqual(fake_conversion.requests[0].package_path, job_paths.parsed_result_package)
            self.assertEqual(job_paths.result_docx.read_bytes(), b"fake-docx")

            event_stages = [item.stage for item in runtime.repository.list_events(job.id)]
            self.assertIn("parsed_result_conversion_started", event_stages)
            self.assertIn("parsed_result_package_recovered", event_stages)
            self.assertIn("job_completed", event_stages)

    def test_convert_parsed_result_fails_when_result_zip_download_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir))
            runtime.stage_service.fake_mineru_client.raise_download_error = True
            job = JobRecord(
                id="job_parsed_download_fail",
                source_filename="source.pdf",
                status="parsed",
                progress=60,
                source_kind="source_pdf",
                lifecycle_status="parsed",
                execution_status="idle",
                source_pdf_context=SourcePdfJobContext(
                    batch_id="batch_parsed",
                    data_id="job_parsed_download_fail",
                    upstream_status="done",
                    result_zip_url="https://mineru.net/result.zip",
                ),
            )
            runtime.repository.create_job(job)

            message = runtime.stage_service.enqueue_parsed_result_conversion(job, trace_id="trace_parsed_fail")
            runtime.stage_service.dispatch_message(message.id)

            updated_job = runtime.repository.get_job(job.id)
            self.assertIsNotNone(updated_job)
            self.assertEqual(updated_job.status, "failed")
            self.assertEqual(updated_job.error_code, "parsed_result_download_failed")
            event_stages = [item.stage for item in runtime.repository.list_events(job.id)]
            self.assertIn("job_failed", event_stages)

    def test_upload_pdf_submits_to_mineru_and_enters_parsing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), mineru_api_token="token-123")
            app = create_app(runtime)
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("source.pdf", b"%PDF-1.4\nbody", "application/pdf")},
                    data={"translation_mode": "direct"},
                )
                self.assertEqual(response.status_code, 201)
                job_id = response.json()["job_id"]

                detail = client.get(f"/api/v1/jobs/{job_id}").json()
                self.assertEqual(detail["status"], "parsing")
                self.assertEqual(detail["source_kind"], "source_pdf")
                self.assertEqual(detail["mineru_batch_id"], "batch_test_001")
                self.assertEqual(detail["mineru_data_id"], job_id)
                self.assertEqual(detail["mineru_status"], "submitted")

                files = client.get(f"/api/v1/jobs/{job_id}/files").json()["files"]
                self.assertEqual(files[0]["file_type"], "source_pdf")

            fake_client = runtime.stage_service.fake_mineru_client
            self.assertEqual(len(fake_client.calls), 1)
            self.assertEqual(fake_client.calls[0]["task_uuids"], [job_id])

    def test_upload_pdf_rejects_when_mineru_token_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(build_test_runtime(Path(temp_dir), mineru_api_token=""))
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("source.pdf", b"%PDF-1.4\nbody", "application/pdf")},
                )

        self.assertEqual(response.status_code, 503)
        self.assertIn("MINERU_API_TOKEN", response.json()["detail"])

    def test_upload_pdf_rejects_invalid_pdf(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(build_test_runtime(Path(temp_dir), mineru_api_token="token-123"))
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("bad.pdf", b"not-pdf", "application/pdf")},
                )

        self.assertEqual(response.status_code, 400)
        self.assertIn("PDF", response.json()["detail"])

    def test_upload_pdf_marks_job_failed_when_mineru_submit_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), mineru_api_token="token-123")
            runtime.stage_service.fake_mineru_client.raise_error = True
            app = create_app(runtime)
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("source.pdf", b"%PDF-1.4\nbody", "application/pdf")},
                )
                self.assertEqual(response.status_code, 201)
                job_id = response.json()["job_id"]

                detail = client.get(f"/api/v1/jobs/{job_id}").json()
                self.assertEqual(detail["status"], "failed")
                self.assertEqual(detail["error_code"], "mineru_submit_failed")
                event_stages = [item["stage"] for item in detail["events"]]
                self.assertIn("mineru_submit_failed", event_stages)
                self.assertIn("job_failed", event_stages)

    def test_retry_requeues_failed_job_without_admin_token(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir))
            runtime.stage_service.conversion_entrypoint.raise_error = True
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs",
                    files={"package": ("mineru-output.zip", make_zip_bytes(), "application/zip")},
                    data={"translation_mode": "direct"},
                )
                self.assertEqual(create_response.status_code, 201)
                job_id = create_response.json()["job_id"]

                failed_detail = client.get(f"/api/v1/jobs/{job_id}").json()
                self.assertEqual(failed_detail["status"], "failed")

                runtime.stage_service.conversion_entrypoint.raise_error = False
                retry_response = client.post(
                    f"/api/v1/jobs/{job_id}/retry",
                    data={"reason": "rerun"},
                )
                self.assertEqual(retry_response.status_code, 200)
                self.assertEqual(retry_response.json()["operation"], "retry")

                detail_response = client.get(f"/api/v1/jobs/{job_id}")
                self.assertEqual(detail_response.status_code, 200)
                self.assertEqual(detail_response.json()["status"], "completed")

    def test_cancel_queued_job_without_admin_token(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir))
            runtime.stage_service.dispatch_message = lambda _message_id: None
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs",
                    files={"package": ("mineru-output.zip", make_zip_bytes(), "application/zip")},
                    data={"translation_mode": "direct"},
                )
                self.assertEqual(create_response.status_code, 201)
                job_id = create_response.json()["job_id"]

                queued_detail = client.get(f"/api/v1/jobs/{job_id}").json()
                self.assertEqual(queued_detail["status"], "queued")

                cancel_response = client.post(
                    f"/api/v1/jobs/{job_id}/cancel",
                    data={"reason": "stop"},
                )
                self.assertEqual(cancel_response.status_code, 200)
                self.assertEqual(cancel_response.json()["status"], "canceled")
                self.assertEqual(runtime.repository.list_pending_stage_messages(), [])

    def test_cleanup_local_files_preserves_registered_artifacts_and_removes_work_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir))
            app = create_app(runtime)
            job = JobRecord(
                id="job_cleanup",
                source_filename="sample.zip",
                status="completed",
                progress=100,
                result_ready=True,
                completed_at=utc_now(),
            )
            runtime.repository.create_job(job)
            job_paths = build_job_paths(runtime.settings.data_path, job.id)
            ensure_job_dirs(job_paths)
            job_paths.source_package.write_bytes(b"zip")
            job_paths.result_docx.write_bytes(b"docx")
            (job_paths.work_dir / "temp.txt").write_text("tmp", encoding="utf-8")
            runtime.repository.upsert_file(job.id, JobFile(file_type="source_package", path="input/source.zip"))
            runtime.repository.upsert_file(job.id, JobFile(file_type="result_docx", path="output/result.docx"))

            with TestClient(app) as client:
                response = client.post(
                    f"/api/v1/jobs/{job.id}/cleanup-local-files",
                    data={"reason": "cleanup"},
                )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertIn(str(job_paths.work_dir), payload["deleted_paths"])
            skipped = {item["path"]: item["reason"] for item in payload["skipped_paths"]}
            self.assertEqual(skipped[str(job_paths.source_package)], "registered_local_artifact")
            self.assertEqual(skipped[str(job_paths.result_docx)], "registered_local_artifact")
            self.assertFalse(job_paths.work_dir.exists())
