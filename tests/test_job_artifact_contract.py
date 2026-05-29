from __future__ import annotations

# tests/test_job_artifact_contract.py: 验证 jobs artifact 合同、alias、path 和下载响应形状。

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.core.job_models import JobFile, JobRecord
from app.core.job_paths import build_job_paths
from app.services.jobs.artifact_storage import DownloadArtifact, LocalArtifactStorageAdapter
from app.services.jobs.artifacts import JobArtifactService


class JobArtifactContractTests(TestCase):
    def test_artifact_alias_file_type_media_type_and_paths_are_stable(self):
        with TemporaryDirectory() as temp_dir:
            paths = build_job_paths(Path(temp_dir), "job_artifact_contract")
            service = JobArtifactService()
            storage = LocalArtifactStorageAdapter(service)
            paths.input_dir.mkdir(parents=True, exist_ok=True)
            paths.output_dir.mkdir(parents=True, exist_ok=True)
            paths.translation_dir.mkdir(parents=True, exist_ok=True)
            paths.source_package.write_bytes(b"zip")
            paths.source_pdf.write_bytes(b"%PDF-1.4\nbody")
            paths.parsed_result_package.write_bytes(b"parsed")
            paths.translation_request.write_bytes(b"{}")
            paths.result_docx.write_bytes(b"docx")
            job = JobRecord(
                id="job_artifact_contract",
                source_filename="source.pdf",
                status="completed",
                progress=100,
                source_kind="source_pdf",
                lifecycle_status="completed",
                execution_status="idle",
                result_ready=True,
            )

            cases = [
                (
                    "source_package",
                    "source-package",
                    "input/source.zip",
                    "application/zip",
                    "source.pdf",
                ),
                (
                    "source_pdf",
                    "source-pdf",
                    "input/source.pdf",
                    "application/pdf",
                    "source.pdf",
                ),
                (
                    "parsed_result_package",
                    "parsed-result-package",
                    "input/parsed-result.zip",
                    "application/zip",
                    "job_artifact_contract-parsed-result.zip",
                ),
                (
                    "translation_request",
                    "translation-request",
                    "translation/request.json",
                    "application/json",
                    "job_artifact_contract-translation-request.json",
                ),
                (
                    "result_docx",
                    "result",
                    "output/result.docx",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "source.docx",
                ),
            ]

            for file_type, alias, logical_path, media_type, filename in cases:
                with self.subTest(file_type=file_type):
                    file = storage.build_registered_file(file_type, paths)

                    self.assertEqual(file.file_type, file_type)
                    self.assertEqual(file.path, logical_path)
                    self.assertEqual(service.alias_for_file(file), alias)
                    self.assertEqual(service.spec_for_alias(alias).file_type, file_type)
                    self.assertEqual(service.media_type_for_file(file), media_type)
                    self.assertEqual(service.build_download_filename(job, file), filename)
                    self.assertEqual(file.size_bytes, getattr(paths, service.spec_for_file_type(file_type).path_attr).stat().st_size)
                    self.assertTrue((file.sha256 or "").startswith("sha256:"))

    def test_parsed_result_package_contract_is_stable(self):
        with TemporaryDirectory() as temp_dir:
            paths = build_job_paths(Path(temp_dir), "job_artifact_contract")
            service = JobArtifactService()
            storage = LocalArtifactStorageAdapter(service)
            paths.input_dir.mkdir(parents=True, exist_ok=True)
            paths.parsed_result_package.write_bytes(b"parsed")
            job = JobRecord(
                id="job_artifact_contract",
                source_filename="source.pdf",
                status="parsed",
                progress=60,
                source_kind="source_pdf",
                lifecycle_status="parsed",
                execution_status="idle",
            )

            file = storage.build_registered_file("parsed_result_package", paths)
            resolved_path = storage.resolve_download_path(paths, file)
            download = storage.resolve_download(paths, file)
            expected_path = paths.parsed_result_package.resolve()

        self.assertEqual(file.file_type, "parsed_result_package")
        self.assertEqual(file.path, "input/parsed-result.zip")
        self.assertEqual(file.size_bytes, 6)
        self.assertEqual(file.sha256, f"sha256:{hashlib.sha256(b'parsed').hexdigest()}")
        self.assertEqual(resolved_path, expected_path)
        self.assertEqual(download.kind, "local_path")
        self.assertEqual(download.path, expected_path)
        self.assertEqual(service.alias_for_file(file), "parsed-result-package")
        self.assertEqual(service.media_type_for_file(file), "application/zip")
        self.assertEqual(service.build_download_filename(job, file), "job_artifact_contract-parsed-result.zip")

    def test_legacy_job_file_without_fingerprint_remains_valid(self):
        file = JobFile(file_type="result_docx", path="output/result.docx")

        self.assertIsNone(file.size_bytes)
        self.assertIsNone(file.sha256)

    def test_download_artifact_contract_supports_stream_and_redirect_shapes(self):
        stream_download = DownloadArtifact.stream([b"chunk"])
        redirect_download = DownloadArtifact.redirect("https://storage.example/jobs/result.docx")

        self.assertEqual(stream_download.kind, "stream")
        self.assertEqual(list(stream_download.content or []), [b"chunk"])
        self.assertEqual(redirect_download.kind, "redirect")
        self.assertEqual(redirect_download.redirect_url, "https://storage.example/jobs/result.docx")
