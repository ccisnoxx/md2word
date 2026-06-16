# File: app/domains/files/service.py
# Purpose: 处理文件元数据登记、上传授权、代理写入和保留期物理删除。

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Literal
from uuid import uuid4

from fastapi import status

from app.services.auth.models import AuthenticatedUser
from app.core.config import Settings
from app.core.errors import ApiError
from app.domains.files.models import DocumentFileRecord, DocumentFileStorageProvider, DocumentFileType
from app.domains.files.repository import DocumentFileRepositoryProtocol
from app.domains.files.validation import validate_pdf_metadata, validate_pdf_upload
from app.domains.resources.models import utc_now

RETENTION_DELETE_BATCH_LIMIT = 50
RETENTION_DELETE_CONFIRMATION_PHRASE = "DELETE EXPIRED FILES"
RETENTION_DELETE_SUPPORTED_LOCAL_PROVIDERS = {"local_file", "local_object"}
S3_DELETE_FAKE_CONTRACT_VERSION = "s3-delete-fake-v1"


@dataclass(frozen=True, slots=True)
class FileRetentionS3DeleteContract:
    """描述 S3 删除 fake adapter 的精确目标和安全边界，不代表真实删除授权。"""

    contract_version: str
    adapter_mode: Literal["fake"]
    bucket: str
    object_key: str
    version_id: str | None
    target_exact: bool
    missing_target_fields: list[str]
    expected_outcome: Literal["fake_skipped"]
    safety: dict[str, bool]

    def to_dict(self) -> dict[str, Any]:
        """转换为 API 响应和 cleanup hash 可复用的稳定字典。"""

        return {
            "contract_version": self.contract_version,
            "adapter_mode": self.adapter_mode,
            "bucket": self.bucket,
            "object_key": self.object_key,
            "version_id": self.version_id,
            "target_exact": self.target_exact,
            "missing_target_fields": self.missing_target_fields,
            "expected_outcome": self.expected_outcome,
            "safety": self.safety,
        }


