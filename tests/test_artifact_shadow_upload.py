from __future__ import annotations

# tests/test_artifact_shadow_upload.py: 验证 artifact shadow upload、object_key 回填和 local fallback。

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.domains.jobs.models import JobFile, JobRecord, utc_now
from app.domains.jobs.paths import build_job_paths
from app.infrastructure.persistence import build_file_persistence_adapters
from app.domains.jobs.artifacts import JobArtifactService
from app.domains.jobs.object_artifact_storage import ObjectArtifactStorageAdapter
from scripts.ops.shadow_upload_artifacts_to_object_storage import shadow_upload_artifacts_to_object_storage


class ArtifactShadowUploadTests(TestCase):
    def test_shadow_upload_updates_job_files_and_is_idempotent(self):
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            object_root = Path(temp_dir) / "objects"
            adapters = build_file_persistence_adapters(data_dir)
            job = JobRecord(
                id="job_shadow_artifacts",
                source_filename="source.pdf",
                status="completed",
                progress=100,
                result_ready=True,
                source_kind="source_pdf",
                completed_at=utc_now(),
            )
            adapters.job_repository.create_job(job)
            paths = build_job_paths(data_dir, job.id)
            paths.source_pdf.write_bytes(b"%PDF-1.4\nbody")
            paths.parsed_result_package.write_bytes(b"parsed")
            paths.result_docx.write_bytes(b"docx")
            adapters.job_file_repository.upsert_file(job.id, JobFile(file_type="source_pdf", path="input/source.pdf"))
            adapters.job_file_repository.upsert_file(job.id, JobFile(file_type="parsed_result_package", path="input/parsed-result.zip"))
            adapters.job_file_repository.upsert_file(job.id, JobFile(file_type="result_docx", path="output/result.docx"))

            first_report = shadow_upload_artifacts_to_object_storage(data_dir, object_root, repository=adapters)
            second_report = shadow_upload_artifacts_to_object_storage(data_dir, object_root, repository=adapters)
            files = {item.file_type: item for item in adapters.job_file_repository.list_files(job.id)}
            object_bytes = {
                "source_pdf": (object_root / "jobs/job_shadow_artifacts/input/source.pdf").read_bytes(),
                "parsed_result_package": (object_root / "jobs/job_shadow_artifacts/input/parsed-result.zip").read_bytes(),
                "result_docx": (object_root / "jobs/job_shadow_artifacts/output/result.docx").read_bytes(),
            }

        self.assertTrue(first_report.ok)
        self.assertTrue(second_report.ok)
        self.assertEqual(first_report.totals["uploaded_artifacts"], 3)
        self.assertEqual(second_report.totals["uploaded_artifacts"], 3)
        self.assertEqual(set(files), {"source_pdf", "parsed_result_package", "result_docx"})
        self.assertEqual(files["source_pdf"].path, "input/source.pdf")
        self.assertEqual(files["source_pdf"].storage_backend, "object")
        self.assertEqual(files["source_pdf"].object_key, "jobs/job_shadow_artifacts/input/source.pdf")
        self.assertEqual(files["parsed_result_package"].object_key, "jobs/job_shadow_artifacts/input/parsed-result.zip")
        self.assertEqual(files["result_docx"].object_key, "jobs/job_shadow_artifacts/output/result.docx")
        self.assertEqual(object_bytes["source_pdf"], b"%PDF-1.4\nbody")
        self.assertEqual(object_bytes["parsed_result_package"], b"parsed")
        self.assertEqual(object_bytes["result_docx"], b"docx")

    def test_object_adapter_download_prefers_object_and_keeps_local_fallback(self):
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            object_root = Path(temp_dir) / "objects"
            paths = build_job_paths(data_dir, "job_object_download")
            paths.output_dir.mkdir(parents=True, exist_ok=True)
            paths.result_docx.write_bytes(b"local-docx")
            storage = ObjectArtifactStorageAdapter(JobArtifactService(), object_root)
            file = storage.shadow_upload_registered_file(
                "job_object_download",
                paths,
                JobFile(file_type="result_docx", path="output/result.docx"),
            )
            object_path = (object_root / "jobs/job_object_download/output/result.docx").resolve()
            local_path = paths.result_docx.resolve()

            object_download = storage.resolve_download(paths, file)
            object_path.unlink()
            fallback_download = storage.resolve_download(paths, file)
            paths.result_docx.unlink()

            with self.assertRaises(FileNotFoundError):
                storage.resolve_download(paths, file)

        self.assertEqual(object_download.kind, "local_path")
        self.assertEqual(object_download.path, object_path)
        self.assertEqual(fallback_download.kind, "local_path")
        self.assertEqual(fallback_download.path, local_path)
