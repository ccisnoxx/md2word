from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

from app.core.config import Settings
from scripts.dev.run_document_worker import build_worker_main_args, check_poppler_tools, main


class DocumentWorkerEntrypointTests(TestCase):
    def test_worker_consumes_document_and_translation_batch_queues(self):
        settings = Settings(
            _env_file=None,
            document_jobs_celery_queue="document-jobs",
            document_jobs_translation_batch_celery_queue="document-translation-batches",
        )

        args = build_worker_main_args(settings)

        self.assertEqual(args, ["worker", "--loglevel=INFO", "-Q", "document-jobs,document-translation-batches"])

    def test_worker_deduplicates_when_queues_share_one_physical_queue(self):
        settings = Settings(
            _env_file=None,
            document_jobs_celery_queue="document-jobs",
            document_jobs_translation_batch_celery_queue="document-jobs",
        )

        args = build_worker_main_args(settings)

        self.assertEqual(args, ["worker", "--loglevel=INFO", "-Q", "document-jobs"])

    def test_worker_fails_fast_when_translation_batch_queue_is_missing(self):
        settings = Settings(
            _env_file=None,
            document_jobs_celery_queue="document-jobs",
            document_jobs_translation_batch_celery_queue="",
        )

        with self.assertRaisesRegex(RuntimeError, "DOCUMENT_JOBS_TRANSLATION_BATCH_CELERY_QUEUE"):
            build_worker_main_args(settings)

    def test_production_worker_does_not_start_without_poppler(self):
        settings = Settings(_env_file=None, app_env="production")
        with patch("scripts.dev.run_document_worker.poppler_tools_available", return_value=False), \
                patch("scripts.dev.run_document_worker.Settings", return_value=settings), \
                patch("scripts.dev.run_document_worker.create_celery_app") as create_celery_app, \
                self.assertRaisesRegex(RuntimeError, "Poppler"):
            main()
        create_celery_app.assert_not_called()

    def test_development_worker_only_warns_without_poppler(self):
        with patch("scripts.dev.run_document_worker.poppler_tools_available", return_value=False), \
                self.assertLogs("scripts.dev.run_document_worker", level="WARNING"):
            check_poppler_tools(Settings(_env_file=None, app_env="dev"))
