from __future__ import annotations

# tests/test_artifact_retention.py: 验证 artifact retention dry-run 按 job 状态和保留期筛选对象。

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.core.job_models import JobFile, JobRecord
from app.repositories.file_job_repository import FileJobRepository
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
