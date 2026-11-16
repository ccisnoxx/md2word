from __future__ import annotations

from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient
from uvicorn import Config

from app.core.config import Settings
from app.domains.document_jobs.recovery import DocumentJobRecoveryService, DocumentJobStartupRecoveryResult
from app.domains.mineru.config import MinerUConfigService
from app.domains.templates.read_service import TemplateReadService
from app.domains.translation.models import TranslationProviderRequest
from app.domains.translation.provider_config import AiProviderConfigService
from app.infrastructure.persistence import build_persistence_adapters
from app.main import build_runtime, create_app
from app.workers import document_tasks
from tests.test_database_job_repository import _FakeMysqlDatabase
from tests.test_fastapi_jobs_backend import build_auth_users_json


class ApiRuntimeBootstrapTests(TestCase):
    def test_app_factory_initializes_fresh_sqlite_before_health(self) -> None:
        with TemporaryDirectory() as directory:
            settings = Settings(
                _env_file=None,
                app_env="test",
                data_dir=str(Path(directory) / "data"),
                jobs_repository_backend="database",
                document_jobs_worker_backend="disabled",
                auth_internal_users_json=build_auth_users_json(),
            )
            self.assertFalse(settings.data_path.exists())
            with patch("app.main.Settings", return_value=settings):
                config = Config("app.main:create_app", factory=True, log_config=None, proxy_headers=False)
                config.load()

            self.assertTrue(settings.jobs_dir.is_dir())
            self.assertTrue(settings.jobs_metadata_database_file.is_file())
            self.assertTrue(settings.term_rules_runtime_yaml_file.is_file())
            self.assertTrue(settings.template_state_file.is_file())
            recovery_started = Event()
            with patch.object(
                DocumentJobRecoveryService, "run_startup_recovery", side_effect=lambda **_kwargs: recovery_started.set(),
            ) as recover:
                with TestClient(config.loaded_app) as client:
                    self.assertEqual(client.get("/api/v1/health/live").status_code, 200)
                    self.assertTrue(recovery_started.wait(timeout=2))
                recover.assert_called_once_with(trace_id="startup")
            runtime = config.loaded_app.state.runtime
            self.assertEqual(runtime.internal_user_repository.count_internal_users(), 2)
            self.assertEqual(len(runtime.acceptance_run_repository.list_acceptance_runs()), 3)

    def test_seed_failure_prevents_uvicorn_factory_from_loading(self) -> None:
        with TemporaryDirectory() as directory:
            settings = Settings(
                _env_file=None,
                app_env="test",
                data_dir=directory,
                jobs_repository_backend="file",
                document_jobs_worker_backend="disabled",
            )
            config = Config("app.main:create_app", factory=True, log_config=None)
            with patch("app.main.Settings", return_value=settings), patch.object(
                TemplateReadService, "bootstrap_manifest_versions", side_effect=ValueError("测试 seed 失败"),
            ), self.assertRaisesRegex(ValueError, "测试 seed 失败"):
                config.load()
            self.assertFalse(config.loaded)

    def test_app_with_prepared_runtime_only_wires_routes(self) -> None:
        with TemporaryDirectory() as directory:
            runtime = build_runtime(Settings(_env_file=None, app_env="test", data_dir=directory))
            with patch("app.main.build_runtime") as build, patch.object(
                TemplateReadService, "bootstrap_manifest_versions",
            ) as bootstrap:
                self.assertIs(create_app(runtime).state.runtime, runtime)
            build.assert_not_called()
            bootstrap.assert_not_called()


