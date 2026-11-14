from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from app.core.config import Settings
from app.domains.templates.read_service import TemplateReadService
from app.main import build_runtime
from app.workers import document_tasks


class WorkerTemplateBootstrapTests(TestCase):
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
