from __future__ import annotations

# tests/test_artifact_retention.py: 验证 artifact retention dry-run 按 job 状态和保留期筛选对象。

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.core.file_models import DocumentFileRecord
from app.core.job_models import JobFile, JobRecord
from app.repositories.file_job_repository import FileJobRepository
from app.services.files.retention import DocumentFileRetentionPlanner
from app.services.jobs.artifact_retention import ArtifactRetentionPlanner, ArtifactRetentionPolicy


class ArtifactRetentionTests(TestCase):
    def test_retention_dry_run_selects_local_and_object_artifacts_by_status_and_age(self):
        now = datetime(2026, 5, 28, tzinfo=timezone.utc)
        with TemporaryDirectory() as temp_dir:
            repository = FileJobRepository(Path(temp_dir))
            self._seed_job(
                repository,
                "job_old_completed",
                status="completed",
                completed_at=now - timedelta(days=31),
                object_key="jobs/job_old_completed/output/result.docx",
            )
            self._seed_job(
                repository,
                "job_recent_completed",
                status="completed",
                completed_at=now - timedelta(days=29),
                object_key="jobs/job_recent_completed/output/result.docx",
            )
            self._seed_job(
                repository,
                "job_old_failed",
                status="failed",
                completed_at=now - timedelta(days=13),
                object_key="jobs/job_old_failed/output/result.docx",
            )
            self._seed_job(
                repository,
                "job_old_canceled",
                status="canceled",
                completed_at=now - timedelta(days=8),
                object_key="jobs/job_old_canceled/input/source.pdf",
                file_type="source_pdf",
            )
            self._seed_job(
                repository,
                "job_local_only",
                status="completed",
                completed_at=now - timedelta(days=60),
                object_key=None,
            )

            report = ArtifactRetentionPlanner(repository, repository).build_dry_run(
                ArtifactRetentionPolicy({"completed": 30, "failed": 14, "canceled": 7}),
                now=now,
            )

        self.assertEqual(report.totals["jobs_seen"], 5)
        self.assertEqual(report.totals["eligible_jobs"], 3)
        self.assertEqual(report.totals["candidate_artifacts"], 3)
        self.assertEqual(report.totals["candidate_local_artifacts"], 1)
        self.assertEqual(report.totals["candidate_objects"], 2)
        candidates = {item.job_id: item for item in report.candidates}
        self.assertEqual(candidates["job_local_only"].storage_backend, "local")
        self.assertEqual(candidates["job_local_only"].path, "output/result.docx")
        self.assertIsNone(candidates["job_local_only"].object_key)
        self.assertEqual(candidates["job_local_only"].size_bytes, 10)
        self.assertEqual(candidates["job_local_only"].sha256, "sha256:local")
        self.assertEqual(
            candidates["job_old_canceled"].object_key,
            "jobs/job_old_canceled/input/source.pdf",
        )
        self.assertEqual(
            candidates["job_old_completed"].object_key,
            "jobs/job_old_completed/output/result.docx",
        )

    def _seed_job(
        self,
        repository: FileJobRepository,
        job_id: str,
        *,
        status: str,
        completed_at: datetime,
        object_key: str | None,
        file_type: str = "result_docx",
    ) -> None:
        repository.create_job(
            JobRecord(
                id=job_id,
                source_filename="source.pdf",
                status=status,
                progress=100,
                completed_at=completed_at,
                updated_at=completed_at,
            )
        )
        repository.upsert_file(
            job_id,
            JobFile(
                file_type=file_type,
                path="input/source.pdf" if file_type == "source_pdf" else "output/result.docx",
                storage_backend="object" if object_key else "local",
                object_key=object_key,
                size_bytes=10,
                sha256="sha256:local" if object_key is None else "sha256:object",
            ),
        )


class DocumentFileRetentionTests(TestCase):
    def test_document_file_retention_plan_marks_expired_without_deleting_objects(self):
        now = datetime(2026, 5, 28, tzinfo=timezone.utc)
        with TemporaryDirectory() as temp_dir:
            repository = FileJobRepository(Path(temp_dir))
            old_file = DocumentFileRecord(
                id="file_old",
                tenant_id="tenant_default",
                company_id="company_default",
                job_id="docjob_old",
                file_type="generated_word",
                storage_provider="local_object",
                bucket="local-object",
                object_key="document-jobs/tenant_default/docjob_old/generated_word/result.docx",
                original_filename="result.docx",
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                size_bytes=10,
                status="uploaded",
                expires_at=now - timedelta(seconds=1),
                created_by="operator",
            )
            recent_file = old_file.model_copy(
                update={
                    "id": "file_recent",
                    "job_id": "docjob_recent",
                    "object_key": "document-jobs/tenant_default/docjob_recent/generated_word/result.docx",
                    "expires_at": now + timedelta(days=1),
                }
            )
            repository.create_document_file(old_file)
            repository.create_document_file(recent_file)

            planner = DocumentFileRetentionPlanner(repository, retention_days=90)
            plan = planner.build_plan(now=now)
            marked_plan = planner.mark_expired(now=now)
            old_after_mark = repository.get_document_file("file_old")
            recent_after_mark = repository.get_document_file("file_recent")

        self.assertEqual(plan.totals["files_seen"], 2)
        self.assertEqual(plan.totals["files_with_expires_at"], 2)
        self.assertEqual(plan.totals["candidate_files"], 1)
        self.assertEqual(plan.totals["candidate_local_files"], 1)
        self.assertEqual(plan.candidates[0].file_id, "file_old")
        self.assertEqual(marked_plan.candidates[0].object_key, old_file.object_key)
        self.assertEqual(old_after_mark.status, "expired")
        self.assertEqual(recent_after_mark.status, "uploaded")