class WorkerTemplateBootstrapTests(TestCase):
    def setUp(self) -> None:
        document_tasks._task_runtime.cache_clear()
        self.addCleanup(document_tasks._task_runtime.cache_clear)

    def test_celery_entry_uses_runtime_without_seed_or_default_resolution(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = Settings(
                _env_file=None,
                app_env="test",
                data_dir=str(Path(temp_dir) / "data"),
                jobs_repository_backend="file",
                document_jobs_worker_backend="disabled",
            )
            with patch.object(
                TemplateReadService, "bootstrap_manifest_versions", side_effect=FileNotFoundError("测试 seed 缺失"),
            ), patch.object(
                TemplateReadService, "get_default_template_id", side_effect=AssertionError("Worker 读取了全局默认"),
            ), patch(
                "app.domains.document_jobs.execution.DocumentJobExecutionService.execute_job", return_value=None,
            ) as execute, patch.object(
                document_tasks, "build_runtime", side_effect=lambda **kwargs: build_runtime(settings, **kwargs),
            ):
                self.assertIsNone(document_tasks.run_document_job.run("docjob_bound", trace_id="trace"))
                execute.assert_called_once_with("docjob_bound", trace_id="trace")
                with self.assertRaises(FileNotFoundError):
                    build_runtime(settings, initialize=True)

    def test_worker_assembly_does_not_create_storage_or_write_existing_metadata(self) -> None:
        for backend in ("file", "database", "mysql"):
            with self.subTest(backend=backend), TemporaryDirectory() as directory:
                document_tasks._task_runtime.cache_clear()
                settings = Settings(
                    _env_file=None,
                    app_env="test",
                    data_dir=str(Path(directory) / "data"),
                    jobs_repository_backend=backend,
                    document_jobs_worker_backend="disabled",
                    auth_internal_users_json=build_auth_users_json(),
                )
                fake_mysql = _FakeMysqlDatabase()
                with patch(
                    "app.main.build_persistence_adapters",
                    partial(build_persistence_adapters, mysql_connect_factory=fake_mysql.connect),
                ), patch.object(document_tasks, "build_runtime", partial(build_runtime, settings)):
                    document_tasks._task_runtime(101)
                    self.assertFalse(settings.data_path.exists())
                    self.assertEqual(fake_mysql.executed_sql, [])

                    build_runtime(settings, initialize=True)
                    if backend == "mysql":
                        self.assertTrue(fake_mysql.created_tables)
                        self.assertEqual(len(fake_mysql.internal_users), 2)
                        self.assertTrue(fake_mysql.translation_terms)
                        self.assertTrue(fake_mysql.term_rules)
                        self.assertIsNotNone(fake_mysql.template_catalog_default)
                        self.assertIn(("translation_profile", "electronics-ru2zh"), fake_mysql.resource_default_versions)
                    before = {
                        path: path.read_bytes() if path.is_file() else None
                        for path in settings.data_path.rglob("*")
                    }
                    fake_mysql.executed_sql.clear()

                    document_tasks._task_runtime(102)
                    self.assertEqual({
                        path: path.read_bytes() if path.is_file() else None
                        for path in settings.data_path.rglob("*")
                    }, before)
                    self.assertEqual(fake_mysql.executed_sql, [])

    def test_tasks_share_successful_runtime_and_rebuild_after_pid_change(self) -> None:
        settings = Settings(_env_file=None, app_env="test", document_jobs_worker_backend="disabled")
        first_execution = SimpleNamespace(
            execute_job=lambda *_args, **_kwargs: None,
            translation_batches=SimpleNamespace(execute_translation_batch=lambda *_args, **_kwargs: None),
        )
        first_runtime = SimpleNamespace(settings=settings, document_job_execution_service=first_execution)
        second_runtime = SimpleNamespace(settings=settings, document_job_execution_service=first_execution)
        with (
            patch.object(document_tasks, "getpid", side_effect=[101, 101, 101, 102]),
            patch.object(document_tasks, "build_runtime", side_effect=[
                RuntimeError("测试构造失败"), first_runtime, second_runtime,
            ]) as build,
        ):
            self.assertEqual(document_tasks.ping.run(), "pong")
            build.assert_not_called()
            with self.assertRaisesRegex(RuntimeError, "测试构造失败"):
                document_tasks.run_document_job.run("job")
            document_tasks.run_document_job.run("job")
            document_tasks.run_document_translation_batch.run("batch")
            self.assertEqual(build.call_count, 2)
            document_tasks.run_document_translation_batch.run("batch")
            self.assertEqual(build.call_count, 3)

    def test_polling_recovery_keeps_task_runtime_lazy_and_skips_callback_mode(self) -> None:
        with TemporaryDirectory() as directory:
            settings = Settings(
                _env_file=None,
                app_env="test",
                data_dir=str(Path(directory) / "data"),
                mineru_callback_url="",
                document_jobs_worker_backend="disabled",
            )
            callback_settings = settings.model_copy(update={
                "mineru_callback_url": "https://example.test/callback",
                "log_format": "json",
            })
            with patch.object(document_tasks, "Settings", return_value=callback_settings), patch.object(
                document_tasks, "build_runtime",
            ) as build, patch.object(document_tasks, "configure_logging") as configure:
                document_tasks.recover_mineru_polling_jobs()
                build.assert_not_called()
                configure.assert_called_once_with("test", "json")

            with patch.object(document_tasks, "Settings", return_value=settings), patch.object(
                document_tasks, "build_runtime", wraps=build_runtime,
            ) as build, patch.object(
                DocumentJobRecoveryService,
                "run_startup_recovery",
                return_value=DocumentJobStartupRecoveryResult(2, 1, 1, 0, 0),
            ) as recover:
                document_tasks.recover_mineru_polling_jobs()
                build.assert_called_once_with(settings)
                recover.assert_called_once_with(trace_id="worker_startup", polling_only=True)
                self.assertFalse(settings.data_path.exists())
                self.assertEqual(document_tasks._task_runtime.cache_info().currsize, 0)

    def test_same_runtime_reads_new_manifest_and_rotated_provider_configuration(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "templates.yaml"
            manifest.write_text("templates: [{id: sample, name: 示例, template_path: sample.docx}]\n", encoding="utf-8")
            settings = Settings(
                _env_file=None,
                app_env="test",
                data_dir=str(root / "data"),
                jobs_repository_backend="file",
                templates_manifest_path=str(manifest),
                mineru_api_token="fixture-mineru-start",
                mineru_uid="uid-start",
                translation_provider_backend="openai_compatible",
                openai_api_key="fixture-ai-start",
                openai_model="model-start",
            )
            with patch.object(document_tasks, "build_runtime", return_value=build_runtime(settings)):
                runtime = document_tasks._task_runtime(101)
                reader = runtime.template_read_service
                self.assertEqual(reader.resolve_template_render_state("sample", None)[1], 1)

                request = TranslationProviderRequest("en2zh", "en", "zh", ())
                with patch("app.domains.document_jobs.mineru_execution.MinerUClient") as mineru, patch(
                    "openai.OpenAI",
                ) as ai:
                    complete = ai.return_value.chat.completions.create
                    complete.return_value = SimpleNamespace(
                        choices=[SimpleNamespace(
                            message=SimpleNamespace(content='{"items":[]}'), finish_reason="stop",
                        )],
                    )
                    runtime.document_job_execution_service.mineru.build_mineru_client()
                    runtime.translation_provider.translate(request)
                    MinerUConfigService(settings).update_credentials(
                        api_token="fixture-mineru-new", uid="uid-new", updated_by="test",
                    )
                    AiProviderConfigService(settings).update_config(
                        backend="openai_compatible", base_url=None, model="model-new",
                        timeout_seconds=None, max_output_tokens=None, api_key="fixture-ai-new",
                        clear_api_key=False, api_key_supplied=True, updated_by="test",
                    )
                    self.assertIs(document_tasks._task_runtime(101), runtime)
                    runtime.document_job_execution_service.mineru.build_mineru_client()
                    runtime.translation_provider.translate(request)
                    self.assertEqual([call.kwargs["user_token"] for call in mineru.call_args_list], [
                        "uid-start", "uid-new",
                    ])
                    self.assertEqual([call.kwargs["api_token"] for call in mineru.call_args_list], [
                        "fixture-mineru-start", "fixture-mineru-new",
                    ])
                    self.assertEqual([call.kwargs["api_key"] for call in ai.call_args_list], [
                        "fixture-ai-start", "fixture-ai-new",
                    ])
                    self.assertEqual([call.kwargs["model"] for call in complete.call_args_list], [
                        "model-start", "model-new",
                    ])
                manifest.write_text(
                    "templates: [{id: sample, name: 示例, template_path: sample.docx, version: 2}]\n",
                    encoding="utf-8",
                )
                self.assertEqual(reader.resolve_template_render_state("sample", None)[1], 2)
                self.assertEqual(reader.resolve_template_render_state("sample", 1)[1], 1)
