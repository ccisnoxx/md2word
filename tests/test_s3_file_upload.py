from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from botocore.exceptions import ClientError

from app.domains.files.service import FileUploadService
from app.main import create_app
from tests.test_fastapi_jobs_backend import (
    build_auth_header,
    build_multi_operator_auth_users_json,
    build_test_runtime,
    make_pdf_bytes,
)


class S3FileUploadTests(TestCase):
    """验证 S3 源文件经过真实代理上传路由后才能用于创建任务。"""

    def setUp(self) -> None:
        data_dir = self.enterContext(TemporaryDirectory())
        self.runtime = build_test_runtime(
            Path(data_dir),
            jobs_artifact_storage_backend="s3",
            jobs_artifact_s3_bucket="test-source-bucket",
            jobs_artifact_s3_key_prefix="test-prefix",
            auth_jwt_secret_key="test-jwt-secret",
            auth_internal_users_json=build_multi_operator_auth_users_json(),
            document_jobs_worker_backend="disabled",
        )
        self.s3 = Mock(spec=["put_object", "get_object", "generate_presigned_url"])
        self.s3.put_object.return_value = {"ETag": '"test-source-etag"'}
        self.s3.generate_presigned_url.return_value = "https://signed.example/source.pdf"
        self.enterContext(patch.object(FileUploadService, "_s3_client", return_value=self.s3))
        self.client = self.enterContext(TestClient(create_app(self.runtime), raise_server_exceptions=False))
        self.headers = build_auth_header(self.client)

    def test_s3_authorization_upload_and_job_creation_use_authenticated_api(self) -> None:
        content = make_pdf_bytes(page_count=2)
        checksum = f"sha256:{hashlib.sha256(content).hexdigest()}"
        authorization = self.client.post(
            "/api/v1/files/upload-url",
            headers={**self.headers, "X-Forwarded-Proto": "https"},
            json={
                "filename": "source.pdf",
                "mime_type": "application/pdf",
                "size_bytes": len(content),
                "checksum_sha256": checksum,
            },
        )
        self.assertEqual(authorization.status_code, 201, authorization.text)
        payload = authorization.json()
        file_id = payload["file_id"]
        self.assertEqual(payload["upload_url"], f"https://testserver/api/v1/files/{file_id}/content")
        self.assertEqual(payload["method"], "PUT")
        self.assertEqual(payload["headers"], {"Content-Type": "application/pdf"})
        self.assertEqual(payload["file"]["storage_provider"], "s3")
        self.assertEqual(payload["file"]["status"], "pending_upload")
        self.assertTrue(payload["object_key"].startswith("test-prefix/document-files/tenant_default/"))
        self.s3.generate_presigned_url.assert_not_called()

        missing_token = self.client.put(payload["upload_url"], headers=payload["headers"], content=content)
        self.assertEqual(missing_token.status_code, 401)
        other_headers = build_auth_header(self.client, username="operator2", password="operator2-pass")
        other_upload = self.client.put(
            payload["upload_url"],
            headers={**other_headers, **payload["headers"]},
            content=content,
        )
        self.assertEqual(other_upload.status_code, 403)
        self.s3.put_object.assert_not_called()

        uploaded = self.client.put(
            payload["upload_url"],
            headers={**self.headers, **payload["headers"]},
            content=content,
        )
        self.assertEqual(uploaded.status_code, 201, uploaded.text)
        metadata = self.client.get(f"/api/v1/files/{file_id}", headers=self.headers)
        self.assertEqual(metadata.status_code, 200, metadata.text)
        uploaded_file = metadata.json()
        self.assertEqual(uploaded_file["status"], "uploaded")
        self.assertEqual(uploaded_file["checksum_sha256"], checksum)
        self.assertEqual(uploaded_file["etag"], "test-source-etag")
        self.assertEqual(uploaded_file["metadata"]["page_count"], 2)
        self.assertEqual(uploaded_file["metadata"]["uploaded_size_bytes"], len(content))
        self.s3.put_object.assert_called_once_with(
            Bucket="test-source-bucket",
            Key=payload["object_key"],
            Body=content,
            ContentType="application/pdf",
            IfNoneMatch="*",
        )

        created = self.client.post(
            "/api/v1/document-jobs",
            headers=self.headers,
            json={"source_file_id": file_id, "mode": "direct_pdf_to_word"},
        )
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["job"]["source_file_id"], file_id)
        self.assertEqual(created.json()["status"], "pending")
        self.assertEqual(created.json()["stage"], "uploaded")
        record = self.runtime.document_file_repository.get_document_file(file_id)
        self.assertEqual(record.job_id, created.json()["job_id"])
        upload_events = [
            event
            for event in self.runtime.audit_event_repository.list_audit_events()
            if event.action == "file.upload_content" and event.target_id == file_id
        ]
        self.assertEqual(len(upload_events), 1)

        download_url = self.runtime.file_upload_service.create_presigned_download_url(record, expires_seconds=600)
        self.assertEqual(download_url, "https://signed.example/source.pdf")
        self.s3.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "test-source-bucket", "Key": payload["object_key"]},
            ExpiresIn=600,
        )

    def test_s3_existing_object_only_accepts_identical_content(self) -> None:
        """已有对象的条件创建失败时，只允许同内容收口；不同PDF不能伪装上传成功。"""
        stored_content = make_pdf_bytes()
        for identical in (True, False):
            with self.subTest(identical=identical):
                content = stored_content if identical else stored_content + b"\n% distinct test PDF\n"
                authorization = self.client.post(
                    "/api/v1/files/upload-url",
                    headers=self.headers,
                    json={"filename": "source.pdf", "size_bytes": len(content)},
                )
                self.assertEqual(authorization.status_code, 201, authorization.text)
                payload = authorization.json()
                self.s3.reset_mock()
                # 模拟S3已有实物的条件创建拒绝；读回内容不受此次上传改变。
                self.s3.put_object.side_effect = ClientError(
                    {"Error": {"Code": "PreconditionFailed"}, "ResponseMetadata": {"HTTPStatusCode": 412}},
                    "PutObject",
                )
                self.s3.get_object.return_value = {"Body": BytesIO(stored_content)}
                response = self.client.put(
                    payload["upload_url"],
                    headers={**self.headers, **payload["headers"]},
                    content=content,
                )
                self.s3.put_object.assert_called_once_with(
                    Bucket="test-source-bucket", Key=payload["object_key"], Body=content,
                    ContentType="application/pdf", IfNoneMatch="*",
                )
                self.s3.get_object.assert_called_once_with(Bucket="test-source-bucket", Key=payload["object_key"])
                record = self.runtime.document_file_repository.get_document_file(payload["file_id"])
                if identical:
                    self.assertEqual(response.status_code, 201, response.text)
                    self.assertEqual(record.status, "uploaded")
                    self.assertEqual(record.checksum_sha256, f"sha256:{hashlib.sha256(stored_content).hexdigest()}")
                    self.assertEqual(record.metadata["page_count"], 1)
                else:
                    self.assertEqual(response.status_code, 409, response.text)
                    self.assertEqual(response.json()["error_code"], "conflict")
                    self.assertEqual(record.status, "pending_upload")
                    self.assertIsNone(record.checksum_sha256)
                    self.assertNotIn("page_count", record.metadata)
                    self.assertFalse(any(
                        event.action == "file.upload_content" and event.target_id == record.id
                        for event in self.runtime.audit_event_repository.list_audit_events()
                    ))

    def test_s3_write_failure_keeps_pending_and_prevents_job_creation(self) -> None:
        content = make_pdf_bytes()
        authorization = self.client.post(
            "/api/v1/files/upload-url",
            headers=self.headers,
            json={"filename": "source.pdf", "size_bytes": len(content)},
        )
        self.assertEqual(authorization.status_code, 201, authorization.text)
        payload = authorization.json()
        file_id = payload["file_id"]
        self.s3.put_object.side_effect = OSError("测试 S3 对象写入失败。")

        uploaded = self.client.put(
            payload["upload_url"],
            headers={**self.headers, **payload["headers"]},
            content=content,
        )
        self.assertEqual(uploaded.status_code, 500)
        self.s3.put_object.assert_called_once()
        metadata = self.client.get(f"/api/v1/files/{file_id}", headers=self.headers)
        self.assertEqual(metadata.status_code, 200, metadata.text)
        self.assertEqual(metadata.json()["status"], "pending_upload")
        self.assertIsNone(metadata.json()["checksum_sha256"])
        self.assertIsNone(metadata.json()["etag"])
        self.assertNotIn("page_count", metadata.json()["metadata"])
        created = self.client.post(
            "/api/v1/document-jobs",
            headers=self.headers,
            json={"source_file_id": file_id, "mode": "direct_pdf_to_word"},
        )
        self.assertEqual(created.status_code, 409, created.text)
        self.assertEqual(created.json()["error_code"], "conflict")
        self.assertFalse(
            any(
                event.action == "file.upload_content" and event.target_id == file_id
                for event in self.runtime.audit_event_repository.list_audit_events()
            )
        )

    def test_s3_invalid_pdf_is_rejected_before_object_write(self) -> None:
        content = b"invalid-pdf-content"
        authorization = self.client.post(
            "/api/v1/files/upload-url",
            headers=self.headers,
            json={"filename": "source.pdf", "size_bytes": len(content)},
        )
        self.assertEqual(authorization.status_code, 201, authorization.text)
        payload = authorization.json()
        uploaded = self.client.put(
            payload["upload_url"],
            headers={**self.headers, **payload["headers"]},
            content=content,
        )
        self.assertEqual(uploaded.status_code, 400, uploaded.text)
        self.assertEqual(uploaded.json()["error_code"], "invalid_request")
        self.assertEqual(
            self.runtime.document_file_repository.get_document_file(payload["file_id"]).status,
            "pending_upload",
        )
        self.s3.put_object.assert_not_called()
