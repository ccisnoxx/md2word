from __future__ import annotations

# tests/test_job_artifact_contract.py: 验证 jobs artifact 合同，尤其是 parsed_result_package 的 alias/path 约定。

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.core.job_models import JobRecord
from app.core.job_paths import build_job_paths
from app.services.jobs.artifacts import JobArtifactService


class JobArtifactContractTests(TestCase):
    def test_parsed_result_package_contract_is_stable(self):
        with TemporaryDirectory() as temp_dir:
            paths = build_job_paths(Path(temp_dir), "job_artifact_contract")
            service = JobArtifactService()
            job = JobRecord(
                id="job_artifact_contract",
                source_filename="source.pdf",
                status="parsed",
                progress=60,
                source_kind="source_pdf",
                lifecycle_status="parsed",
                execution_status="idle",
            )

            file = service.build_registered_file("parsed_result_package", paths)

        self.assertEqual(file.file_type, "parsed_result_package")
        self.assertEqual(file.path, "input/parsed-result.zip")
        self.assertEqual(service.alias_for_file(file), "parsed-result-package")
        self.assertEqual(service.media_type_for_file(file), "application/zip")
        self.assertEqual(service.build_download_filename(job, file), "job_artifact_contract-parsed-result.zip")