@dataclass(frozen=True, slots=True)
class FileUploadAuthorization:
    """上传授权结果；本地代理上传时 upload_url 由 API router 补齐。"""

    record: DocumentFileRecord
    upload_url: str | None
    method: Literal["PUT"]
    headers: dict[str, str]
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class FileRetentionDeleteItem:
    """单个 document_file 物理删除预览或执行结果。"""

    file_id: str
    job_id: str | None
    file_type: str | None
    storage_provider: str | None
    status_before: str | None
    status_after: str | None
    object_key: str | None
    size_bytes: int | None
    outcome: str
    reason: str
    deleted: bool = False
    metadata_updated: bool = False
    s3_delete_contract: FileRetentionS3DeleteContract | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为 API schema 可直接校验的 dict。"""

        return {
            "file_id": self.file_id,
            "job_id": self.job_id,
            "file_type": self.file_type,
            "storage_provider": self.storage_provider,
            "status_before": self.status_before,
            "status_after": self.status_after,
            "object_key": self.object_key,
            "size_bytes": self.size_bytes,
            "outcome": self.outcome,
            "reason": self.reason,
            "deleted": self.deleted,
            "metadata_updated": self.metadata_updated,
            "s3_delete_contract": self.s3_delete_contract.to_dict() if self.s3_delete_contract is not None else None,
        }


@dataclass(frozen=True, slots=True)
class FileRetentionDeleteReport:
    """selected document_files 物理删除预览或执行汇总。"""

    generated_at: datetime
    action_mode: Literal["delete_preview", "delete_execute"]
    requested_file_ids: list[str]
    confirmation_phrase: str
    totals: dict[str, int]
    items: list[FileRetentionDeleteItem]


class FileUploadService:
    """管理 document_files 元数据和上传写入，不把二进制放入 metadata store。"""

    def __init__(
        self,
        settings: Settings,
        repository: DocumentFileRepositoryProtocol,
        retention_days_resolver: Callable[[str], int] | None = None,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.retention_days_resolver = retention_days_resolver or (lambda _file_type: settings.oss_file_retention_days)

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
        if job_id is not None and job_id.strip():
            raise ApiError(
                status.HTTP_400_BAD_REQUEST,
                "invalid_request",
                "source_pdf 上传授权不支持预绑定 job_id；请上传完成后通过 document_jobs 创建任务。",
            )
        file_id = f"file_{uuid4().hex[:12]}"
        provider = self._storage_provider()
        bucket = self._bucket_for(provider)
        if provider == "s3" and not bucket:
            raise ApiError(status.HTTP_503_SERVICE_UNAVAILABLE, "service_unavailable", "S3 bucket 未配置。")
        object_key = self._object_key_for(user.tenant_id, file_id, filename, provider)
        now = utc_now()
        expires_at = now + timedelta(days=self.retention_days_resolver("source_pdf"))
        record = DocumentFileRecord(
            id=file_id,
            tenant_id=user.tenant_id,
            company_id=user.company_id,
            job_id=None,
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

    def preview_retention_physical_delete(
        self,
        file_ids: list[str],
        *,
        now: datetime | None = None,
    ) -> FileRetentionDeleteReport:
        """预览 selected expired 文件的物理删除结果，不修改 metadata 或二进制。"""

        generated_at = self._normalize_datetime(now or utc_now())
        requested_file_ids = self._validate_retention_delete_file_ids(file_ids)
        items = [
            self._preview_retention_delete_item(file_id, now=generated_at)
            for file_id in requested_file_ids
        ]
        return self._build_retention_delete_report(
            generated_at=generated_at,
            action_mode="delete_preview",
            requested_file_ids=requested_file_ids,
            items=items,
        )

    def execute_retention_physical_delete(
        self,
        file_ids: list[str],
        *,
        reason: str,
        confirmation: str,
        now: datetime | None = None,
    ) -> FileRetentionDeleteReport:
        """执行 selected expired 文件的物理删除，并把成功项 metadata 标记为 deleted。"""

        normalized_reason = reason.strip()
        if not normalized_reason:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "reason 不能为空。")
        if confirmation != RETENTION_DELETE_CONFIRMATION_PHRASE:
            raise ApiError(
                status.HTTP_400_BAD_REQUEST,
                "invalid_request",
                f"confirmation 必须为 {RETENTION_DELETE_CONFIRMATION_PHRASE}。",
            )
        generated_at = self._normalize_datetime(now or utc_now())
        requested_file_ids = self._validate_retention_delete_file_ids(file_ids)
        items = [
            self._execute_retention_delete_item(file_id, now=generated_at)
            for file_id in requested_file_ids
        ]
        return self._build_retention_delete_report(
            generated_at=generated_at,
            action_mode="delete_execute",
            requested_file_ids=requested_file_ids,
            items=items,
        )

    def preview_document_job_physical_delete(
        self,
        file_ids: list[str],
        *,
        now: datetime | None = None,
    ) -> FileRetentionDeleteReport:
        """预览任务删除需要清理的 document_file，不要求文件先进入 expired。"""

        generated_at = self._normalize_datetime(now or utc_now())
        requested_file_ids = self._validate_retention_delete_file_ids(file_ids)
        items = [
            self._preview_document_job_delete_item(file_id, now=generated_at)
            for file_id in requested_file_ids
        ]
        return self._build_retention_delete_report(
            generated_at=generated_at,
            action_mode="delete_preview",
            requested_file_ids=requested_file_ids,
            items=items,
        )

    def execute_document_job_physical_delete(
        self,
        file_ids: list[str],
        *,
        now: datetime | None = None,
    ) -> FileRetentionDeleteReport:
        """执行任务删除需要清理的 document_file，并把成功项 metadata 标记为 deleted。"""

        generated_at = self._normalize_datetime(now or utc_now())
        requested_file_ids = self._validate_retention_delete_file_ids(file_ids)
        items = [
            self._execute_document_job_delete_item(file_id, now=generated_at)
            for file_id in requested_file_ids
        ]
        return self._build_retention_delete_report(
            generated_at=generated_at,
            action_mode="delete_execute",
            requested_file_ids=requested_file_ids,
            items=items,
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
            expires_at=expires_at or now + timedelta(days=self.retention_days_resolver(file_type)),
            metadata=metadata or {},
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        etag = self._write_object(record, content)
        stored = record.model_copy(update={"etag": etag, "updated_at": utc_now()})
        self.repository.create_document_file(stored)
        return stored

    def _validate_retention_delete_file_ids(self, file_ids: list[str]) -> list[str]:
        """校验物理删除批量 file_id，避免空值、重复和过大批次。"""

        if not file_ids:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "file_ids 不能为空。")
        if len(file_ids) > RETENTION_DELETE_BATCH_LIMIT:
            raise ApiError(
                status.HTTP_400_BAD_REQUEST,
                "invalid_request",
                f"单次最多允许处理 {RETENTION_DELETE_BATCH_LIMIT} 个文件。",
            )
        normalized = [file_id.strip() for file_id in file_ids]
        if any(not file_id for file_id in normalized):
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "file_ids 不能包含空白项。")
        if len(set(normalized)) != len(normalized):
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "file_ids 不能包含重复项。")
        return normalized

    def _preview_retention_delete_item(self, file_id: str, *, now: datetime) -> FileRetentionDeleteItem:
        """构建单个文件的物理删除预览结果。"""

        record = self.repository.get_document_file(file_id)
        if record is None:
            return FileRetentionDeleteItem(
                file_id=file_id,
                job_id=None,
                file_type=None,
                storage_provider=None,
                status_before=None,
                status_after=None,
                object_key=None,
                size_bytes=None,
                outcome="skipped_not_found",
                reason="文件 metadata 不存在。",
            )
        eligibility = self._retention_delete_eligibility(record, now=now)
        return self._build_retention_delete_item(
            record,
            outcome=eligibility[0],
            reason=eligibility[1],
            status_after=record.status,
        )

    def _execute_retention_delete_item(self, file_id: str, *, now: datetime) -> FileRetentionDeleteItem:
        """执行单个文件删除；不符合条件的文件只返回 skip outcome。"""

        record = self.repository.get_document_file(file_id)
        if record is None:
            return FileRetentionDeleteItem(
                file_id=file_id,
                job_id=None,
                file_type=None,
                storage_provider=None,
                status_before=None,
                status_after=None,
                object_key=None,
                size_bytes=None,
                outcome="skipped_not_found",
                reason="文件 metadata 不存在。",
            )
        outcome, reason = self._retention_delete_eligibility(record, now=now)
        if outcome != "deletable":
            return self._build_retention_delete_item(
                record,
                outcome=outcome,
                reason=reason,
                status_after=record.status,
            )
        return self._delete_retention_local_object(record, now=now)

    def _preview_document_job_delete_item(self, file_id: str, *, now: datetime) -> FileRetentionDeleteItem:
        """构建任务删除流程的单文件清理预览，不要求 retention 过期。"""

        record = self.repository.get_document_file(file_id)
        if record is None:
            return FileRetentionDeleteItem(
                file_id=file_id,
                job_id=None,
                file_type=None,
                storage_provider=None,
                status_before=None,
                status_after=None,
                object_key=None,
                size_bytes=None,
                outcome="skipped_not_found",
                reason="文件 metadata 不存在。",
            )
        outcome, reason = self._document_job_delete_eligibility(record)
        if outcome != "deletable":
            return self._build_retention_delete_item(
                record,
                outcome=outcome,
                reason=reason,
                status_after=record.status,
            )
        return self._build_retention_delete_item(
            record,
            outcome="deletable",
            reason="任务删除将清理该文件。",
            status_after=record.status,
        )

    def _execute_document_job_delete_item(self, file_id: str, *, now: datetime) -> FileRetentionDeleteItem:
        """执行任务删除流程的单文件清理；底层删除逻辑与 retention 删除共用。"""

        record = self.repository.get_document_file(file_id)
        if record is None:
            return FileRetentionDeleteItem(
                file_id=file_id,
                job_id=None,
                file_type=None,
                storage_provider=None,
                status_before=None,
                status_after=None,
                object_key=None,
                size_bytes=None,
                outcome="skipped_not_found",
                reason="文件 metadata 不存在。",
            )
        outcome, reason = self._document_job_delete_eligibility(record)
        if outcome != "deletable":
            return self._build_retention_delete_item(
                record,
                outcome=outcome,
                reason=reason,
                status_after=record.status,
            )
        return self._delete_retention_local_object(record, now=now)

    def _document_job_delete_eligibility(self, record: DocumentFileRecord) -> tuple[str, str]:
        """判断任务删除流程是否可直接清理该文件，不要求 retention 过期。"""

        if record.status == "deleted":
            return "skipped_already_deleted", "文件 metadata 已是 deleted。"
        if record.status == "pending_upload":
            return "skipped_pending_upload", "文件仍处于 pending_upload，未执行物理删除。"
        if record.storage_provider not in RETENTION_DELETE_SUPPORTED_LOCAL_PROVIDERS:
            return "skipped_unsupported_storage", f"暂不支持物理删除 storage_provider={record.storage_provider}。"
        if not record.object_key.strip():
            return "skipped_missing_object_key", "文件缺少 object_key，不能物理删除。"
        return "deletable", "eligible_document_job_file"

    def _retention_delete_eligibility(self, record: DocumentFileRecord, *, now: datetime) -> tuple[str, str]:
        """判断文件是否满足第一版物理删除条件。"""

        if record.status == "deleted":
            return "skipped_already_deleted", "文件 metadata 已是 deleted。"
        if record.status != "expired":
            return "skipped_not_expired_status", "文件必须先标记为 expired。"
        if record.expires_at is None:
            return "skipped_not_expired_time", "文件缺少 expires_at，不能物理删除。"
        expires_at = self._normalize_datetime(record.expires_at)
        if expires_at > now:
            return "skipped_not_expired_time", "文件尚未超过 expires_at。"
        if record.storage_provider not in RETENTION_DELETE_SUPPORTED_LOCAL_PROVIDERS:
            return "skipped_unsupported_storage", f"暂不支持物理删除 storage_provider={record.storage_provider}。"
        if not record.object_key.strip():
            return "skipped_missing_object_key", "文件缺少 object_key，不能物理删除。"
        return "deletable", "eligible_expired_file"

    def _delete_retention_local_object(self, record: DocumentFileRecord, *, now: datetime) -> FileRetentionDeleteItem:
        """删除本地 document_file 二进制，并在成功或已缺失时保留 metadata 但标记 deleted。"""

        try:
            object_path = self._resolve_retention_local_path(record)
            if object_path.exists():
                object_path.unlink()
                outcome = "deleted"
                reason = "本地文件已删除。"
                deleted = True
            else:
                outcome = "already_missing"
                reason = "本地文件已不存在，按幂等清理处理。"
                deleted = False
            updated = self.repository.update_document_file(
                record.id,
                status="deleted",
                updated_at=now,
            )
        except OSError as exc:
            return self._build_retention_delete_item(
                record,
                outcome="failed",
                reason=f"本地文件删除失败: {exc.__class__.__name__}",
                status_after=record.status,
            )
        except (FileNotFoundError, ValueError) as exc:
            return self._build_retention_delete_item(
                record,
                outcome="failed",
                reason=f"metadata 更新或路径解析失败: {exc.__class__.__name__}",
                status_after=record.status,
            )
        return self._build_retention_delete_item(
            record,
            outcome=outcome,
            reason=reason,
            status_after=updated.status,
            deleted=deleted,
            metadata_updated=True,
        )

    def _build_retention_delete_item(
        self,
        record: DocumentFileRecord,
        *,
        outcome: str,
        reason: str,
        status_after: str,
        deleted: bool = False,
        metadata_updated: bool = False,
    ) -> FileRetentionDeleteItem:
        """把 document_file metadata 和 outcome 组合为稳定删除结果项。"""

        return FileRetentionDeleteItem(
            file_id=record.id,
            job_id=record.job_id,
            file_type=record.file_type,
            storage_provider=record.storage_provider,
            status_before=record.status,
            status_after=status_after,
            object_key=record.object_key,
            size_bytes=record.size_bytes,
            outcome=outcome,
            reason=reason,
            deleted=deleted,
            metadata_updated=metadata_updated,
            s3_delete_contract=self._build_s3_delete_contract(record),
        )

    def _build_s3_delete_contract(self, record: DocumentFileRecord) -> FileRetentionS3DeleteContract | None:
        """为 S3 文件生成 fake deletion safety contract，不读取 secret 或调用 S3。"""

        if record.storage_provider != "s3":
            return None
        bucket = record.bucket.strip()
        object_key = record.object_key.strip()
        missing_target_fields = []
        if not bucket:
            missing_target_fields.append("bucket")
        if not object_key:
            missing_target_fields.append("object_key")
        version_id = record.metadata.get("s3_version_id")
        normalized_version_id = version_id.strip() if isinstance(version_id, str) and version_id.strip() else None
        return FileRetentionS3DeleteContract(
            contract_version=S3_DELETE_FAKE_CONTRACT_VERSION,
            adapter_mode="fake",
            bucket=bucket,
            object_key=object_key,
            version_id=normalized_version_id,
            target_exact=not missing_target_fields,
            missing_target_fields=missing_target_fields,
            expected_outcome="fake_skipped",
            safety={
                "real_s3_delete_executed": False,
                "fake_s3_delete_executed": True,
                "metadata_mutated": False,
                "audit_events_written": False,
                "requires_future_real_adapter": True,
            },
        )

    def _build_retention_delete_report(
        self,
        *,
        generated_at: datetime,
        action_mode: Literal["delete_preview", "delete_execute"],
        requested_file_ids: list[str],
        items: list[FileRetentionDeleteItem],
    ) -> FileRetentionDeleteReport:
        """汇总删除预览或执行结果，供 API 和审计复用。"""

        totals = {
            "requested": len(requested_file_ids),
            "deletable": sum(1 for item in items if item.outcome == "deletable"),
            "deleted": sum(1 for item in items if item.outcome == "deleted"),
            "already_missing": sum(1 for item in items if item.outcome == "already_missing"),
            "skipped": sum(1 for item in items if item.outcome.startswith("skipped_")),
            "failed": sum(1 for item in items if item.outcome == "failed"),
            "metadata_updated": sum(1 for item in items if item.metadata_updated),
        }
        return FileRetentionDeleteReport(
            generated_at=generated_at,
            action_mode=action_mode,
            requested_file_ids=requested_file_ids,
            confirmation_phrase=RETENTION_DELETE_CONFIRMATION_PHRASE,
            totals=totals,
            items=items,
        )

    def _resolve_retention_local_path(self, record: DocumentFileRecord) -> Path:
        """按文件记录自身的 storage_provider 解析本地路径，避免运行时配置切换导致删错根目录。"""

        if record.storage_provider == "local_object":
            root = self.settings.jobs_artifact_object_store_dir.resolve()
        else:
            root = (self.settings.data_path / "document_file_objects").resolve()
        candidate = (root / record.object_key).resolve()
        if candidate != root and root not in candidate.parents:
            raise ValueError(f"object_key 越界: {record.object_key}")
        return candidate

    def _ensure_visible(self, record: DocumentFileRecord, user: AuthenticatedUser) -> None:
        if record.tenant_id != user.tenant_id or record.company_id != user.company_id:
            raise ApiError(status.HTTP_403_FORBIDDEN, "forbidden", "无权限访问该文件。")
        if user.role == "admin":
            return
        if record.created_by == user.id:
            return
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

    def _normalize_datetime(self, value: datetime) -> datetime:
        """把 naive datetime 视为 UTC，避免和 aware datetime 比较时报错。"""

        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


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
