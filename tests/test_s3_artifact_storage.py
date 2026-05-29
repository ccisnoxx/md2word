from __future__ import annotations

# tests/test_s3_artifact_storage.py: 验证 S3-compatible artifact adapter 的上传、redirect 和 stream 合同。

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.core.job_models import JobFile
from app.core.job_paths import build_job_paths
from app.services.jobs.artifacts import JobArtifactService
from app.services.jobs.object_artifact_storage import S3ArtifactStorageAdapter


class FakeS3Body:
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks
        self.closed = False

    def read(self, chunk_size: int) -> bytes:
        if not self.chunks:
            return b""
        return self.chunks.pop(0)

    def close(self) -> None:
        self.closed = True


class FakeS3Client:
    def __init__(self) -> None:
        self.uploads: list[dict] = []
        self.presign_calls: list[dict] = []
        self.objects: dict[str, bytes] = {}

    def upload_file(self, filename: str, bucket: str, key: str, ExtraArgs: dict | None = None) -> None:
        self.uploads.append(
            {
                "filename": filename,
                "bucket": bucket,
                "key": key,
                "extra_args": ExtraArgs or {},
            }
        )

    def generate_presigned_url(self, operation: str, *, Params: dict, ExpiresIn: int) -> str:
        self.presign_calls.append({"operation": operation, "params": Params, "expires_in": ExpiresIn})
        return f"https://signed.example/{Params['Bucket']}/{Params['Key']}?expires={ExpiresIn}"

    def get_object(self, *, Bucket: str, Key: str) -> dict:
        return {"Body": FakeS3Body([self.objects[Key]])}


class S3ArtifactStorageTests(TestCase):
    def test_s3_adapter_uploads_local_artifact_and_returns_presigned_redirect(self):
        with TemporaryDirectory() as temp_dir:
            paths = build_job_paths(Path(temp_dir), "job_s3_redirect")
            paths.output_dir.mkdir(parents=True, exist_ok=True)
            paths.result_docx.write_bytes(b"docx")
            client = FakeS3Client()
            storage = S3ArtifactStorageAdapter(
                JobArtifactService(),
                bucket="md2word-artifacts",
                key_prefix="tenant-a",
                public_base_url="https://public.example/artifacts",
                presign_expires_seconds=600,
                client=client,
            )

            file = storage.build_registered_file("result_docx", paths)
            download = storage.resolve_download(paths, file)

        self.assertEqual(file.storage_backend, "object")
        self.assertEqual(file.object_key, "tenant-a/jobs/job_s3_redirect/output/result.docx")
        self.assertEqual(file.public_url, "https://public.example/artifacts/tenant-a/jobs/job_s3_redirect/output/result.docx")
        self.assertEqual(client.uploads[0]["bucket"], "md2word-artifacts")
        self.assertEqual(client.uploads[0]["key"], "tenant-a/jobs/job_s3_redirect/output/result.docx")
        self.assertEqual(
            client.uploads[0]["extra_args"]["ContentType"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        self.assertEqual(download.kind, "redirect")
        self.assertEqual(
            download.redirect_url,
            "https://signed.example/md2word-artifacts/tenant-a/jobs/job_s3_redirect/output/result.docx?expires=600",
        )
        self.assertEqual(client.presign_calls[0]["operation"], "get_object")

    def test_s3_adapter_streams_object_body_when_configured(self):
        client = FakeS3Client()
        client.objects["jobs/job_s3_stream/output/result.docx"] = b"stream-docx"
        storage = S3ArtifactStorageAdapter(
            JobArtifactService(),
            bucket="md2word-artifacts",
            download_mode="stream",
            client=client,
        )
        file = JobFile(
            file_type="result_docx",
            path="output/result.docx",
            storage_backend="object",
            object_key="jobs/job_s3_stream/output/result.docx",
        )
        with TemporaryDirectory() as temp_dir:
            paths = build_job_paths(Path(temp_dir), "job_s3_stream")
            download = storage.resolve_download(paths, file)

        self.assertEqual(download.kind, "stream")
        self.assertEqual(b"".join(download.content or []), b"stream-docx")
