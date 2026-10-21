"""验证生成件按登记身份隔离字节，并保持历史路径和上传合同。"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from app.core.config import Settings
from app.core.errors import ApiError
from app.domains.files.models import DocumentFileRecord, DocumentFileStorageProvider, DocumentFileType
from app.domains.files.service import FileUploadService
from app.infrastructure.persistence.file.backend import FilePersistenceBackend
from app.infrastructure.persistence.file.files import FileDocumentFileRepository
from app.services.auth.models import AuthenticatedUser


class FakeS3Client:
    """保存真实 service 写入的对象，按 bucket/key 提供独立读回。"""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, ContentType: str) -> dict:
        self.objects[(Bucket, Key)] = bytes(Body)
        return {"ETag": f'"{hashlib.sha256(Body).hexdigest()}"'}

    def get_object(self, *, Bucket: str, Key: str) -> dict:
        return {"Body": BytesIO(self.objects[(Bucket, Key)])}

    def generate_presigned_url(self, operation: str, *, Params: dict, ExpiresIn: int) -> str:
        return f"https://s3.example/{Params['Bucket']}/{Params['Key']}?expires={ExpiresIn}"


class GeneratedArtifactIdentityTests(TestCase):
    @contextmanager
    def _storage(
        self,
        provider: DocumentFileStorageProvider,
        *,
        prefix: str = "",
    ) -> Iterator[tuple[FileUploadService, FakeS3Client]]:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = Settings(
                _env_file=None,
                data_dir=str(root / "data"),
                jobs_artifact_storage_backend=provider,
                jobs_artifact_object_store_path=str(root / "objects"),
                jobs_artifact_s3_bucket="artifact-test-bucket",
                jobs_artifact_s3_key_prefix=prefix,
            )
            repository = FileDocumentFileRepository(FilePersistenceBackend(root / "metadata"))
            service = FileUploadService(settings, repository)
            client = FakeS3Client()
            with patch.object(service, "_s3_client", return_value=client):
                yield service, client

    def _assert_stored_content(
        self,
        service: FileUploadService,
        record: DocumentFileRecord,
        content: bytes,
    ) -> None:
        stored = service.repository.get_document_file(record.id)
        self.assertIsNotNone(stored)
        self.assertEqual(service.read_file_content(stored), content)
        self.assertEqual(stored.checksum_sha256, f"sha256:{hashlib.sha256(content).hexdigest()}")
        self.assertEqual(stored.size_bytes, len(content))

    def _assert_repeated_generated_content_isolated(self, provider: DocumentFileStorageProvider) -> None:
        artifacts: tuple[tuple[DocumentFileType, str], ...] = (
            ("document_ir", "document_ir_source_v2.json"),
            ("translation_batch_result", "batch_same.json"),
            ("document_ir", "document_ir_v2.json"),
            ("generated_word", "result.docx"),
            ("ai_call_log", "call_same.json"),
            ("ai_debug_archive", "call_same_debug.json"),
        )
        with self._storage(provider, prefix=" /archive/tr-403/ ") as (service, _client):
            for file_type, filename in artifacts:
                records = []
                for revision in ("first", "second", "replayed"):
                    content = f"{filename}:{revision}".encode("utf-8")
                    record = service.register_generated_content(
                        tenant_id="tenant_default",
                        company_id="company_default",
                        job_id="job_identity",
                        created_by="operator",
                        file_type=file_type,
                        filename=filename,
                        mime_type="application/octet-stream",
                        content=content,
                        metadata={"generation": 1, "attempt": 1},
                    )
                    records.append((record, content))

                for record, content in records:
                    self._assert_stored_content(service, record, content)
                    self.assertEqual(record.original_filename, filename)
                    self.assertEqual(record.metadata, {"generation": 1, "attempt": 1})
                    logical_key = (
                        f"document-jobs/tenant_default/job_identity/{file_type}/{record.id}/{filename}"
                    )
                    expected_key = f"archive/tr-403/{logical_key}" if provider == "s3" else logical_key
                    self.assertEqual(record.object_key, expected_key)
                self.assertEqual(len({record.object_key for record, _content in records}), len(records))

    def test_local_file_repeated_generated_artifacts_preserve_each_content(self) -> None:
        self._assert_repeated_generated_content_isolated("local_file")

    def test_local_object_repeated_generated_artifacts_preserve_each_content(self) -> None:
        self._assert_repeated_generated_content_isolated("local_object")

    def test_fake_s3_repeated_generated_artifacts_preserve_each_content_and_prefix(self) -> None:
        self._assert_repeated_generated_content_isolated("s3")

    def test_historical_fixed_keys_remain_readable_after_new_registration(self) -> None:
        for provider in ("local_file", "local_object", "s3"):
            with self.subTest(provider=provider), self._storage(provider, prefix="archive/tr-403") as (service, client):
                content = b"historical-word-content"
                logical_key = "document-jobs/tenant_default/job_identity/generated_word/result.docx"
                key = f"archive/tr-403/{logical_key}" if provider == "s3" else logical_key
                old_record = DocumentFileRecord(
                    id="file_historical",
                    tenant_id="tenant_default",
                    company_id="company_default",
                    job_id="job_identity",
                    created_by="operator",
                    file_type="generated_word",
                    storage_provider=provider,
                    bucket="artifact-test-bucket" if provider == "s3" else provider.replace("_", "-"),
                    object_key=key,
                    original_filename="result.docx",
                    mime_type="application/octet-stream",
                    size_bytes=len(content),
                    checksum_sha256=f"sha256:{hashlib.sha256(content).hexdigest()}",
                    status="uploaded",
                )
                if provider == "s3":
                    client.objects[(old_record.bucket, key)] = content
                else:
                    path = service.resolve_local_object_path(key)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(content)
                service.repository.create_document_file(old_record)
                before = old_record.model_dump(mode="json")

                new_record = service.register_generated_content(
                    tenant_id="tenant_default",
                    company_id="company_default",
                    job_id="job_identity",
                    created_by="operator",
                    file_type="generated_word",
                    filename="result.docx",
                    mime_type="application/octet-stream",
                    content=b"new-word-content",
                )

                self._assert_stored_content(service, old_record, content)
                self._assert_stored_content(service, new_record, b"new-word-content")
                self.assertNotEqual(old_record.object_key, new_record.object_key)
                self.assertEqual(service.repository.get_document_file(old_record.id).model_dump(mode="json"), before)
                self.assertEqual(new_record.original_filename, old_record.original_filename)

    def test_generated_keys_keep_safe_segments_and_original_download_name(self) -> None:
        for provider in ("local_file", "local_object", "s3"):
            with self.subTest(provider=provider), self._storage(provider, prefix=" /archive/tr-403/ ") as (service, _client):
                record = service.register_generated_content(
                    tenant_id="../tenant /default",
                    company_id="company_default",
                    job_id="../../job /alpha",
                    created_by="operator",
                    file_type="generated_word",
                    filename="../nested/../.result report.docx",
                    mime_type="application/octet-stream",
                    content=b"safe-path-content",
                )

                logical_key = f"document-jobs/tenant_default/job_alpha/generated_word/{record.id}/result_report.docx"
                expected_key = f"archive/tr-403/{logical_key}" if provider == "s3" else logical_key
                self.assertEqual(record.object_key, expected_key)
                self.assertEqual(record.original_filename, ".result report.docx")
                self._assert_stored_content(service, record, b"safe-path-content")
                if provider != "s3":
                    root = (
                        service.settings.jobs_artifact_object_store_dir
                        if provider == "local_object"
                        else service.settings.data_path / "document_file_objects"
                    ).resolve()
                    self.assertIn(root, service.resolve_local_object_path(record.object_key).parents)
                    with self.assertRaises(ValueError):
                        service.resolve_local_object_path("../outside.docx")

    def test_source_upload_keys_keep_existing_layout(self) -> None:
        user = AuthenticatedUser(
            id="operator",
            username="operator",
            role="operator",
            tenant_id="../tenant /default",
            company_id="company_default",
        )
        for provider in ("local_file", "local_object", "s3"):
            with self.subTest(provider=provider), self._storage(provider, prefix=" /archive/tr-403/ ") as (service, _client):
                authorization = service.create_upload_authorization(
                    user=user,
                    filename="../nested/source report.pdf",
                    mime_type="application/pdf",
                    size_bytes=20,
                    checksum_sha256=None,
                    job_id=None,
                )

                record = authorization.record
                logical_key = f"document-files/tenant_default/{record.id}/source_report.pdf"
                expected_key = f"archive/tr-403/{logical_key}" if provider == "s3" else logical_key
                self.assertEqual(record.object_key, expected_key)
                self.assertEqual(record.original_filename, "source report.pdf")
                self.assertEqual(record.status, "pending_upload")

    def test_invalid_s3_prefix_is_rejected_before_writing(self) -> None:
        with self._storage("s3", prefix="../unsafe") as (service, client):
            with self.assertRaises(ApiError) as raised:
                service.register_generated_content(
                    tenant_id="tenant_default",
                    company_id="company_default",
                    job_id="job_identity",
                    created_by="operator",
                    file_type="generated_word",
                    filename="result.docx",
                    mime_type="application/octet-stream",
                    content=b"must-not-be-written",
                )

            self.assertEqual(raised.exception.code, "invalid_request")
            self.assertEqual(client.objects, {})
            self.assertEqual(service.repository.list_document_files(), [])
