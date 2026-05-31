from __future__ import annotations

# app/domains/files/service.py: 处理文件元数据登记、上传授权和后端代理写入。

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any, Literal
from uuid import uuid4

from fastapi import status

from app.services.auth.models import AuthenticatedUser
from app.core.config import Settings
from app.core.errors import ApiError
from app.domains.files.models import DocumentFileRecord, DocumentFileStorageProvider, DocumentFileType
from app.domains.files.repository import DocumentFileRepositoryProtocol
from app.domains.files.validation import validate_pdf_metadata, validate_pdf_upload
from app.domains.jobs.models import utc_now


@dataclass(frozen=True, slots=True)
class FileUploadAuthorization:
    """上传授权结果；本地代理上传时 upload_url 由 API router 补齐。"""

    record: DocumentFileRecord
    upload_url: str | None
    method: Literal["PUT"]
    headers: dict[str, str]
    expires_at: datetime


class FileUploadService:
    """管理 document_files 元数据和上传写入，不把二进制放入 metadata store。"""

    def __init__(self, settings: Settings, repository: DocumentFileRepositoryProtocol) -> None:
        self.settings = settings
        self.repository = repository

    def create_upload_authorization(
        self,
        *,
        user: AuthenticatedUser,
        filename: str,
        mime_type: str,
        size_bytes: int,
        checksum_sha256: str | None,
        job_id: str | None,
    ) -> FileUploadAuthorization:
        """登记 source_pdf 元数据，并生成本地代理或 S3 直传授权。"""

        validate_pdf_metadata(
            filename=filename,
            content_type=mime_type,
            size_bytes=size_bytes,
            max_bytes=self.settings.jobs_upload_max_bytes,
        )
        file_id = f"file_{uuid4().hex[:12]}"
        provider = self._storage_provider()
        bucket = self._bucket_for(provider)
        if provider == "s3" and not bucket:
            raise ApiError(status.HTTP_503_SERVICE_UNAVAILABLE, "service_unavailable", "S3 bucket 未配置。")
        object_key = self._object_key_for(user.tenant_id, file_id, filename, provider)
        now = utc_now()
        expires_at = now + timedelta(days=self.settings.oss_file_retention_days)
        record = DocumentFileRecord(
            id=file_id,
            tenant_id=user.tenant_id,
            company_id=user.company_id,
            job_id=job_id,
            file_type="source_pdf",
            storage_provider=provider,
            bucket=bucket,
            object_key=object_key,
            original_filename=Path(filename).name,
            mime_type=mime_type,
            size_bytes=size_bytes,
            checksum_sha256=checksum_sha256,
            status="pending_upload",
            expires_at=expires_at,
            created_by=user.id,
            created_at=now,
            updated_at=now,
        )
        upload_url = self._build_presigned_put_url(record) if provider == "s3" else None
        self.repository.create_document_file(record)
        return FileUploadAuthorization(
            record=record,
            upload_url=upload_url,
            method="PUT",
            headers={"Content-Type": record.mime_type},
            expires_at=now + timedelta(seconds=self.settings.oss_upload_presign_expires_seconds),
        )

    def get_document_file(self, file_id: str, *, user: AuthenticatedUser) -> DocumentFileRecord:
        """读取单个文件元数据，并做最小租户隔离。"""

        record = self.repository.get_document_file(file_id)
        if record is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", f"文件不存在: {file_id}")
        self._ensure_visible(record, user)
        return record

    def upload_authorized_content(
        self,
        *,
        file_id: str,
        user: AuthenticatedUser,
        content: bytes,
        content_type: str | None,
    ) -> DocumentFileRecord:
        """通过后端代理上传已授权文件内容，并回填 checksum / page_count。"""

        record = self.get_document_file(file_id, user=user)
        if record.status != "pending_upload":
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "文件当前状态不允许重复上传。")
        validation = validate_pdf_upload(
            filename=record.original_filename,
            content_type=content_type or record.mime_type,
            content=content,
            max_bytes=self.settings.jobs_upload_max_bytes,
            max_pages=self.settings.pdf_upload_max_pages,
        )
        if validation.size_bytes != record.size_bytes:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "上传内容大小与授权元数据不一致。")

        checksum_sha256 = f"sha256:{hashlib.sha256(content).hexdigest()}"
        if record.checksum_sha256 and record.checksum_sha256 != checksum_sha256:
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "上传内容 checksum 与授权元数据不一致。")

        etag = self._write_object(record, content)
        metadata = dict(record.metadata)
        metadata.update(
            {
                "page_count": validation.page_count,
                "uploaded_size_bytes": validation.size_bytes,
            }
        )
        return self.repository.update_document_file(
            file_id,
            status="uploaded",
            size_bytes=validation.size_bytes,
            checksum_sha256=checksum_sha256,
            etag=etag,
            metadata=metadata,
            updated_at=utc_now(),
        )

    def resolve_local_object_path(self, object_key: str) -> Path:
        """把本地 object_key 解析到实际路径，供测试和本地调试验证。"""

        root = self._local_object_root().resolve()
        candidate = (root / object_key).resolve()
        if candidate != root and root not in candidate.parents:
            raise ValueError(f"object_key 越界: {object_key}")
        return candidate

    def read_file_content(self, record: DocumentFileRecord) -> bytes:
        """读取 document_file 二进制内容，供 Worker 提交源文件和解析中间资产。"""

        if record.storage_provider == "s3":
            response = self._s3_client().get_object(Bucket=record.bucket, Key=record.object_key)
            body = response["Body"]
            return body.read()
        return self.resolve_local_object_path(record.object_key).read_bytes()

    def create_presigned_download_url(self, record: DocumentFileRecord, *, expires_seconds: int) -> str:
        """为 S3 文件生成临时下载 URL；本地存储由 API 路由签发本地 URL。"""

        if record.storage_provider != "s3":
            raise ValueError("本地文件下载不支持 S3 presigned URL。")
        if not record.bucket:
            raise ApiError(status.HTTP_503_SERVICE_UNAVAILABLE, "service_unavailable", "S3 bucket 未配置。")
        return self._s3_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": record.bucket, "Key": record.object_key},
            ExpiresIn=expires_seconds,
        )

    def register_generated_content(
        self,
        *,
        tenant_id: str,
        company_id: str,
        job_id: str,
        created_by: str | None,
        file_type: DocumentFileType,
        filename: str,
        mime_type: str,
        content: bytes,
        metadata: dict[str, Any] | None = None,
        expires_at: datetime | None = None,
    ) -> DocumentFileRecord:
        """登记并写入 Worker 生成的中间或结果文件。"""

        file_id = f"file_{uuid4().hex[:12]}"
        provider = self._storage_provider()
        bucket = self._bucket_for(provider)
        if provider == "s3" and not bucket:
            raise ApiError(status.HTTP_503_SERVICE_UNAVAILABLE, "service_unavailable", "S3 bucket 未配置。")
        object_key = self._generated_object_key_for(
            tenant_id=tenant_id,
            job_id=job_id,
            file_type=file_type,
            filename=filename,
            provider=provider,
        )
        now = utc_now()
        checksum_sha256 = f"sha256:{hashlib.sha256(content).hexdigest()}"
        record = DocumentFileRecord(
            id=file_id,
            tenant_id=tenant_id,
            company_id=company_id,
            job_id=job_id,
            file_type=file_type,
            storage_provider=provider,
            bucket=bucket,
            object_key=object_key,
            original_filename=Path(filename).name,
            mime_type=mime_type,
            size_bytes=len(content),
            checksum_sha256=checksum_sha256,
            status="uploaded",
            expires_at=expires_at or now + timedelta(days=self.settings.oss_file_retention_days),
            metadata=metadata or {},
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        etag = self._write_object(record, content)
        stored = record.model_copy(update={"etag": etag, "updated_at": utc_now()})
        self.repository.create_document_file(stored)
        return stored

    def _ensure_visible(self, record: DocumentFileRecord, user: AuthenticatedUser) -> None:
        if user.role == "admin":
            return
        if record.tenant_id != user.tenant_id or record.company_id != user.company_id:
            raise ApiError(status.HTTP_403_FORBIDDEN, "forbidden", "无权限访问该文件。")

    def _storage_provider(self) -> DocumentFileStorageProvider:
        if self.settings.jobs_artifact_storage_backend == "s3":
            return "s3"
        if self.settings.jobs_artifact_storage_backend == "local_object":
            return "local_object"
        return "local_file"

    def _bucket_for(self, provider: DocumentFileStorageProvider) -> str:
        if provider == "s3":
            return self.settings.jobs_artifact_s3_bucket
        if provider == "local_object":
            return "local-object"
        return "local-file"

    def _object_key_for(
        self,
        tenant_id: str,
        file_id: str,
        filename: str,
        provider: DocumentFileStorageProvider,
    ) -> str:
        safe_filename = _safe_object_filename(filename)
        logical_key = f"document-files/{_safe_path_part(tenant_id)}/{file_id}/{safe_filename}"
        if provider != "s3":
            return logical_key
        prefix = _normalize_key_prefix(self.settings.jobs_artifact_s3_key_prefix)
        if prefix:
            return f"{prefix}/{logical_key}"
        return logical_key

    def _generated_object_key_for(
        self,
        *,
        tenant_id: str,
        job_id: str,
        file_type: DocumentFileType,
        filename: str,
        provider: DocumentFileStorageProvider,
    ) -> str:
        safe_filename = _safe_object_filename(filename)
        logical_key = (
            f"document-jobs/{_safe_path_part(tenant_id)}/{_safe_path_part(job_id)}/"
            f"{_safe_path_part(file_type)}/{safe_filename}"
        )
        if provider != "s3":
            return logical_key
        prefix = _normalize_key_prefix(self.settings.jobs_artifact_s3_key_prefix)
        if prefix:
            return f"{prefix}/{logical_key}"
        return logical_key

    def _write_object(self, record: DocumentFileRecord, content: bytes) -> str | None:
        if record.storage_provider == "s3":
            response = self._s3_client().put_object(
                Bucket=record.bucket,
                Key=record.object_key,
                Body=content,
                ContentType=record.mime_type,
            )
            etag = response.get("ETag") if isinstance(response, dict) else None
            return str(etag).strip('"') if etag else None

        target_path = self.resolve_local_object_path(record.object_key)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = target_path.with_name(f"{target_path.name}.tmp")
        temp_path.write_bytes(content)
        temp_path.replace(target_path)
        return f"sha256:{hashlib.sha256(content).hexdigest()}"

    def _local_object_root(self) -> Path:
        if self.settings.jobs_artifact_storage_backend == "local_object":
            return self.settings.jobs_artifact_object_store_dir
        return self.settings.data_path / "document_file_objects"

    def _build_presigned_put_url(self, record: DocumentFileRecord) -> str:
        if not record.bucket:
            raise ApiError(status.HTTP_503_SERVICE_UNAVAILABLE, "service_unavailable", "S3 bucket 未配置。")
        return self._s3_client().generate_presigned_url(
            "put_object",
            Params={"Bucket": record.bucket, "Key": record.object_key, "ContentType": record.mime_type},
            ExpiresIn=self.settings.oss_upload_presign_expires_seconds,
        )

    def _s3_client(self) -> Any:
        try:
            import boto3
        except ModuleNotFoundError as exc:  # pragma: no cover - depends on deployment env
            raise ApiError(status.HTTP_503_SERVICE_UNAVAILABLE, "service_unavailable", "S3 上传需要安装 boto3。") from exc

        kwargs: dict[str, str] = {}
        if self.settings.jobs_artifact_s3_endpoint_url:
            kwargs["endpoint_url"] = self.settings.jobs_artifact_s3_endpoint_url
        if self.settings.jobs_artifact_s3_region:
            kwargs["region_name"] = self.settings.jobs_artifact_s3_region
        if self.settings.jobs_artifact_s3_access_key_id:
            kwargs["aws_access_key_id"] = self.settings.jobs_artifact_s3_access_key_id
        if self.settings.jobs_artifact_s3_secret_access_key:
            kwargs["aws_secret_access_key"] = self.settings.jobs_artifact_s3_secret_access_key
        return boto3.client("s3", **kwargs)


def _safe_object_filename(filename: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(filename).name).strip("._")
    return safe or "upload.pdf"


def _safe_path_part(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")
    return safe or "default"


def _normalize_key_prefix(key_prefix: str) -> str:
    stripped = key_prefix.strip().strip("/")
    if not stripped:
        return ""
    prefix = PurePosixPath(stripped)
    if prefix.is_absolute() or any(part in {"", ".", ".."} for part in prefix.parts):
        raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", f"S3 object_key prefix 非法: {key_prefix}")
    return prefix.as_posix()
