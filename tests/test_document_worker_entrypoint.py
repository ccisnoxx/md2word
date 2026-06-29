from __future__ import annotations

from unittest import TestCase

from app.core.config import Settings
from scripts.dev.run_document_worker import build_worker_main_args


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
