from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from app.core.config import Settings
from app.domains.document_jobs.execution import DocumentJobExecutionService
from app.domains.document_jobs.recovery import DocumentJobRecoveryService, DocumentJobStartupRecoveryResult
from app.domains.document_jobs.translation_execution import TranslationBatchExecution
from app.domains.templates.read_service import TemplateReadService
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend
from app.main import build_runtime
from app.workers import document_tasks


class WorkerBootstrapTests(TestCase):
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
                    build_runtime(settings)

    def test_celery_entries_skip_mysql_schema_users_and_seed_initialization(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = Settings(
                _env_file=None,
                app_env="test",
                data_dir=temp_dir,
                jobs_repository_backend="mysql",
                document_jobs_worker_backend="disabled",
                mineru_callback_url="",
            )
            batch_payload = {"id": "batch_bound"}
            batch = Mock(model_dump=Mock(return_value=batch_payload))
            empty_recovery = DocumentJobStartupRecoveryResult(
                scanned_jobs=0, eligible_jobs=0, queued_jobs=0, ignored_callback_messages=0, failed_jobs=0,
            )
            with (
                patch.object(
                    MysqlPersistenceBackend,
                    "_build_pymysql_connection",
                    side_effect=AssertionError("Worker 装配访问了 MySQL"),
                ),
                patch("app.main.run_startup_bootstrap", side_effect=AssertionError("Worker 装配执行了种子初始化")),
                patch.object(DocumentJobExecutionService, "execute_job", return_value=None) as execute,
                patch.object(TranslationBatchExecution, "execute_translation_batch", return_value=batch) as translate,
                patch.object(DocumentJobRecoveryService, "run_startup_recovery", return_value=empty_recovery) as recover,
                patch.object(document_tasks, "build_runtime", side_effect=lambda **kwargs: build_runtime(settings, **kwargs)),
            ):
                self.assertIsNone(document_tasks.run_document_job.run("docjob_bound", trace_id="job_trace"))
                self.assertEqual(
                    document_tasks.run_document_translation_batch.run("batch_bound", trace_id="batch_trace"),
                    batch_payload,
                )
                document_tasks.recover_mineru_polling_jobs()

            execute.assert_called_once_with("docjob_bound", trace_id="job_trace")
            translate.assert_called_once_with("batch_bound", trace_id="batch_trace")
            batch.model_dump.assert_called_once_with(mode="json")
            recover.assert_called_once_with(trace_id="worker_startup", polling_only=True)

    def test_worker_runtime_leaves_empty_sqlite_database_for_api_to_initialize(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = Settings(
                _env_file=None,
                app_env="test",
                data_dir=temp_dir,
                jobs_repository_backend="database",
                jobs_metadata_database_path=str(Path(temp_dir) / "metadata.sqlite3"),
                document_jobs_worker_backend="disabled",
            )
            build_runtime(settings, bootstrap=False)
            self.assertFalse(settings.jobs_metadata_database_file.exists())

            build_runtime(settings)
            self.assertTrue(settings.jobs_metadata_database_file.is_file())
